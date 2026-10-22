"""
Queries de las tablas `clientes`, `clientes_telefonos`, `clientes_cuits`.

Todas las funciones son síncronas (psycopg2).
Llamar desde contexto async con el helper q() de db.base.
"""
import psycopg2
import psycopg2.pool

from db.base import conexion_escritura, conexion_lectura


def _cliente_a_dict(row: tuple) -> dict:
    return {
        "id": str(row[0]),
        "codigo_cliente": row[1],
        "razon_social": row[2],
        "direccion": row[3],
        "activo": row[4],
        "creado_en": row[5].isoformat() if row[5] else None,
    }


def listar_clientes(
    pool: psycopg2.pool.ThreadedConnectionPool,
    texto: str | None = None,
    solo_activos: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    conditions: list[str] = []
    params: list = []

    if solo_activos:
        conditions.append("activo = true")
    if texto:
        conditions.append("(codigo_cliente ILIKE %s OR razon_social ILIKE %s)")
        termino = f"%{texto}%"
        params.extend([termino, termino])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""  # nosec B608 — solo strings hardcodeados
    offset = (page - 1) * page_size

    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM clientes {where}", params)  # nosec B608
        total: int = cur.fetchone()[0]

        cur.execute(
            f"SELECT id::text, codigo_cliente, razon_social, direccion, activo, creado_en "  # nosec B608
            f"FROM clientes {where} ORDER BY razon_social ASC LIMIT %s OFFSET %s",
            params + [page_size, offset],
        )
        rows = cur.fetchall()

    return {"items": [_cliente_a_dict(r) for r in rows], "total": total}


def obtener_cliente_con_detalle(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cliente_id: str,
) -> dict | None:
    """Devuelve el cliente con sus teléfonos y CUITs asociados."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, codigo_cliente, razon_social, direccion, activo, creado_en
            FROM clientes
            WHERE id = %s::uuid
            """,
            (cliente_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cliente = _cliente_a_dict(row)

        cur.execute(
            "SELECT id::text, telefono FROM clientes_telefonos WHERE cliente_id = %s::uuid ORDER BY telefono",
            (cliente_id,),
        )
        cliente["telefonos"] = [{"id": r[0], "telefono": r[1]} for r in cur.fetchall()]

        cur.execute(
            "SELECT id::text, cuit FROM clientes_cuits WHERE cliente_id = %s::uuid ORDER BY cuit",
            (cliente_id,),
        )
        cliente["cuits"] = [{"id": r[0], "cuit": r[1]} for r in cur.fetchall()]

    return cliente


def buscar_clientes(
    pool: psycopg2.pool.ThreadedConnectionPool,
    q: str,
    limit: int = 10,
) -> list[dict]:
    """Búsqueda por código o razón social (ILIKE). Solo clientes activos."""
    termino = f"%{q}%"
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, codigo_cliente, razon_social, direccion, activo, creado_en
            FROM clientes
            WHERE activo = true
              AND (codigo_cliente ILIKE %s OR razon_social ILIKE %s)
            ORDER BY razon_social
            LIMIT %s
            """,
            (termino, termino, limit),
        )
        rows = cur.fetchall()
    return [_cliente_a_dict(r) for r in rows]


def obtener_cliente_por_codigo(
    pool: psycopg2.pool.ThreadedConnectionPool,
    codigo_cliente: str,
) -> dict | None:
    """Para lookup por código de cliente."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, codigo_cliente, razon_social, direccion, activo, creado_en
            FROM clientes
            WHERE codigo_cliente = %s AND activo = true
            """,
            (codigo_cliente,),
        )
        row = cur.fetchone()
    return _cliente_a_dict(row) if row else None


def obtener_cliente_por_telefono(
    pool: psycopg2.pool.ThreadedConnectionPool,
    telefono: str,
) -> dict | None:
    """Para lookup desde el canal WhatsApp."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id::text, c.codigo_cliente, c.razon_social, c.direccion, c.activo, c.creado_en
            FROM clientes c
            JOIN clientes_telefonos ct ON ct.cliente_id = c.id
            WHERE ct.telefono = %s AND c.activo = true
            """,
            (telefono,),
        )
        row = cur.fetchone()
    return _cliente_a_dict(row) if row else None


def obtener_cliente_por_cuit(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cuit: str,
) -> dict | None:
    """Para auto-vinculación cuando el OCR extrae cuit_remitente."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id::text, c.codigo_cliente, c.razon_social, c.direccion, c.activo, c.creado_en
            FROM clientes c
            JOIN clientes_cuits cc ON cc.cliente_id = c.id
            WHERE cc.cuit = %s AND c.activo = true
            """,
            (cuit,),
        )
        row = cur.fetchone()
    return _cliente_a_dict(row) if row else None


def resolver_cliente_para_vinculacion(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cuit_remitente: str | None,
    telefono: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Retorna (cliente_id, codigo_cliente) para auto-vincular un comprobante.
    Intenta por CUIT primero; si no matchea y hay teléfono, intenta por teléfono.
    Retorna (None, None) si no hay match en ningún caso.
    """
    if cuit_remitente:
        cliente = obtener_cliente_por_cuit(pool, cuit_remitente)
        if cliente:
            return cliente["id"], cliente["codigo_cliente"]
    if telefono:
        cliente = obtener_cliente_por_telefono(pool, telefono)
        if cliente:
            return cliente["id"], cliente["codigo_cliente"]
    return None, None


def crear_cliente(
    pool: psycopg2.pool.ThreadedConnectionPool,
    codigo_cliente: str,
    razon_social: str,
    direccion: str | None = None,
) -> str:
    """
    Inserta un cliente. Retorna su UUID como string.
    Lanza psycopg2.errors.UniqueViolation si el codigo_cliente ya existe.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clientes (codigo_cliente, razon_social, direccion)
            VALUES (%s, %s, %s)
            RETURNING id::text
            """,
            (codigo_cliente, razon_social, direccion),
        )
        result = cur.fetchone()
    return result[0]


def actualizar_cliente(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cliente_id: str,
    razon_social: str | None,
    direccion: str | None,
    activo: bool | None,
) -> dict | None:
    """
    Actualiza los campos que no son None. Devuelve la fila actualizada, o None si no existe.

    El f-string solo concatena nombres de columna hardcodeados ("razon_social = %s", etc.).
    Los valores del usuario siempre van en `valores` como parámetros %s — sin riesgo de inyección.
    """
    campos: list[str] = []
    valores: list = []

    if razon_social is not None:
        campos.append("razon_social = %s")
        valores.append(razon_social)
    if direccion is not None:
        campos.append("direccion = %s")
        valores.append(direccion)
    if activo is not None:
        campos.append("activo = %s")
        valores.append(activo)

    if not campos:
        return None

    valores.append(cliente_id)
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        set_clause = ", ".join(campos)
        sql = (
            f"UPDATE clientes SET {set_clause} "  # nosec B608 — campos son strings hardcodeados ("col = %s"); valores van en %s
            "WHERE id = %s::uuid "
            "RETURNING id::text, codigo_cliente, razon_social, direccion, activo, creado_en"
        )
        cur.execute(sql, valores)
        row = cur.fetchone()
    return _cliente_a_dict(row) if row else None


def agregar_telefono(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cliente_id: str,
    telefono: str,
) -> dict:
    """
    Asocia un teléfono al cliente. Retorna el registro creado.
    Lanza UniqueViolation si el teléfono ya está asociado a otro cliente.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clientes_telefonos (cliente_id, telefono)
            VALUES (%s::uuid, %s)
            RETURNING id::text, telefono
            """,
            (cliente_id, telefono),
        )
        row = cur.fetchone()
    return {"id": row[0], "telefono": row[1]}


def eliminar_telefono(
    pool: psycopg2.pool.ThreadedConnectionPool,
    telefono_id: str,
    cliente_id: str,
) -> bool:
    """Elimina un teléfono. Retorna True si existía, False si no."""
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM clientes_telefonos
            WHERE id = %s::uuid AND cliente_id = %s::uuid
            """,
            (telefono_id, cliente_id),
        )
        return cur.rowcount > 0


def agregar_cuit(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cliente_id: str,
    cuit: str,
) -> dict:
    """
    Asocia un CUIT al cliente. Retorna el registro creado.
    Lanza UniqueViolation si el CUIT ya está asociado a otro cliente.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clientes_cuits (cliente_id, cuit)
            VALUES (%s::uuid, %s)
            RETURNING id::text, cuit
            """,
            (cliente_id, cuit),
        )
        row = cur.fetchone()
    return {"id": row[0], "cuit": row[1]}


def eliminar_cuit(
    pool: psycopg2.pool.ThreadedConnectionPool,
    cuit_id: str,
    cliente_id: str,
) -> bool:
    """Elimina un CUIT. Retorna True si existía, False si no."""
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM clientes_cuits
            WHERE id = %s::uuid AND cliente_id = %s::uuid
            """,
            (cuit_id, cliente_id),
        )
        return cur.rowcount > 0


def preview_importacion(
    pool: psycopg2.pool.ThreadedConnectionPool,
    clientes_csv: list[dict],
) -> dict:
    """
    Calcula cuántos clientes serían nuevos, cuántos cambian y cuántos son idénticos.
    Una sola query con ANY(%s) — O(1) round-trips sin importar el tamaño del CSV.
    La comparación campo a campo se hace en memoria con los datos ya traídos.
    """
    if not clientes_csv:
        return {"nuevos": 0, "con_cambios": 0, "sin_cambios": 0}

    csv_map = {c["codigo_cliente"]: c for c in clientes_csv}
    codigos = list(csv_map.keys())

    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT codigo_cliente, razon_social, direccion FROM clientes WHERE codigo_cliente = ANY(%s)",
            (codigos,),
        )
        existentes = {
            row[0]: {"razon_social": row[1], "direccion": row[2], "telefonos": set(), "cuits": set()}
            for row in cur.fetchall()
        }

        if existentes:
            codigos_existentes = list(existentes.keys())
            cur.execute(
                """
                SELECT c.codigo_cliente, ct.telefono
                FROM clientes_telefonos ct
                JOIN clientes c ON c.id = ct.cliente_id
                WHERE c.codigo_cliente = ANY(%s)
                """,
                (codigos_existentes,),
            )
            for codigo, telefono in cur.fetchall():
                existentes[codigo]["telefonos"].add(telefono)

            cur.execute(
                """
                SELECT c.codigo_cliente, cc.cuit
                FROM clientes_cuits cc
                JOIN clientes c ON c.id = cc.cliente_id
                WHERE c.codigo_cliente = ANY(%s)
                """,
                (codigos_existentes,),
            )
            for codigo, cuit in cur.fetchall():
                existentes[codigo]["cuits"].add(cuit)

    nuevos = len(set(codigos) - set(existentes))
    con_cambios = 0
    sin_cambios = 0

    for codigo, datos_db in existentes.items():
        datos_csv = csv_map[codigo]
        telefonos_nuevos = set(datos_csv.get("telefonos", [])) - datos_db["telefonos"]
        cuits_nuevos = set(datos_csv.get("cuits", [])) - datos_db["cuits"]
        hay_cambio = (
            datos_db["razon_social"] != datos_csv["razon_social"]
            or datos_db["direccion"] != datos_csv.get("direccion")
            or bool(telefonos_nuevos)
            or bool(cuits_nuevos)
        )
        if hay_cambio:
            con_cambios += 1
        else:
            sin_cambios += 1

    return {"nuevos": nuevos, "con_cambios": con_cambios, "sin_cambios": sin_cambios}


def importar_clientes(
    pool: psycopg2.pool.ThreadedConnectionPool,
    clientes: list[dict],
) -> dict:
    """
    Importa una lista de clientes desde CSV.
    Cada dict tiene: codigo_cliente, razon_social, direccion, telefonos, cuits.
    Si el codigo_cliente ya existe lo saltea (no falla).
    Retorna contadores: insertados, salteados, errores.

    Formato de columnas basado en CSV de prueba — puede ajustarse al CSV oficial del cliente.
    Ver _parsear_csv() en routers/clientes.py para el mapeo de columnas.
    """
    insertados = 0
    actualizados = 0
    errores: list[str] = []

    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        for cliente in clientes:
            try:
                cur.execute(
                    """
                    INSERT INTO clientes (codigo_cliente, razon_social, direccion)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (codigo_cliente) DO UPDATE
                        SET razon_social = EXCLUDED.razon_social,
                            direccion    = EXCLUDED.direccion
                    WHERE clientes.razon_social IS DISTINCT FROM EXCLUDED.razon_social
                       OR clientes.direccion    IS DISTINCT FROM EXCLUDED.direccion
                    RETURNING id::text, (xmax = 0) AS es_nuevo
                    """,
                    (cliente["codigo_cliente"], cliente["razon_social"], cliente.get("direccion")),
                )
                row = cur.fetchone()
                if row is None:
                    # Sin cambios en razon_social ni direccion — buscar id para telefonos/CUITs
                    cur.execute(
                        "SELECT id::text FROM clientes WHERE codigo_cliente = %s",
                        (cliente["codigo_cliente"],),
                    )
                    id_row = cur.fetchone()
                    cliente_id = id_row[0] if id_row else None
                elif row[1]:  # xmax = 0 → fila nueva
                    cliente_id = row[0]
                    insertados += 1
                else:
                    cliente_id = row[0]
                    actualizados += 1

                # Teléfonos y CUITs del CSV se agregan si no existen — nunca se borran los existentes
                if cliente_id:
                    for telefono in cliente.get("telefonos", []):
                        cur.execute(
                            """
                            INSERT INTO clientes_telefonos (cliente_id, telefono)
                            VALUES (%s::uuid, %s)
                            ON CONFLICT (telefono) DO NOTHING
                            """,
                            (cliente_id, telefono),
                        )
                    for cuit in cliente.get("cuits", []):
                        cur.execute(
                            """
                            INSERT INTO clientes_cuits (cliente_id, cuit)
                            VALUES (%s::uuid, %s)
                            ON CONFLICT (cuit) DO NOTHING
                            """,
                            (cliente_id, cuit),
                        )
            except psycopg2.Error as exc:
                errores.append(f"{cliente.get('codigo_cliente', '?')}: {exc}")

    return {"insertados": insertados, "actualizados": actualizados, "errores": errores}


def exportar_clientes(
    pool: psycopg2.pool.ThreadedConnectionPool,
) -> list[dict]:
    """
    Devuelve clientes activos con teléfonos y CUITs agregados como strings separados por ';'.
    Formato idéntico al CSV de importación para que export → editar → reimportar funcione sin fricción.
    """
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                c.codigo_cliente,
                c.razon_social,
                COALESCE(c.direccion, '') AS direccion,
                COALESCE(STRING_AGG(DISTINCT ct.telefono, ';' ORDER BY ct.telefono), '') AS telefonos,
                COALESCE(STRING_AGG(DISTINCT cc.cuit,     ';' ORDER BY cc.cuit),     '') AS cuits
            FROM clientes c
            LEFT JOIN clientes_telefonos ct ON ct.cliente_id = c.id
            LEFT JOIN clientes_cuits      cc ON cc.cliente_id = c.id
            WHERE c.activo = TRUE
            GROUP BY c.id, c.codigo_cliente, c.razon_social, c.direccion
            ORDER BY c.razon_social ASC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "codigo_cliente": r[0],
            "razon_social": r[1],
            "direccion": r[2],
            "telefonos": r[3],
            "cuits": r[4],
        }
        for r in rows
    ]


def listar_clientes_sin_actividad(
    pool: psycopg2.pool.ThreadedConnectionPool,
    dias: int = 7,
) -> list[dict]:
    """Devuelve clientes activos que alguna vez enviaron pero hace más de `dias` días."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id::text, c.codigo_cliente, c.razon_social,
                   MAX(v.procesado_en) AS ultimo_comprobante
            FROM clientes c
            LEFT JOIN validaciones v
                ON v.codigo_cliente = c.codigo_cliente AND v.eliminado_en IS NULL
            WHERE c.activo = TRUE
            GROUP BY c.id, c.codigo_cliente, c.razon_social
            HAVING MAX(v.procesado_en) IS NOT NULL
               AND MAX(v.procesado_en) < NOW() - (%s * INTERVAL '1 day')
            ORDER BY ultimo_comprobante ASC
            """,
            (dias,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "codigo_cliente": r[1],
            "razon_social": r[2],
            "ultimo_comprobante": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]


def listar_clientes_sin_comprobantes(
    pool: psycopg2.pool.ThreadedConnectionPool,
) -> list[dict]:
    """Devuelve clientes activos que nunca enviaron ningún comprobante."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id::text, c.codigo_cliente, c.razon_social,
                   NULL AS ultimo_comprobante
            FROM clientes c
            LEFT JOIN validaciones v
                ON v.codigo_cliente = c.codigo_cliente AND v.eliminado_en IS NULL
            WHERE c.activo = TRUE
            GROUP BY c.id, c.codigo_cliente, c.razon_social
            HAVING MAX(v.procesado_en) IS NULL
            ORDER BY c.razon_social ASC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "codigo_cliente": r[1],
            "razon_social": r[2],
            "ultimo_comprobante": None,
        }
        for r in rows
    ]
