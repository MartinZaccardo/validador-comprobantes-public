"""
Tests de integración: GET /api/admins y PATCH /api/admins/{id}/activo.

Ambos endpoints requieren rol superadmin — un admin regular recibe 403.
"""
import uuid

import db.connection as db_conn
from services.auth_service import hash_password


def _listar(client, token):
    return client.get(
        "/api/admins",
        cookies={"access_token": token},
    )


def _toggle(client, token, admin_id, activo):
    return client.patch(
        f"/api/admins/{admin_id}/activo",
        json={"activo": activo},
        cookies={"access_token": token},
    )


# =============================================================================
# GET /api/admins
# =============================================================================

def test_listar_admins_superadmin_ve_lista(client, superadmin_token, superadmin_test):
    resp = _listar(client, superadmin_token)

    assert resp.status_code == 200
    admins = resp.json()
    assert isinstance(admins, list)
    assert len(admins) >= 1


def test_listar_admins_campos_esperados(client, superadmin_token):
    resp = _listar(client, superadmin_token)
    assert resp.status_code == 200

    for admin in resp.json():
        for campo in ("id", "nombre", "email", "activo", "creado_en"):
            assert campo in admin, f"Falta el campo '{campo}'"


def test_listar_admins_superadmin_se_ve_a_si_mismo(client, superadmin_token, superadmin_test):
    resp = _listar(client, superadmin_token)
    assert resp.status_code == 200

    ids = [a["id"] for a in resp.json()]
    assert superadmin_test["id"] in ids


def test_listar_admins_admin_regular_devuelve_403(client, admin_token):
    resp = _listar(client, admin_token)
    assert resp.status_code == 403


def test_listar_admins_sin_token_devuelve_401(client):
    resp = client.get("/api/admins")
    assert resp.status_code == 401


def test_listar_admins_aislamiento_multi_tenant(client, superadmin_token):
    """El endpoint no retorna admins de otro tenant."""
    pool = db_conn.get_pool()
    otro_email = "admin_otro_tenant_test@validador-tests.com"
    otro_id = None

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admins (tenant_id, email, nombre, password_hash)
                VALUES ('otro_tenant_test', %s, 'Admin Otro Tenant', %s)
                RETURNING id::text
                """,
                (otro_email, hash_password("Test_123!")),
            )
            otro_id = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)

    resp = _listar(client, superadmin_token)

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            if otro_id:
                cur.execute("DELETE FROM admins WHERE id = %s::uuid", (otro_id,))
        conn.commit()
    finally:
        pool.putconn(conn)

    assert resp.status_code == 200
    ids_retornados = [a["id"] for a in resp.json()]
    assert otro_id not in ids_retornados


# =============================================================================
# PATCH /api/admins/{id}/activo
# =============================================================================

def test_toggle_desactiva_admin(client, superadmin_token, admin_para_toggle):
    resp = _toggle(client, superadmin_token, admin_para_toggle["id"], False)

    assert resp.status_code == 200
    assert resp.json()["activo"] is False


def test_toggle_reactiva_admin(client, superadmin_token, admin_para_toggle):
    _toggle(client, superadmin_token, admin_para_toggle["id"], False)
    resp = _toggle(client, superadmin_token, admin_para_toggle["id"], True)

    assert resp.status_code == 200
    assert resp.json()["activo"] is True


def test_toggle_respuesta_incluye_campos_esperados(client, superadmin_token, admin_para_toggle):
    resp = _toggle(client, superadmin_token, admin_para_toggle["id"], False)
    assert resp.status_code == 200

    body = resp.json()
    for campo in ("id", "nombre", "email", "activo", "creado_en"):
        assert campo in body, f"Falta el campo '{campo}'"


def test_toggle_superadmin_no_puede_desactivarse_a_si_mismo(client, superadmin_token, superadmin_test):
    resp = _toggle(client, superadmin_token, superadmin_test["id"], False)

    assert resp.status_code == 400
    assert "vos mismo" in resp.json()["detail"]


def test_toggle_admin_regular_devuelve_403(client, admin_token, admin_para_toggle):
    resp = _toggle(client, admin_token, admin_para_toggle["id"], False)
    assert resp.status_code == 403


def test_toggle_sin_token_devuelve_401(client, admin_para_toggle):
    resp = client.patch(
        f"/api/admins/{admin_para_toggle['id']}/activo",
        json={"activo": False},
    )
    assert resp.status_code == 401


def test_toggle_admin_inexistente_devuelve_404(client, superadmin_token):
    resp = _toggle(client, superadmin_token, str(uuid.uuid4()), False)
    assert resp.status_code == 404


# =============================================================================
# DELETE /api/admins/datos-usuario
# =============================================================================

def test_eliminar_datos_usuario_sin_jwt_devuelve_401(client):
    resp = client.delete(
        "/api/admins/datos-usuario",
        params={"telefono": "5491112345678"},
    )
    assert resp.status_code == 401


def test_eliminar_datos_usuario_admin_regular_devuelve_403(client, admin_token):
    resp = client.delete(
        "/api/admins/datos-usuario",
        params={"telefono": "5491112345678"},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 403


def test_eliminar_datos_usuario_telefono_muy_corto_devuelve_422(client, superadmin_token):
    resp = client.delete(
        "/api/admins/datos-usuario",
        params={"telefono": "123"},
        cookies={"access_token": superadmin_token},
    )
    assert resp.status_code == 422


def test_eliminar_datos_usuario_sin_coincidencias_devuelve_cero(client, superadmin_token):
    """Un teléfono sin validaciones asociadas devuelve eliminadas=0."""
    resp = client.delete(
        "/api/admins/datos-usuario",
        params={"telefono": "5499999000000"},
        cookies={"access_token": superadmin_token},
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["eliminadas"] == 0
    assert datos["imagenes_eliminadas"] == 0
