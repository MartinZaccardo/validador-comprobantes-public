"""
Tests de integración: PATCH /auth/me.

Verifica la actualización del teléfono del admin autenticado.
GET /auth/me ya está cubierto en test_auth.py.
"""


def _patch_me(client, token, body):
    return client.patch(
        "/auth/me",
        json=body,
        cookies={"access_token": token},
    )


def _get_me(client, token):
    return client.get(
        "/auth/me",
        cookies={"access_token": token},
    )


# =============================================================================
# PATCH /auth/me
# =============================================================================

def test_patch_me_sin_token_devuelve_401(client):
    resp = client.patch("/auth/me", json={"telefono": "+54911111111"})
    assert resp.status_code == 401


def test_patch_me_actualiza_telefono(client, admin_token, admin_test):
    resp = _patch_me(client, admin_token, {"telefono": "+54911234567"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["telefono"] == "+54911234567"
    assert body["id"] == admin_test["id"]
    assert body["email"] == admin_test["email"]

    # Cleanup: restaurar sin teléfono para no afectar otros tests
    _patch_me(client, admin_token, {"telefono": None})


def test_patch_me_telefono_persiste_en_get(client, admin_token):
    """El teléfono guardado aparece en GET /auth/me posterior."""
    _patch_me(client, admin_token, {"telefono": "+54911999888"})

    resp = _get_me(client, admin_token)
    assert resp.status_code == 200
    assert resp.json()["telefono"] == "+54911999888"

    _patch_me(client, admin_token, {"telefono": None})


def test_patch_me_borra_telefono(client, admin_token):
    """Enviar telefono=null limpia el valor guardado."""
    _patch_me(client, admin_token, {"telefono": "+54911234567"})

    resp = _patch_me(client, admin_token, {"telefono": None})
    assert resp.status_code == 200
    assert resp.json()["telefono"] is None


def test_patch_me_respuesta_incluye_campos_de_identidad(client, admin_token):
    """La respuesta incluye todos los campos del modelo AdminInfo."""
    resp = _patch_me(client, admin_token, {"telefono": None})

    assert resp.status_code == 200
    body = resp.json()
    for campo in ("id", "nombre", "email", "es_superadmin", "telefono"):
        assert campo in body, f"Falta el campo '{campo}'"
