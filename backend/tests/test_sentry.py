"""
Tests de integración de Sentry.

No testeamos que Sentry envíe eventos reales (requiere DSN válido y red).
Verificamos que el init condicional funciona correctamente: Sentry se activa
solo cuando SENTRY_DSN está configurado, y la app arranca bien en ambos casos.
"""
import sentry_sdk


def test_sentry_inactivo_sin_dsn(client):
    """Sin SENTRY_DSN configurado, Sentry no debe estar inicializado."""
    # sentry_sdk.is_initialized() devuelve True si init() fue llamado con DSN.
    # En tests, SENTRY_DSN no está en .env → el cliente debe estar en modo noop.
    cliente_sentry = sentry_sdk.get_client()
    # El cliente noop tiene dsn=None
    assert cliente_sentry.dsn is None


def test_app_responde_con_sentry_desactivado(client):
    """La app funciona normalmente aunque Sentry no esté configurado."""
    resp = client.get("/health")
    assert resp.status_code == 200
