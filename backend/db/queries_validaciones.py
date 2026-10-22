"""
Queries de las tablas `validaciones` y `auditoria`.

Auditoría se incluye acá porque sus operaciones siempre forman parte de
transacciones de validaciones — nunca se llaman de forma independiente.

Todas las funciones son síncronas (psycopg2).
Llamar desde contexto async con el helper q() de db.base.
"""
import psycopg2.pool
from models.resultado import ResultadoOCR

from db.base import conexion_escritura, conexion_lectura


def _a_float_monto(monto_str: str | None) -> float | None:
    if not monto_str:
        return None
    from services.mp_client import _parsear_monto
    return _parsear_monto(monto_str)


def _extraer_campos_ocr(
    resultado_ocr: ResultadoOCR | None,
) -> tuple[str | None, float | None, bool, str | None, str | None, str | None, str | None]:
    return (
        resultado_ocr.fuente                       if resultado_ocr else None,
        resultado_ocr.confianza                    if resultado_ocr else None,
        resultado_ocr.baja_confianza_identificador if resultado_ocr else False,
        resultado_ocr.fecha_comprobante            if resultado_ocr else None,
        resultado_ocr.cvu_cbu_destinatario         if resultado_ocr else None,
        resultado_ocr.entidad_emisora              if resultado_ocr else None,
        resultado_ocr.cuit_remitente               if resultado_ocr else None,
    )


def _fila_a_dict(row: tuple) -> dict:
    return {
        "id": row[0], "run_id": row[1], "respuesta_id": row[2],
        "codigo_cliente": row[3], "estado": row[4],
        "identificador_pago": row[5], "monto_detectado": row[6],
        "cuit_destinatario_detectado": row[7], "es_comprobante_valido": row[8],
        "mp_status_code": row[9], "error": row[10],
        "procesado_en": row[11].isoformat() if row[11] else None,
        "codigo_vendedor": row[12], "canal": row[13],
        "fecha_modificacion": row[14].isoformat() if row[14] else None,
        "imagen_path": row[15],
        "modificado_por_nombre": row[16],
        "creado_por_nombre": row[17],
        "observaciones": row[18],
        "estado_inicial": row[19],
        "entidad_emisora": row[20],
    }


def obtener_ops_aprobadas(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
) -> set[str]:
    """Reemplaza ops_aprobadas del procesados.json."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT identificador_pago FROM validaciones
            WHERE tenant_id = %s AND estado = 'APROBADO'
              AND identificador_pago IS NOT NULL
            """,
            (tenant_id,),
        )
        return {row[0] for row in cur.fetchall()}


def guardar_validacion_manual(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
    codigo_cliente: str,
    estado: str,
    identificador_pago: str | None,
    monto_detectado_str: str | None,
    cuit_destinatario_detectado: str | None,
    es_comprobante_valido: bool,
    mp_status_code: int | None,
    imagen_path: str | None,
    resultado_ocr: ResultadoOCR | None = None,
    creado_por_admin_id: str | None = None,
    cliente_id: str | None = None,
) -> dict:
    """
    Inserta una validación originada en el upload manual de un admin.

    canal = 'MANUAL', run_id = NULL, respuesta_id = NULL.

    Por qué recibe el UUID ya generado (validacion_id):
      El caller genera el UUID antes de guardar la imagen en disco, de modo que
      el nombre del archivo coincide con el id de la fila en DB.
      Así la relación archivo↔fila es 1-a-1 sin necesidad de un segundo UPDATE.

    monto_detectado_str: el texto crudo del OCR (ej: "$1.500,00").
      La función lo parsea a float internamente, igual que guardar_validacion.
    """
    monto_float = _a_float_monto(monto_detectado_str)
    ocr_fuente, ocr_confianza, baja_confianza_num, fecha_comprobante, cvu_cbu, entidad_emisora, cuit_remitente = _extraer_campos_ocr(resultado_ocr)

    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH fila_insertada AS (
                INSERT INTO validaciones (
                    id, tenant_id, canal, codigo_cliente,
                        estado, estado_inicial, identificador_pago, monto_detectado,
                        cuit_destinatario_detectado, es_comprobante_valido,
                        mp_status_code, imagen_path, creado_por_admin_id,
                        ocr_fuente, ocr_confianza, baja_confianza_identificador,
                        fecha_comprobante, cvu_cbu_destinatario,
                        entidad_emisora, cuit_remitente, cliente_id
                    ) VALUES (
                        %s::uuid, %s, 'MANUAL', %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s::uuid,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s::uuid
                    )
                    RETURNING *
                )
                SELECT fi.id::text, fi.run_id::text, fi.respuesta_id, fi.codigo_cliente,
                       fi.estado, fi.identificador_pago, fi.monto_detectado,
                       fi.cuit_destinatario_detectado, fi.es_comprobante_valido,
                       fi.mp_status_code, fi.error, fi.procesado_en,
                       fi.codigo_vendedor, fi.canal, fi.fecha_modificacion, fi.imagen_path,
                       NULL AS modificado_por_nombre,
                       a.nombre AS creado_por_nombre,
                       fi.observaciones, fi.estado_inicial,
                       fi.entidad_emisora
                FROM fila_insertada fi
                LEFT JOIN admins a ON a.id = fi.creado_por_admin_id
                """,
                (
                    validacion_id, tenant_id, codigo_cliente,
                    estado, estado, identificador_pago, monto_float,
                    cuit_destinatario_detectado, es_comprobante_valido,
                    mp_status_code, imagen_path, creado_por_admin_id,
                    ocr_fuente, ocr_confianza, baja_confianza_num,
                    fecha_comprobante, cvu_cbu,
                    entidad_emisora, cuit_remitente, cliente_id,
                ),
            )
        row = cur.fetchone()
    return _fila_a_dict(row)


def guardar_validacion_whatsapp(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
    numero_telefono: str,
    estado: str,
    identificador_pago: str | None,
    monto_detectado_str: str | None,
    cuit_destinatario_detectado: str | None,
    es_comprobante_valido: bool,
    mp_status_code: int | None,
    imagen_path: str | None,
    error: str | None,
    resultado_ocr: ResultadoOCR | None = None,
    cliente_id: str | None = None,
    codigo_cliente_vinculado: str | None = None,
) -> None:
    """Inserta una validación originada en un mensaje de WhatsApp.

    canal = 'WhatsApp', run_id = NULL, respuesta_id = NULL.
    No retorna la fila completa porque la respuesta al cliente va por WhatsApp,
    no por HTTP.
    """
    monto_float = _a_float_monto(monto_detectado_str)
    ocr_fuente, ocr_confianza, baja_confianza_num, fecha_comprobante, cvu_cbu, entidad_emisora, cuit_remitente = _extraer_campos_ocr(resultado_ocr)

    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO validaciones (
                id, tenant_id, canal, codigo_cliente,
                estado, estado_inicial, identificador_pago, monto_detectado,
                cuit_destinatario_detectado, es_comprobante_valido,
                mp_status_code, error, imagen_path,
                    ocr_fuente, ocr_confianza, baja_confianza_identificador,
                    fecha_comprobante, cvu_cbu_destinatario,
                    entidad_emisora, cuit_remitente, cliente_id
                ) VALUES (
                    %s::uuid, %s, 'WhatsApp', %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s::uuid
                )
                """,
                (
                    validacion_id, tenant_id, codigo_cliente_vinculado or numero_telefono,
                    estado, estado, identificador_pago, monto_float,
                    cuit_destinatario_detectado, es_comprobante_valido,
                    mp_status_code, error, imagen_path,
                    ocr_fuente, ocr_confianza, baja_confianza_num,
                    fecha_comprobante, cvu_cbu,
                    entidad_emisora, cuit_remitente, cliente_id,
                ),
            )


def obtener_metricas(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> dict:
    condiciones = ["tenant_id = %s", "eliminado_en IS NULL"]
    params: list = [tenant_id]
    if fecha_desde:
        condiciones.append("(procesado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date >= %s::date")
        params.append(fecha_desde)
    if fecha_hasta:
        condiciones.append("(procesado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date <= %s::date")
        params.append(fecha_hasta)
    where = " AND ".join(condiciones)

    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT estado, COUNT(*) FROM validaciones WHERE {where} GROUP BY estado",  # nosec B608
            params,
        )
        por_estado = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute(
            f"SELECT canal, COUNT(*) FROM validaciones WHERE {where} GROUP BY canal",  # nosec B608
            params,
        )
        por_canal = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute(
            f"SELECT entidad_emisora, COUNT(*) FROM validaciones WHERE {where} AND entidad_emisora IS NOT NULL GROUP BY entidad_emisora",  # nosec B608
            params,
        )
        por_banco = {row[0]: row[1] for row in cur.fetchall()}

    return {
        "total": sum(por_estado.values()),
        "por_estado": por_estado,
        "por_canal": por_canal,
        "por_banco": por_banco,
    }


def obtener_entidades_emisoras(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
) -> list[str]:
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT entidad_emisora
            FROM validaciones
            WHERE tenant_id = %s AND entidad_emisora IS NOT NULL AND eliminado_en IS NULL
            ORDER BY entidad_emisora
            """,
            (tenant_id,),
        )
        return [row[0] for row in cur.fetchall()]


def listar_validaciones(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    estado: str | None = None,
    canal: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    fecha_mod_desde: str | None = None,
    fecha_mod_hasta: str | None = None,
    codigo_cliente: str | None = None,
    numero_operacion: str | None = None,
    modificado_por: str | None = None,
    entidad_emisora: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    condiciones = ["v.tenant_id = %s", "v.eliminado_en IS NULL"]
    params: list = [tenant_id]
    if estado:
        condiciones.append("v.estado = %s")
        params.append(estado)
    if canal:
        condiciones.append("v.canal = %s")
        params.append(canal)
    if fecha_desde:
        condiciones.append("(v.procesado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date >= %s::date")
        params.append(fecha_desde)
    if fecha_hasta:
        condiciones.append("(v.procesado_en AT TIME ZONE 'America/Argentina/Buenos_Aires')::date <= %s::date")
        params.append(fecha_hasta)
    if fecha_mod_desde:
        condiciones.append("v.fecha_modificacion::date >= %s::date")
        params.append(fecha_mod_desde)
    if fecha_mod_hasta:
        condiciones.append("v.fecha_modificacion::date <= %s::date")
        params.append(fecha_mod_hasta)
    if codigo_cliente:
        condiciones.append("v.codigo_cliente ILIKE %s")
        params.append(f"%{codigo_cliente}%")
    if numero_operacion:
        condiciones.append("v.identificador_pago ILIKE %s")
        params.append(f"%{numero_operacion}%")
    if modificado_por:
        condiciones.append("(v.codigo_vendedor ILIKE %s OR ca.nombre ILIKE %s)")
        params.extend([f"%{modificado_por}%", f"%{modificado_por}%"])
    if entidad_emisora:
        condiciones.append("v.entidad_emisora = %s")
        params.append(entidad_emisora)
    params.extend([limit, offset])
    where = " AND ".join(condiciones)

    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT v.id::text, v.run_id::text, v.respuesta_id, v.codigo_cliente,
                   v.estado, v.identificador_pago, v.monto_detectado,
                   v.cuit_destinatario_detectado, v.es_comprobante_valido,
                   v.mp_status_code, v.error, v.procesado_en,
                   v.codigo_vendedor, v.canal, v.fecha_modificacion, v.imagen_path,
                   a.nombre AS modificado_por_nombre,
                   ca.nombre AS creado_por_nombre,
                   v.observaciones, v.estado_inicial,
                   v.entidad_emisora
            FROM validaciones v
            LEFT JOIN admins a  ON a.id  = v.modificado_por_admin_id
            LEFT JOIN admins ca ON ca.id = v.creado_por_admin_id
            WHERE {where}
            ORDER BY v.procesado_en DESC
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = cur.fetchall()
    return [_fila_a_dict(r) for r in rows]


def listar_validaciones_por_cliente(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cliente_id: str,
    limit: int = 200,
) -> list[dict]:
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.id::text, v.estado, v.identificador_pago,
                   v.monto_detectado, v.procesado_en,
                   v.canal, v.entidad_emisora, v.codigo_cliente,
                   v.imagen_path
            FROM validaciones v
            WHERE v.cliente_id = %s::uuid
              AND v.eliminado_en IS NULL
            ORDER BY v.procesado_en DESC
            LIMIT %s
            """,
            (cliente_id, limit),
        )
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "estado": row[1],
            "identificador_pago": row[2],
            "monto_detectado": row[3],
            "procesado_en": row[4].isoformat() if row[4] else None,
            "canal": row[5],
            "entidad_emisora": row[6],
            "codigo_cliente": row[7],
            "imagen_path": row[8],
        }
        for row in rows
    ]


def obtener_validacion_por_id(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
) -> dict | None:
    """Devuelve una validación por UUID y tenant, o None si no existe o pertenece a otro tenant."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.id::text, v.run_id::text, v.respuesta_id, v.codigo_cliente,
                   v.estado, v.identificador_pago, v.monto_detectado,
                   v.cuit_destinatario_detectado, v.es_comprobante_valido,
                   v.mp_status_code, v.error, v.procesado_en,
                   v.codigo_vendedor, v.canal, v.fecha_modificacion, v.imagen_path,
                   a.nombre AS modificado_por_nombre,
                   ca.nombre AS creado_por_nombre,
                   v.observaciones, v.estado_inicial,
                   v.entidad_emisora
            FROM validaciones v
            LEFT JOIN admins a  ON a.id  = v.modificado_por_admin_id
            LEFT JOIN admins ca ON ca.id = v.creado_por_admin_id
            WHERE v.id = %s::uuid AND v.tenant_id = %s AND v.eliminado_en IS NULL
            """,
            (validacion_id, tenant_id),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return _fila_a_dict(row)


def actualizar_validacion_reverificada(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
    numero_operacion: str,
    nuevo_estado: str,
    mp_status_code: int | None,
) -> dict:
    """
    Actualiza el estado de una validación tras la corrección manual del operador.
    Retorna la fila actualizada completa para que el endpoint la devuelva al frontend.

    RETURNING: en lugar de hacer UPDATE + SELECT separados, PostgreSQL devuelve
    la fila modificada en el mismo statement — más eficiente y atómico.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE validaciones
            SET estado                      = %s,
                identificador_pago  = %s,
                mp_status_code              = %s
            WHERE id = %s::uuid AND tenant_id = %s
            RETURNING id::text, run_id::text, respuesta_id, codigo_cliente,
                      estado, identificador_pago, monto_detectado,
                      cuit_destinatario_detectado, es_comprobante_valido,
                      mp_status_code, error, procesado_en,
                      codigo_vendedor, canal, fecha_modificacion, imagen_path,
                      estado_inicial
            """,
            (nuevo_estado, numero_operacion, mp_status_code, validacion_id, tenant_id),
        )
        row = cur.fetchone()

    return {
        "id": row[0], "run_id": row[1], "respuesta_id": row[2],
        "codigo_cliente": row[3], "estado": row[4],
        "identificador_pago": row[5], "monto_detectado": row[6],
        "cuit_destinatario_detectado": row[7], "es_comprobante_valido": row[8],
        "mp_status_code": row[9], "error": row[10],
        "procesado_en": row[11].isoformat() if row[11] else None,
        "codigo_vendedor": row[12], "canal": row[13],
        "fecha_modificacion": row[14].isoformat() if row[14] else None,
        "imagen_path": row[15],
        "modificado_por_nombre": None,
        "creado_por_nombre": None,
        "estado_inicial": row[16],
    }


def actualizar_validacion_manual(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
    numero_operacion: str | None,
    estado: str,
    admin_id: str,
    observaciones: str | None = None,
    actualizar_observaciones: bool = False,
) -> dict:
    """
    Actualiza una validación por decisión explícita de un admin.

    A diferencia de actualizar_validacion_reverificada (que llama a MP
    para determinar el estado), acá el admin decide directamente:
    puede cambiar el número de operación, el estado, o ambos.

    fecha_modificacion = NOW(): marca el momento de la edición manual.
    modificado_por_admin_id: quién hizo el cambio — visible en el dashboard.

    Por qué usamos una CTE (WITH ... AS):
      RETURNING no puede hacer JOIN. La CTE actualiza la fila y la expone
      como una tabla temporal, sobre la que sí podemos hacer JOIN con admins
      para traer el nombre del admin en el mismo round-trip a la DB.

    Por qué recibe estado como obligatorio aunque el caller podría no cambiarlo:
      Simplifica la SQL — siempre actualiza ambos campos.
      El router decide qué valor pasar (el nuevo si cambió, el actual si no).
    """
    set_clauses = [
        "identificador_pago = %s",
        "estado                     = %s",
        "fecha_modificacion         = NOW()",
        "modificado_por_admin_id    = %s::uuid",
    ]
    params: list = [numero_operacion, estado, admin_id]

    # observaciones: solo se actualiza si el caller lo indica explícitamente.
    # Esto permite editar número/estado sin borrar una observación previa.
    if actualizar_observaciones:
        set_clauses.append("observaciones = %s")
        params.append(observaciones or None)

    params.append(validacion_id)
    params.append(tenant_id)
    set_sql = ",\n                        ".join(set_clauses)
 
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            WITH fila_actualizada AS (
                UPDATE validaciones
                SET {set_sql}
                WHERE id = %s::uuid AND tenant_id = %s
                RETURNING *
            )
            SELECT fila_actualizada.id::text,
                   fila_actualizada.run_id::text,
                   fila_actualizada.respuesta_id,
                   fila_actualizada.codigo_cliente,
                   fila_actualizada.estado,
                   fila_actualizada.identificador_pago,
                   fila_actualizada.monto_detectado,
                   fila_actualizada.cuit_destinatario_detectado,
                   fila_actualizada.es_comprobante_valido,
                   fila_actualizada.mp_status_code,
                   fila_actualizada.error,
                   fila_actualizada.procesado_en,
                   fila_actualizada.codigo_vendedor,
                   fila_actualizada.canal,
                   fila_actualizada.fecha_modificacion,
                   fila_actualizada.imagen_path,
                   a.nombre AS modificado_por_nombre,
                   ca.nombre AS creado_por_nombre,
                   fila_actualizada.observaciones,
                   fila_actualizada.estado_inicial,
                   fila_actualizada.entidad_emisora
            FROM fila_actualizada
            LEFT JOIN admins a  ON a.id  = fila_actualizada.modificado_por_admin_id
            LEFT JOIN admins ca ON ca.id = fila_actualizada.creado_por_admin_id
            """,
            params,
        )
        row = cur.fetchone()
    return _fila_a_dict(row)


def actualizar_imagen_validacion(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
    nueva_imagen_path: str,
) -> bool:
    """
    Actualiza la imagen de una validación existente.
    Devuelve True si encontró y actualizó la fila, False si no existe o no pertenece al tenant.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE validaciones SET imagen_path = %s
            WHERE id = %s::uuid AND tenant_id = %s
            """,
            (nueva_imagen_path, validacion_id, tenant_id),
        )
        return cur.rowcount == 1


# ---------------------------------------------------------------------------
# Auditoría (siempre en contexto de operaciones sobre validaciones)
# ---------------------------------------------------------------------------

def guardar_auditoria(
    pool: psycopg2.pool.ThreadedConnectionPool,
    admin_id: str,
    validacion_id: str,
    campo: str,
    valor_anterior: str | None,
    valor_nuevo: str,
) -> None:
    """
    Registra un cambio manual en el log de auditoría.

    Por qué no usamos RETURNING acá:
      La auditoría es append-only. El llamador no necesita el ID del log —
      solo necesita saber que se guardó (o que falló con excepción).
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auditoria (admin_id, validacion_id, campo, valor_anterior, valor_nuevo)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s)
            """,
            (admin_id, validacion_id, campo, valor_anterior, valor_nuevo),
        )


def eliminar_validacion(
    pool: psycopg2.pool.ThreadedConnectionPool,
    validacion_id: str,
    tenant_id: str,
    admin_id: str,
) -> bool:
    """
    Soft-delete de una validación: marca eliminado_en y eliminado_por.
    No borra la imagen de R2 (preservada para eventual recuperación).
    Registra el evento en auditoría.
    Devuelve True si se encontró y marcó, False si no existe o ya estaba eliminada.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE validaciones
            SET eliminado_en  = NOW(),
                eliminado_por = %s::uuid
            WHERE id = %s::uuid AND tenant_id = %s AND eliminado_en IS NULL
            """,
            (admin_id, validacion_id, tenant_id),
        )
        if cur.rowcount == 0:
            return False
        cur.execute(
            """
            INSERT INTO auditoria (admin_id, validacion_id, campo, valor_anterior, valor_nuevo)
            VALUES (%s::uuid, %s::uuid, 'eliminado', NULL, 'true')
            """,
            (admin_id, validacion_id),
        )
    return True


def eliminar_datos_telefono(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    telefono: str,
) -> tuple[int, list[str]]:
    """Elimina todas las validaciones WhatsApp de un número de teléfono.

    Borra auditoria y validaciones en una sola transacción.
    Retorna (cantidad_eliminada, lista_de_image_paths) para que el caller
    pueda borrar las imágenes de R2 (best-effort, fuera de esta transacción).
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, imagen_path FROM validaciones
            WHERE tenant_id = %s AND canal = 'WhatsApp' AND codigo_cliente = %s
            """,
            (tenant_id, telefono),
        )
        filas = cur.fetchall()
        if not filas:
            return 0, []

        ids = [fila[0] for fila in filas]
        imagen_paths = [fila[1] for fila in filas if fila[1]]

        cur.execute(
            "DELETE FROM auditoria WHERE validacion_id = ANY(%s::uuid[])",
            (ids,),
        )
        cur.execute(
            "DELETE FROM validaciones WHERE id = ANY(%s::uuid[])",
            (ids,),
        )
    return len(ids), imagen_paths
