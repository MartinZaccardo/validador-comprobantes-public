"""
Tests de integración: GET /api/metricas.

Verifica estructura de respuesta, conteo correcto con datos reales en DB,
filtros de fecha, y aislamiento multi-tenant.
"""
import db.connection as db_conn
from config import config


def _get_metricas(client, token, params=None):
    return client.get(
        "/api/metricas",
        params=params,
        cookies={"access_token": token},
    )


# =============================================================================
# GET /api/metricas
# =============================================================================

def test_metricas_sin_token_devuelve_401(client):
    resp = client.get("/api/metricas")
    assert resp.status_code == 401


def test_metricas_estructura_de_respuesta(client, admin_token):
    resp = _get_metricas(client, admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert "total" in body
    assert "por_estado" in body
    assert "por_canal" in body
    assert "por_banco" in body
    assert isinstance(body["total"], int)
    assert isinstance(body["por_estado"], dict)
    assert isinstance(body["por_canal"], dict)
    assert isinstance(body["por_banco"], dict)


def test_metricas_total_es_suma_de_por_estado(client, admin_token, validacion_test):
    """total == sum(por_estado.values()). validacion_test garantiza que hay al menos una fila."""
    resp = _get_metricas(client, admin_token)
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == sum(body["por_estado"].values())


def test_metricas_cuenta_validacion_existente(client, admin_token, validacion_test):
    """Con una validación en la DB, el total debe ser >= 1."""
    resp = _get_metricas(client, admin_token)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_metricas_con_filtros_de_fecha(client, admin_token):
    """Los parámetros fecha_desde y fecha_hasta se aceptan sin error."""
    resp = _get_metricas(
        client, admin_token,
        params={"fecha_desde": "2020-01-01", "fecha_hasta": "2099-12-31"},
    )
    assert resp.status_code == 200
    assert "total" in resp.json()


def test_metricas_aislamiento_multi_tenant(client, admin_token):
    """Validaciones de otro tenant no se incluyen en el total."""
    pool = db_conn.get_pool()

    resp_antes = _get_metricas(client, admin_token)
    total_antes = resp_antes.json()["total"]

    otro_id = None
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO validaciones (tenant_id, estado, canal)
                VALUES ('otro_tenant_test', 'APROBADO', 'WhatsApp')
                RETURNING id::text
                """,
            )
            otro_id = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)

    resp_despues = _get_metricas(client, admin_token)

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            if otro_id:
                cur.execute("DELETE FROM validaciones WHERE id = %s::uuid", (otro_id,))
        conn.commit()
    finally:
        pool.putconn(conn)

    assert resp_despues.json()["total"] == total_antes
