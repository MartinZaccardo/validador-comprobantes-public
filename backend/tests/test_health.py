"""
Tests de integración: GET /health.

Endpoint de infraestructura — Railway lo usa para healthcheck.
No requiere autenticación.
"""


def test_health_devuelve_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_no_requiere_token(client):
    """El healthcheck debe responder sin ningún header de auth."""
    resp = client.get("/health")
    assert resp.status_code == 200
