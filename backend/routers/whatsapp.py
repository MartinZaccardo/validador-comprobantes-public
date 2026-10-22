"""
Webhook de WhatsApp (Meta Cloud API).

Dos endpoints:
  GET  /webhook/whatsapp — verificación inicial que Meta exige al configurar el webhook.
  POST /webhook/whatsapp — mensajes entrantes de clientes.

Por qué responder 200 antes de procesar:
  Meta reintenta el POST si no recibe 200 en < 5 segundos. OCR puede tardar 8-10 s.
  Si procesamos sincrónicamente, Meta reenvía el mensaje → duplicados en DB.
  Solución: mismo patrón de POST /api/runs — responder 200 inmediatamente,
  procesar en BackgroundTask.
"""
import hashlib
import hmac
import logging

from config import config
from fastapi import APIRouter, BackgroundTasks, Query, Request, Response

from routers.deps import WhatsAppServiceDep

router = APIRouter(tags=["whatsapp"])

_logger = logging.getLogger(__name__)


async def _firma_valida(request: Request) -> bool:
    """
    Verifica la firma HMAC-SHA256 que Meta incluye en cada POST del webhook.

    Si WHATSAPP_APP_SECRET no está configurado (dev local sin webhook real),
    loguea un WARNING y deja pasar — la validación se activa sola en producción
    cuando la variable está presente.
    """
    if not config.whatsapp_app_secret:
        if config.secure_cookies:
            _logger.error("WHATSAPP_APP_SECRET no configurado en producción — rechazando webhook")
            return False
        _logger.warning("WHATSAPP_APP_SECRET no configurado — omitiendo verificación de firma (solo dev)")
        return True

    firma_recibida = request.headers.get("x-hub-signature-256", "")
    if not firma_recibida:
        return False

    cuerpo = await request.body()
    firma_calculada = "sha256=" + hmac.new(
        config.whatsapp_app_secret.encode(),
        cuerpo,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(firma_calculada, firma_recibida)


@router.get("/webhook/whatsapp")
async def verificar_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Response:
    """
    Meta llama a este endpoint cuando configurás el webhook en el panel de desarrolladores.
    Si el verify_token coincide con el nuestro, respondemos con el challenge.
    """
    if hub_mode == "subscribe" and hub_verify_token == config.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(status_code=403)


@router.post("/webhook/whatsapp", status_code=200)
async def recibir_mensaje(request: Request, background_tasks: BackgroundTasks, servicio_whatsapp: WhatsAppServiceDep) -> dict:
    """
    Recibe eventos de Meta: mensajes, actualizaciones de estado de entrega, etc.

    Siempre devuelve 200 — Meta reintenta si no recibe 200 en < 5 segundos.
    El procesamiento real (OCR + MP + DB + respuesta WhatsApp) va en BackgroundTask.
    """
    _logger.info("POST /webhook/whatsapp recibido")

    if not await _firma_valida(request):
        _logger.warning("POST /webhook/whatsapp rechazado — firma X-Hub-Signature-256 inválida o ausente")
        return {"status": "ok"}

    payload = await request.json()
    _logger.info("Webhook payload — entries=%d", len(payload.get("entry", [])))

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            datos_evento = change.get("value", {})
            for mensaje in datos_evento.get("messages", []):
                numero_remitente = mensaje.get("from", "")
                tipo_mensaje = mensaje.get("type", "")
                _logger.info(
                    "Mensaje entrante tipo=%s de ...%s",
                    tipo_mensaje, numero_remitente[-4:] if numero_remitente else "??",
                )
                if tipo_mensaje == "image":
                    media_id = mensaje.get("image", {}).get("id", "")
                elif tipo_mensaje == "document":
                    doc = mensaje.get("document", {})
                    if doc.get("mime_type", "") != "application/pdf":
                        background_tasks.add_task(
                            servicio_whatsapp.manejar_mensaje_no_imagen,
                            numero_remitente,
                        )
                        continue
                    media_id = doc.get("id", "")
                else:
                    background_tasks.add_task(
                        servicio_whatsapp.manejar_mensaje_no_imagen,
                        numero_remitente,
                    )
                    continue

                if not media_id:
                    _logger.warning("Mensaje tipo=%s sin media_id — ignorando", tipo_mensaje)
                    continue

                _logger.info("Background task encolado para media_id=...%s", media_id[-6:])
                await servicio_whatsapp.registrar_pendiente(media_id, numero_remitente)
                background_tasks.add_task(
                    servicio_whatsapp.procesar_mensaje,
                    numero_remitente,
                    media_id,
                )

    return {"status": "ok"}
