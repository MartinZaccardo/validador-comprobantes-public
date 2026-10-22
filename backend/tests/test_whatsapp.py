"""
Tests de routers/whatsapp:
  - Unitarios: _texto_respuesta (función pura, sin DB ni red).
  - Unitarios: _validar_url_meta (prevención SSRF en descarga de media).
  - Integración: GET /webhook/whatsapp (verificación Meta).
  - Integración: POST /webhook/whatsapp (mensajes entrantes de WhatsApp).
  - Seguridad: validación de firma X-Hub-Signature-256.
"""
import asyncio
import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, patch

import db.connection as db_conn
import pytest
from config import config
from db import queries_whatsapp
from db.redis import get_cliente_redis
from models.resultado import FuenteOCR, ResultadoOCR
from services.whatsapp_client import _validar_url_meta
from services.whatsapp_service import (
    _MENSAJE_APROBADO,
    _MENSAJE_NO_ES_IMAGEN,
    _MENSAJE_REVISION_MANUAL,
    _MENSAJE_SIN_NUMERO_OPERACION,
    WhatsAppService,
    _texto_respuesta,
)


def test_numero_op_no_encontrado_pide_compartir_comprobante():
    """OCR no detectó número de operación pero sí hay evidencia de comprobante → pedir 'Compartir comprobante'."""
    assert _texto_respuesta("NUMERO_OP_NO_ENCONTRADO") == _MENSAJE_SIN_NUMERO_OPERACION


def test_revision_manual_usa_mensaje_generico():
    """numero_op con baja confianza o MP devolvió 404 → mensaje de revisión manual."""
    assert _texto_respuesta("REVISION_MANUAL") == _MENSAJE_REVISION_MANUAL


def test_aprobado_usa_mensaje_de_tabla():
    assert _texto_respuesta("APROBADO") == _MENSAJE_APROBADO


# --- Integración: GET /webhook/whatsapp ---

def test_verificacion_token_correcto_devuelve_challenge(client):
    """Meta envía mode=subscribe + token correcto → 200 con el challenge exacto."""
    resp = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": config.whatsapp_verify_token,
            "hub.challenge": "test_challenge_12345",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "test_challenge_12345"


def test_verificacion_token_incorrecto_devuelve_403(client):
    """Token incorrecto → 403 aunque el mode sea correcto."""
    resp = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "token_incorrecto",
            "hub.challenge": "test_challenge_12345",
        },
    )
    assert resp.status_code == 403


def test_verificacion_mode_incorrecto_devuelve_403(client):
    """Mode distinto de 'subscribe' → 403 aunque el token sea correcto."""
    resp = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": config.whatsapp_verify_token,
            "hub.challenge": "test_challenge_12345",
        },
    )
    assert resp.status_code == 403


def test_verificacion_sin_parametros_devuelve_403(client):
    """Sin parámetros → defaults vacíos, no coincide → 403."""
    resp = client.get("/webhook/whatsapp")
    assert resp.status_code == 403


# --- Integración: POST /webhook/whatsapp ---

_NUMERO_REMITENTE = "5491112345678"

_PAYLOAD_SIN_MENSAJES = {"entry": [{"changes": [{"value": {}}]}]}

_PAYLOAD_TEXTO = {
    "entry": [{"changes": [{"value": {"messages": [
        {"from": _NUMERO_REMITENTE, "type": "text"},
    ]}}]}]
}

_PAYLOAD_IMAGEN = {
    "entry": [{"changes": [{"value": {"messages": [
        {"from": _NUMERO_REMITENTE, "type": "image", "image": {"id": "fake_media_id_123"}},
    ]}}]}]
}


def test_webhook_post_payload_sin_mensajes_responde_ok(client):
    """Status update de entrega (sin messages) → 200, sin side effects."""
    resp = client.post("/webhook/whatsapp", json=_PAYLOAD_SIN_MENSAJES)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_mensaje_no_imagen_envia_instruccion(client):
    """Mensaje de texto → 200 + envía _MENSAJE_NO_ES_IMAGEN por WhatsApp."""
    with (
        patch.object(config, "whatsapp_app_secret", ""),  # deshabilitar firma en test de comportamiento
        patch(
            "services.whatsapp_service.whatsapp_client.enviar_mensaje_texto",
            new_callable=AsyncMock,
        ) as mock_enviar,
    ):
        resp = client.post("/webhook/whatsapp", json=_PAYLOAD_TEXTO)

    assert resp.status_code == 200
    mock_enviar.assert_called_once()
    numero, mensaje, *_ = mock_enviar.call_args[0]
    assert numero == _NUMERO_REMITENTE
    assert mensaje == _MENSAJE_NO_ES_IMAGEN


# --- Seguridad: validación de firma X-Hub-Signature-256 ---

_SECRET_TEST = "test_app_secret_para_tests"


def _firma_para(body_bytes: bytes) -> str:
    """Calcula la firma HMAC-SHA256 que Meta enviaría con el cuerpo dado."""
    return "sha256=" + hmac.new(_SECRET_TEST.encode(), body_bytes, hashlib.sha256).hexdigest()


def test_post_con_secret_configurado_sin_firma_no_procesa(client):
    """Con WHATSAPP_APP_SECRET configurado, un POST sin firma devuelve 200 pero no procesa."""
    with (
        patch.object(config, "whatsapp_app_secret", _SECRET_TEST),
        patch("services.whatsapp_service.whatsapp_client.enviar_mensaje_texto", new_callable=AsyncMock) as mock_enviar,
    ):
        resp = client.post("/webhook/whatsapp", json=_PAYLOAD_TEXTO)

    assert resp.status_code == 200
    mock_enviar.assert_not_called()


def test_post_con_secret_configurado_firma_invalida_no_procesa(client):
    """Con WHATSAPP_APP_SECRET configurado, una firma incorrecta devuelve 200 pero no procesa."""
    with (
        patch.object(config, "whatsapp_app_secret", _SECRET_TEST),
        patch("services.whatsapp_service.whatsapp_client.enviar_mensaje_texto", new_callable=AsyncMock) as mock_enviar,
    ):
        resp = client.post(
            "/webhook/whatsapp",
            content=json.dumps(_PAYLOAD_TEXTO).encode(),
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=firma_incorrecta"},
        )

    assert resp.status_code == 200
    mock_enviar.assert_not_called()


def test_post_sin_secret_en_produccion_no_procesa(client):
    """En producción (secure_cookies=True), APP_SECRET vacío → rechaza sin procesar."""
    with (
        patch.object(config, "whatsapp_app_secret", ""),
        patch.object(config, "secure_cookies", True),
        patch("services.whatsapp_service.whatsapp_client.enviar_mensaje_texto", new_callable=AsyncMock) as mock_enviar,
    ):
        resp = client.post("/webhook/whatsapp", json=_PAYLOAD_TEXTO)

    assert resp.status_code == 200
    mock_enviar.assert_not_called()


def test_post_con_secret_configurado_firma_valida_procesa(client):
    """Con WHATSAPP_APP_SECRET configurado, una firma correcta deja pasar el request."""
    cuerpo = json.dumps(_PAYLOAD_SIN_MENSAJES).encode()
    with patch.object(config, "whatsapp_app_secret", _SECRET_TEST):
        resp = client.post(
            "/webhook/whatsapp",
            content=cuerpo,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": _firma_para(cuerpo)},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_imagen_aprobada_envia_mensaje_aprobado(client):
    """Pipeline completo (imagen APROBADO): OCR→MP→WPP — responde _MENSAJE_APROBADO."""
    # Número único por corrida: nunca está en la DB de test → obtener_ops_aprobadas devuelve set()
    resultado_ocr_fake = ResultadoOCR(
        fuente=FuenteOCR.LLM_GEMINI,
        es_comprobante_valido=True,
        identificador_pago=str(uuid.uuid4()),
        monto_detectado="$1.000,00",
        cuit_destinatario_detectado="20123456789",
    )

    with (
        patch.object(config, "whatsapp_app_secret", ""),  # deshabilitar firma en test de comportamiento
        patch("services.whatsapp_service.whatsapp_client.descargar_imagen", new_callable=AsyncMock, return_value=b"fake_bytes"),
        patch("services.whatsapp_service.procesar_imagen", new_callable=AsyncMock, return_value=resultado_ocr_fake),
        patch("services.validacion_core.MpClient.verificar_pago", new_callable=AsyncMock, return_value=("APROBADO", 200)),
        patch("services.whatsapp_service.subir_imagen_async", new_callable=AsyncMock, return_value=None),
        patch("services.whatsapp_service.queries_validaciones.guardar_validacion_whatsapp"),  # evita residuos en DB de test
        patch("services.whatsapp_service.whatsapp_client.enviar_mensaje_texto", new_callable=AsyncMock) as mock_enviar,
    ):
        resp = client.post("/webhook/whatsapp", json=_PAYLOAD_IMAGEN)

    assert resp.status_code == 200
    # 1ª llamada: _MENSAJE_PROCESANDO — 2ª: resultado final
    assert mock_enviar.call_count == 2
    _, mensaje_final, *_ = mock_enviar.call_args_list[-1][0]
    assert mensaje_final == _MENSAJE_APROBADO


# =============================================================================
# Unitarios: _validar_url_meta (prevención SSRF)
# =============================================================================

@pytest.mark.parametrize("url_valida", [
    "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123",
    "https://mmg.whatsapp.net/v/t62.7119-24/123456",
    "https://cdn.whatsapp.net/media/123",
    "https://media.fbcdn.net/v/t1.18169-9/123456",
])
def test_validar_url_meta_acepta_dominios_de_meta(url_valida: str):
    _validar_url_meta(url_valida)  # no debe lanzar excepción


@pytest.mark.parametrize("url_invalida", [
    "http://lookaside.fbsbx.com/imagen.jpg",           # HTTP plano
    "https://169.254.169.254/latest/meta-data/",       # metadata de instancia (SSRF)
    "https://localhost/internal-api",                  # red interna
    "https://evil.com/fake-whatsapp-media",            # dominio arbitrario
    "file:///etc/passwd",                              # protocolo file://
    "https://evilfbsbx.com/bypass",                   # dominio que contiene pero no termina en sufijo
])
def test_validar_url_meta_rechaza_urls_no_permitidas(url_invalida: str):
    with pytest.raises(ValueError):
        _validar_url_meta(url_invalida)


# =============================================================================
# Integración: patrón PENDIENTE — recovery de mensajes en reinicio
# =============================================================================

def test_registrar_pendiente_inserta_en_db(client):
    """registrar_pendiente() crea una fila en mensajes_whatsapp_pendientes."""
    pool = db_conn.get_pool()
    servicio = WhatsAppService(pool, get_cliente_redis())

    asyncio.run(servicio.registrar_pendiente("media_reg_test_001", _NUMERO_REMITENTE))

    pendientes = queries_whatsapp.obtener_mensajes_pendientes(pool, config.tenant_id)
    assert any(p["media_id"] == "media_reg_test_001" for p in pendientes)

    queries_whatsapp.eliminar_mensaje_pendiente(pool, "media_reg_test_001")


def test_ciclo_completo_imagen_elimina_pendiente_al_terminar(client):
    """POST /webhook → registrar_pendiente → background task → finally elimina el pendiente."""
    pool = db_conn.get_pool()
    resultado_ocr_fake = ResultadoOCR(
        fuente=FuenteOCR.LLM_GEMINI,
        es_comprobante_valido=True,
        identificador_pago=str(uuid.uuid4()),
        monto_detectado="$1.000,00",
        cuit_destinatario_detectado="20123456789",
    )
    with (
        patch.object(config, "whatsapp_app_secret", ""),
        patch("services.whatsapp_service.whatsapp_client.descargar_imagen", new_callable=AsyncMock, return_value=b"fake_bytes"),
        patch("services.whatsapp_service.procesar_imagen", new_callable=AsyncMock, return_value=resultado_ocr_fake),
        patch("services.validacion_core.MpClient.verificar_pago", new_callable=AsyncMock, return_value=("APROBADO", 200)),
        patch("services.whatsapp_service.subir_imagen_async", new_callable=AsyncMock, return_value=None),
        patch("services.whatsapp_service.queries_validaciones.guardar_validacion_whatsapp"),
        patch("services.whatsapp_service.whatsapp_client.enviar_mensaje_texto", new_callable=AsyncMock),
    ):
        resp = client.post("/webhook/whatsapp", json=_PAYLOAD_IMAGEN)

    assert resp.status_code == 200
    pendientes = queries_whatsapp.obtener_mensajes_pendientes(pool, config.tenant_id)
    assert not any(p["media_id"] == "fake_media_id_123" for p in pendientes)


def test_procesar_mensaje_elimina_pendiente_si_descarga_falla(client):
    """finally corre incluso cuando la descarga de imagen falla — sin pérdida silenciosa."""
    pool = db_conn.get_pool()
    servicio = WhatsAppService(pool, get_cliente_redis())

    asyncio.run(servicio.registrar_pendiente("media_err_test_001", _NUMERO_REMITENTE))
    assert any(
        p["media_id"] == "media_err_test_001"
        for p in queries_whatsapp.obtener_mensajes_pendientes(pool, config.tenant_id)
    )

    with (
        patch("services.whatsapp_service.whatsapp_client.descargar_imagen", side_effect=Exception("red caída")),
        patch("services.whatsapp_service.whatsapp_client.enviar_mensaje_texto", new_callable=AsyncMock),
    ):
        asyncio.run(servicio.procesar_mensaje(_NUMERO_REMITENTE, "media_err_test_001"))

    pendientes = queries_whatsapp.obtener_mensajes_pendientes(pool, config.tenant_id)
    assert not any(p["media_id"] == "media_err_test_001" for p in pendientes)

