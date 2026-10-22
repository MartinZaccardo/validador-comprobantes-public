"""
Tests de integración: GET y PATCH /api/validaciones y GET /api/validaciones/{id}.

Cada test de PATCH recibe una validación fresca (fixture 'validacion_test').
Los tests de GET crean sus propios datos cuando necesitan estado/canal específico,
y los limpian en un bloque finally — sin depender del estado previo de la DB.
"""
import uuid

import db.connection as db_conn
from config import config

# ---------------------------------------------------------------------------
# Helpers de DB directa (para tests de GET que necesitan datos específicos)
# ---------------------------------------------------------------------------

def _insertar_validacion(
    tenant_id: str | None = None,
    estado: str = "IMAGEN_INVALIDA",
    canal: str = "MANUAL",
    codigo_cliente: str | None = None,
    identificador_pago: str | None = None,
) -> str:
    """Inserta una validación mínima y devuelve su id. Limpiar con _borrar_validacion."""
    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO validaciones (tenant_id, estado, canal, codigo_cliente, identificador_pago)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (tenant_id or config.tenant_id, estado, canal, codigo_cliente, identificador_pago),
            )
            validacion_id = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)
    return validacion_id


def _borrar_validacion(validacion_id: str) -> None:
    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auditoria   WHERE validacion_id = %s::uuid", (validacion_id,))
            cur.execute("DELETE FROM validaciones WHERE id           = %s::uuid", (validacion_id,))
        conn.commit()
    finally:
        pool.putconn(conn)


def _patch(client, admin_token, validacion_id, body):
    """Helper para no repetir headers en cada llamada."""
    return client.patch(
        f"/api/validaciones/{validacion_id}",
        json=body,
        cookies={"access_token": admin_token},
    )


# =============================================================================
# Casos exitosos
# =============================================================================

def test_patch_cambia_estado(client, admin_token, validacion_test):
    resp = _patch(client, admin_token, validacion_test, {"estado": "APROBADO"})

    assert resp.status_code == 200
    assert resp.json()["estado"] == "APROBADO"


def test_patch_cambia_numero_operacion(client, admin_token, validacion_test):
    resp = _patch(client, admin_token, validacion_test, {"numero_operacion": "98765432"})

    assert resp.status_code == 200
    assert resp.json()["identificador_pago"] == "98765432"


def test_patch_cambia_ambos_campos(client, admin_token, validacion_test):
    resp = _patch(client, admin_token, validacion_test, {
        "estado": "APROBADO",
        "numero_operacion": "11223344",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "APROBADO"
    assert body["identificador_pago"] == "11223344"


def test_patch_setea_fecha_modificacion(client, admin_token, validacion_test):
    """
    La edición manual siempre actualiza fecha_modificacion.
    Verificamos que deja de ser None después del PATCH.
    """
    resp = _patch(client, admin_token, validacion_test, {"estado": "APROBADO"})

    assert resp.status_code == 200
    assert resp.json()["fecha_modificacion"] is not None


def test_patch_devuelve_fila_completa(client, admin_token, validacion_test):
    """La respuesta contiene todos los campos de la validación, incluido modificado_por_nombre."""
    resp = _patch(client, admin_token, validacion_test, {"estado": "DUPLICADO"})

    body = resp.json()
    campos_esperados = [
        "id", "estado", "canal", "codigo_cliente",
        "identificador_pago", "monto_detectado",
        "procesado_en", "fecha_modificacion",
        "modificado_por_nombre",
    ]
    for campo in campos_esperados:
        assert campo in body, f"Falta el campo '{campo}' en la respuesta"


def test_patch_devuelve_nombre_del_admin(client, admin_token, admin_test, validacion_test):
    """
    Después de una edición manual, modificado_por_nombre debe ser el nombre
    del admin autenticado — no None.

    Verifica que el CTE (WITH fila_actualizada ... LEFT JOIN admins) funciona
    correctamente: la query une la fila actualizada con la tabla admins para
    traer el nombre en el mismo round-trip, sin un SELECT separado.
    """
    resp = _patch(client, admin_token, validacion_test, {"estado": "APROBADO"})

    assert resp.status_code == 200
    assert resp.json()["modificado_por_nombre"] == admin_test["nombre"]


# =============================================================================
# Auditoría
# =============================================================================

def test_patch_registra_auditoria_de_estado(client, admin_token, validacion_test):
    """
    Cuando el estado cambia, debe quedar una fila en la tabla auditoria
    con campo='estado', valor_anterior='IMAGEN_INVALIDA', valor_nuevo='APROBADO'.
    """
    _patch(client, admin_token, validacion_test, {"estado": "APROBADO"})

    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT campo, valor_anterior, valor_nuevo
                FROM auditoria
                WHERE validacion_id = %s::uuid
                ORDER BY timestamp DESC
                """,
                (validacion_test,),
            )
            filas = cur.fetchall()
    finally:
        pool.putconn(conn)

    assert len(filas) >= 1
    campos = {f[0]: {"anterior": f[1], "nuevo": f[2]} for f in filas}
    assert "estado" in campos
    assert campos["estado"]["anterior"] == "IMAGEN_INVALIDA"
    assert campos["estado"]["nuevo"]    == "APROBADO"


def test_patch_sin_cambio_no_genera_auditoria(client, admin_token, validacion_test):
    """
    Si el admin envía el mismo estado que ya tiene la validación,
    no debe generarse ninguna fila de auditoría.
    """
    # La validación ya tiene estado IMAGEN_INVALIDA (creada por el fixture)
    _patch(client, admin_token, validacion_test, {"estado": "IMAGEN_INVALIDA"})

    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM auditoria WHERE validacion_id = %s::uuid",
                (validacion_test,),
            )
            count = cur.fetchone()[0]
    finally:
        pool.putconn(conn)

    assert count == 0


# =============================================================================
# Casos de error
# =============================================================================

def test_patch_sin_jwt_devuelve_401(client, validacion_test):
    resp = client.patch(
        f"/api/validaciones/{validacion_test}",
        json={"estado": "APROBADO"},
    )
    assert resp.status_code == 401


def test_patch_estado_invalido_devuelve_400(client, admin_token, validacion_test):
    resp = _patch(client, admin_token, validacion_test, {"estado": "ESTADO_INVENTADO"})
    assert resp.status_code == 400


def test_patch_sin_ningún_campo_devuelve_422(client, admin_token, validacion_test):
    """Pydantic valida que al menos un campo esté presente."""
    resp = _patch(client, admin_token, validacion_test, {})
    assert resp.status_code == 422


def test_patch_numero_operacion_vacio_devuelve_422(client, admin_token, validacion_test):
    """El número de operación no puede ser una cadena vacía."""
    resp = _patch(client, admin_token, validacion_test, {"numero_operacion": "   "})
    assert resp.status_code == 422


def test_patch_numero_operacion_no_numerico_devuelve_422(client, admin_token, validacion_test):
    """Solo dígitos son válidos — previene cadenas que irían interpoladas en URLs externas."""
    resp = _patch(client, admin_token, validacion_test, {"numero_operacion": "abc123"})
    assert resp.status_code == 422


def test_patch_numero_operacion_demasiado_largo_devuelve_422(client, admin_token, validacion_test):
    """Los IDs de MP son hasta ~18 dígitos — rechazar cadenas excesivamente largas."""
    resp = _patch(client, admin_token, validacion_test, {"numero_operacion": "1" * 21})
    assert resp.status_code == 422


def test_patch_validacion_inexistente_devuelve_404(client, admin_token):
    resp = _patch(client, admin_token, str(uuid.uuid4()), {"estado": "APROBADO"})
    assert resp.status_code == 404


def test_patch_id_no_uuid_devuelve_404(client, admin_token):
    """Un ID con formato inválido se trata como no encontrado."""
    resp = _patch(client, admin_token, "esto-no-es-un-uuid", {"estado": "APROBADO"})
    assert resp.status_code == 404


# =============================================================================
# Re-verificación (rate limit + validación)
# =============================================================================

def test_reverificar_uuid_inexistente_devuelve_404(client, admin_token):
    """
    El endpoint responde dentro del límite (no bloquea el primer request)
    y el parámetro request: Request requerido por slowapi no rompió la firma.
    """
    resp = client.post(
        f"/api/validaciones/{uuid.uuid4()}/reverificar",
        json={"numero_operacion": "123456789"},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


# =============================================================================
# Observaciones (MVP8)
# =============================================================================

def test_patch_observaciones_campo_presente_en_respuesta(client, admin_token, validacion_test):
    """El campo observaciones siempre está en la respuesta, aunque sea None."""
    resp = _patch(client, admin_token, validacion_test, {"estado": "APROBADO"})

    assert resp.status_code == 200
    assert "observaciones" in resp.json()


def test_patch_guarda_observaciones(client, admin_token, validacion_test):
    resp = _patch(client, admin_token, validacion_test, {"observaciones": "Pago confirmado por el cliente."})

    assert resp.status_code == 200
    assert resp.json()["observaciones"] == "Pago confirmado por el cliente."


def test_patch_observaciones_como_unico_campo(client, admin_token, validacion_test):
    """observaciones como único campo en el body es válido."""
    resp = _patch(client, admin_token, validacion_test, {"observaciones": "Solo una observación."})

    assert resp.status_code == 200
    assert resp.json()["observaciones"] == "Solo una observación."


def test_patch_borra_observaciones_con_string_vacio(client, admin_token, validacion_test):
    """
    Enviar observaciones='' limpia el campo — queda NULL en DB.

    Por qué None y no "":
      La query hace `observaciones or None`, así que "" se convierte en NULL
      antes de guardarse. La respuesta devuelve None, no una cadena vacía.
    """
    _patch(client, admin_token, validacion_test, {"observaciones": "Texto previo"})
    resp = _patch(client, admin_token, validacion_test, {"observaciones": ""})

    assert resp.status_code == 200
    assert resp.json()["observaciones"] is None


def test_patch_observaciones_sin_tocar_con_none_en_body(client, admin_token, validacion_test):
    """
    Si observaciones no viene en el body (None implícito), el campo no se toca.
    Cambiar el estado no debe borrar observaciones ya guardadas.
    """
    _patch(client, admin_token, validacion_test, {"observaciones": "Nota que debe sobrevivir."})
    resp = _patch(client, admin_token, validacion_test, {"estado": "APROBADO"})

    assert resp.status_code == 200
    assert resp.json()["observaciones"] == "Nota que debe sobrevivir."


def test_patch_observaciones_registra_auditoria(client, admin_token, validacion_test):
    """Cambiar observaciones genera una fila de auditoría con campo='observaciones'."""
    _patch(client, admin_token, validacion_test, {"observaciones": "Primera nota."})
    _patch(client, admin_token, validacion_test, {"observaciones": "Nota actualizada."})

    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT campo, valor_nuevo
                FROM auditoria
                WHERE validacion_id = %s::uuid AND campo = 'observaciones'
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (validacion_test,),
            )
            fila = cur.fetchone()
    finally:
        pool.putconn(conn)

    assert fila is not None
    assert fila[0] == "observaciones"
    assert fila[1] == "Nota actualizada."


# =============================================================================
# GET /api/validaciones  — listado con filtros
# =============================================================================

def test_listar_sin_jwt_devuelve_401(client):
    resp = client.get("/api/validaciones")
    assert resp.status_code == 401


def test_listar_estado_invalido_devuelve_400(client, admin_token):
    resp = client.get(
        "/api/validaciones?estado=INEXISTENTE",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 400


def test_listar_canal_invalido_devuelve_400(client, admin_token):
    resp = client.get(
        "/api/validaciones?canal=FOOBAR",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 400


def test_listar_incluye_validacion_del_tenant(client, admin_token, validacion_test):
    """Una validación del tenant aparece en el listado sin filtros."""
    resp = client.get(
        "/api/validaciones",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200
    ids = [v["id"] for v in resp.json()]
    assert validacion_test in ids


def test_listar_filtro_por_estado(client, admin_token):
    """Con ?estado=APROBADO solo devuelve validaciones con ese estado."""
    vid = _insertar_validacion(estado="APROBADO")
    try:
        resp = client.get(
            "/api/validaciones?estado=APROBADO",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert any(v["id"] == vid for v in datos)
        assert all(v["estado"] == "APROBADO" for v in datos)
    finally:
        _borrar_validacion(vid)


def test_listar_filtro_por_canal(client, admin_token):
    """Con ?canal=WhatsApp solo devuelve validaciones con ese canal."""
    vid = _insertar_validacion(canal="WhatsApp")
    try:
        resp = client.get(
            "/api/validaciones?canal=WhatsApp",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert any(v["id"] == vid for v in datos)
        assert all(v["canal"] == "WhatsApp" for v in datos)
    finally:
        _borrar_validacion(vid)


def test_listar_filtro_por_numero_operacion(client, admin_token):
    """Con ?numero_operacion=<substring> solo devuelve validaciones que lo contienen."""
    vid = _insertar_validacion(identificador_pago="123456789012")
    try:
        resp = client.get(
            "/api/validaciones?numero_operacion=456789",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert any(v["id"] == vid for v in datos)
        assert all("456789" in (v["identificador_pago"] or "") for v in datos)
    finally:
        _borrar_validacion(vid)


def test_listar_filtro_por_codigo_cliente(client, admin_token):
    """
    El filtro codigo_cliente usa ILIKE — es parcial y case-insensitive.
    Buscar 'testcli999' debe encontrar una validación con 'TESTCLI999'.
    """
    vid = _insertar_validacion(codigo_cliente="TESTCLI999")
    try:
        resp = client.get(
            "/api/validaciones?codigo_cliente=testcli999",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 200
        ids = [v["id"] for v in resp.json()]
        assert vid in ids
    finally:
        _borrar_validacion(vid)


def test_listar_aislamiento_multi_tenant(client, admin_token):
    """
    Una validación de otro tenant NO aparece en el listado del tenant actual.

    Este es el test más importante del módulo: verifica que listar_validaciones
    filtra siempre por tenant_id y no expone datos de otros tenants.
    """
    vid_otro = _insertar_validacion(tenant_id="otro_tenant")
    try:
        resp = client.get(
            "/api/validaciones",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 200
        ids = [v["id"] for v in resp.json()]
        assert vid_otro not in ids
    finally:
        _borrar_validacion(vid_otro)


# =============================================================================
# GET /api/validaciones/{id}  — detalle
# =============================================================================

def test_obtener_sin_jwt_devuelve_401(client, validacion_test):
    resp = client.get(f"/api/validaciones/{validacion_test}")
    assert resp.status_code == 401


def test_obtener_uuid_invalido_devuelve_404(client, admin_token):
    """Un id que no tiene formato UUID se trata como no encontrado."""
    resp = client.get(
        "/api/validaciones/esto-no-es-un-uuid",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


def test_obtener_inexistente_devuelve_404(client, admin_token):
    resp = client.get(
        f"/api/validaciones/{uuid.uuid4()}",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


def test_obtener_devuelve_datos_completos(client, admin_token, validacion_test):
    """El detalle contiene todos los campos esperados por el frontend."""
    resp = client.get(
        f"/api/validaciones/{validacion_test}",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == validacion_test
    for campo in ("estado", "canal", "codigo_cliente", "procesado_en",
                  "modificado_por_nombre", "observaciones", "estado_inicial"):
        assert campo in body, f"Falta el campo '{campo}' en la respuesta"


def test_obtener_otro_tenant_devuelve_404(client, admin_token):
    """
    Una validación de otro tenant devuelve 404 — no debe ser visible
    para un admin de un tenant diferente.

    Verifica que obtener_validacion_por_id filtra por tenant_id y no
    solo por id.
    """
    vid_otro = _insertar_validacion(tenant_id="otro_tenant")
    try:
        resp = client.get(
            f"/api/validaciones/{vid_otro}",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 404
    finally:
        _borrar_validacion(vid_otro)


# =============================================================================
# Re-verificación
# =============================================================================

def test_reverificar_sin_jwt_devuelve_401(client, validacion_test):
    resp = client.post(
        f"/api/validaciones/{validacion_test}/reverificar",
        json={"numero_operacion": "123456789"},
    )
    assert resp.status_code == 401


def test_reverificar_uuid_invalido_devuelve_404(client, admin_token):
    resp = client.post(
        "/api/validaciones/no-es-uuid/reverificar",
        json={"numero_operacion": "123456789"},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


def test_reverificar_estado_no_reverificable_devuelve_400(client, admin_token):
    """
    Un estado APROBADO no está en _ESTADOS_REVERIFICABLES — debe responder 400
    con un mensaje que explique qué estados sí son válidos.
    """
    vid = _insertar_validacion(estado="APROBADO")
    try:
        resp = client.post(
            f"/api/validaciones/{vid}/reverificar",
            json={"numero_operacion": "123456789"},
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 400
        assert "Revisión manual" in resp.json()["detail"]
    finally:
        _borrar_validacion(vid)


def test_reverificar_aislamiento_multi_tenant(client, admin_token):
    """Tenant A no puede reverificar una validación de tenant B."""
    vid_otro = _insertar_validacion(tenant_id="otro_tenant_rev", estado="REVISION_MANUAL")
    try:
        resp = client.post(
            f"/api/validaciones/{vid_otro}/reverificar",
            json={"numero_operacion": "123456789"},
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 404
    finally:
        _borrar_validacion(vid_otro)


# =============================================================================
# Eliminación (DELETE /api/validaciones/{id})
# =============================================================================

def test_eliminar_sin_jwt_devuelve_401(client, validacion_test):
    resp = client.delete(f"/api/validaciones/{validacion_test}")
    assert resp.status_code == 401


def test_eliminar_uuid_invalido_devuelve_404(client, admin_token):
    resp = client.delete(
        "/api/validaciones/no-es-uuid",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


def test_eliminar_inexistente_devuelve_404(client, admin_token):
    resp = client.delete(
        f"/api/validaciones/{uuid.uuid4()}",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


def test_eliminar_devuelve_204(client, admin_token, validacion_test):
    resp = client.delete(
        f"/api/validaciones/{validacion_test}",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 204


def test_eliminar_borra_la_validacion_de_db(client, admin_token, validacion_test):
    client.delete(
        f"/api/validaciones/{validacion_test}",
        cookies={"access_token": admin_token},
    )
    resp = client.get(
        f"/api/validaciones/{validacion_test}",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 404


def test_eliminar_aislamiento_multi_tenant(client, admin_token):
    """La validación de otro tenant devuelve 404 — no se puede borrar cross-tenant."""
    vid_otro = _insertar_validacion(tenant_id="otro_tenant_delete")
    try:
        resp = client.delete(
            f"/api/validaciones/{vid_otro}",
            cookies={"access_token": admin_token},
        )
        assert resp.status_code == 404
    finally:
        _borrar_validacion(vid_otro)
