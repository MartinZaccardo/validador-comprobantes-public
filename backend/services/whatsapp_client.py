import logging
import urllib.parse

import httpx
from config import config

_logger = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v25.0"

# Sufijos de dominio autorizados para descargar media de Meta.
# Usamos sufijos (no dominios exactos) para no rompernos si Meta cambia subdominios.
_META_SUFIJOS_PERMITIDOS = (
    ".whatsapp.net",
    ".fbsbx.com",
    ".fbcdn.net",
    ".facebook.com",
)


def _validar_url_meta(url: str) -> None:
    """Previene SSRF: la URL de media debe ser HTTPS y pertenecer a dominios de Meta."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"URL de media con esquema no permitido: {parsed.scheme!r}")
    host = parsed.hostname or ""
    if not any(host.endswith(sufijo) for sufijo in _META_SUFIJOS_PERMITIDOS):
        raise ValueError(f"URL de media con dominio no permitido: {host!r}")


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.whatsapp_token}"}


def _normalizar_numero(numero: str) -> str:
    # Argentina: el webhook entrega números móviles como 549XXXXXXXXXX (con el 9
    # de indicador de móvil), pero la Graph API los acepta como 54XXXXXXXXXX.
    # Meta mapea ambos al mismo wa_id internamente.
    if numero.startswith("549") and len(numero) == 13:
        return "54" + numero[3:]
    return numero


async def descargar_imagen(media_id: str, cliente_http: httpx.AsyncClient) -> bytes:
    """Descarga una imagen de la Graph API de Meta dado su media_id.

    El flujo es en dos pasos: primero se obtiene la URL real de la imagen,
    luego se descarga el contenido binario desde esa URL.
    """
    headers = _auth_header()
    respuesta_url = await cliente_http.get(
        f"{_GRAPH_API_BASE}/{media_id}",
        headers=headers,
    )
    if not respuesta_url.is_success:
        _logger.error(
            "Error obteniendo URL de media — status=%s body=%.300s",
            respuesta_url.status_code, respuesta_url.text,
        )
    respuesta_url.raise_for_status()
    url_imagen = respuesta_url.json()["url"]
    _validar_url_meta(url_imagen)

    respuesta_imagen = await cliente_http.get(url_imagen, headers=headers)
    if not respuesta_imagen.is_success:
        _logger.error(
            "Error descargando binario de imagen — status=%s",
            respuesta_imagen.status_code,
        )
    respuesta_imagen.raise_for_status()
    return respuesta_imagen.content


async def enviar_mensaje_texto(
    numero_destino: str,
    texto: str,
    cliente_http: httpx.AsyncClient,
) -> None:
    headers = {**_auth_header(), "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": _normalizar_numero(numero_destino),
        "type": "text",
        "text": {"body": texto},
    }
    respuesta = await cliente_http.post(
        f"{_GRAPH_API_BASE}/{config.whatsapp_phone_number_id}/messages",
        headers=headers,
        json=payload,
    )
    if not respuesta.is_success:
        _logger.error("Meta API error %s: %s", respuesta.status_code, respuesta.text[:200])
    respuesta.raise_for_status()
