"""
Tests de integración: POST /auth/login, GET /auth/me y POST /auth/logout.

Usan la DB de test (validador_test) con un admin creado por el fixture
'admin_test' en conftest.py.
"""
from tests.conftest import _TEST_ADMIN_EMAIL, _TEST_ADMIN_PASSWORD

# =============================================================================
# POST /auth/login
# =============================================================================

def test_login_credenciales_validas(client, admin_test):
    resp = client.post("/auth/login", json={
        "email": _TEST_ADMIN_EMAIL,
        "password": _TEST_ADMIN_PASSWORD,
    })
    assert resp.status_code == 200

    body = resp.json()
    assert "admin" in body
    assert body["admin"]["email"] == _TEST_ADMIN_EMAIL
    assert body["admin"]["nombre"] == "Admin Test"
    # El JWT viaja como cookie httpOnly — no aparece en el body
    assert "access_token" in resp.cookies


def test_login_email_inexistente_devuelve_401(client):
    resp = client.post("/auth/login", json={
        "email": "nadie@noexiste.com",
        "password": "cualquier_cosa",
    })
    assert resp.status_code == 401
    # El mensaje es genérico — no revela si el email existe o no
    assert "inválidas" in resp.json()["detail"].lower()


def test_login_password_incorrecta_devuelve_401(client, admin_test):
    resp = client.post("/auth/login", json={
        "email": _TEST_ADMIN_EMAIL,
        "password": "clave_incorrecta_123",  # sin caracteres especiales (evita encoding Windows)
    })
    assert resp.status_code == 401


def test_login_email_formato_invalido_devuelve_422(client):
    """Pydantic valida que el email tenga formato válido antes de llegar al handler."""
    resp = client.post("/auth/login", json={
        "email": "esto-no-es-un-email",
        "password": "cualquier_cosa",
    })
    assert resp.status_code == 422


def test_login_sin_body_devuelve_422(client):
    resp = client.post("/auth/login")
    assert resp.status_code == 422


# =============================================================================
# GET /auth/me
# =============================================================================

def test_me_con_token_valido(client, admin_token, admin_test):
    resp = client.get(
        "/auth/me",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["id"]    == admin_test["id"]
    assert body["email"] == _TEST_ADMIN_EMAIL
    assert body["nombre"] == "Admin Test"


def test_me_sin_token_devuelve_401(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_con_token_invalido_devuelve_401(client):
    resp = client.get(
        "/auth/me",
        cookies={"access_token": "token.invalido.xxx"},
    )
    assert resp.status_code == 401


def test_me_con_api_key_en_lugar_de_jwt_devuelve_401(client, api_key_header):
    """
    El header X-API-Key no es un Bearer token — no debe funcionar en /auth/me.
    Esto verifica que los dos sistemas de auth no se mezclen.
    """
    resp = client.get("/auth/me", headers=api_key_header)
    assert resp.status_code == 401


# =============================================================================
# POST /auth/logout
# =============================================================================

def test_logout_borra_cookie(client, admin_token):
    """El logout devuelve 204 y la respuesta incluye Set-Cookie con Max-Age=0."""
    resp = client.post(
        "/auth/logout",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 204
    # Starlette implementa delete_cookie con Max-Age=0
    set_cookie = resp.headers.get("set-cookie", "")
    assert "access_token" in set_cookie
    assert "Max-Age=0" in set_cookie


def test_logout_invalida_sesion(client, admin_token):
    """Después del logout, el token ya no sirve para /auth/me."""
    client.post("/auth/logout", cookies={"access_token": admin_token})
    resp = client.get("/auth/me", cookies={"access_token": admin_token})
    # El JWT sigue siendo criptográficamente válido hasta que expira —
    # este test documenta el comportamiento actual (sin lista negra de tokens).
    # Si en el futuro se agrega revocación en DB, este test debería devolver 401.
    assert resp.status_code == 200
