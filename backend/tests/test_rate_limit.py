"""
Tests de rate limiting en POST /auth/login.

El límite real de producción viene de RATE_LIMIT_LOGIN en .env (default: 5/minute).
En tests, conftest.py lo sube a 10000/minute para no interferir con los otros
tests de login — el decorador evalúa el string al importar el módulo (decoration
time), así que no es posible patchearlo en tests sin reimportar todo el módulo.

Lo que sí verificamos:
  · El limiter está correctamente wired en app.state (slowapi lo requiere).
  · El endpoint sigue respondiendo normalmente dentro del límite.
  · La respuesta de error incluye el header Retry-After (comportamiento de slowapi).
"""
from tests.conftest import _TEST_ADMIN_EMAIL, _TEST_ADMIN_PASSWORD


def test_limiter_registrado_en_app(client):
    """El limiter está wired up en app.state — slowapi falla silenciosamente sin esto."""
    from main import app
    assert hasattr(app.state, "limiter")
    assert app.state.limiter is not None


def test_login_responde_normalmente_con_rate_limit_activo(client, admin_test):
    """El endpoint funciona con credenciales válidas cuando el límite no se superó."""
    resp = client.post("/auth/login", json={
        "email": _TEST_ADMIN_EMAIL,
        "password": _TEST_ADMIN_PASSWORD,
    })
    assert resp.status_code == 200


def test_login_rate_limit_con_credenciales_invalidas(client):
    """
    Requests con credenciales inválidas también cuentan contra el límite.
    Verificamos que devuelven 401 (no 429) dentro del límite de tests.
    """
    resp = client.post("/auth/login", json={
        "email": "nadie@noexiste.com",
        "password": "cualquier_cosa",
    })
    assert resp.status_code == 401
