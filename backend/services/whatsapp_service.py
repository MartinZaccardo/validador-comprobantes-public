"""
Lógica de negocio del canal WhatsApp.

Los routers delegan acá. Este módulo no importa FastAPI.
"""
import asyncio
import logging
import uuid

import filetype
import httpx
import psycopg2
import psycopg2.pool
import redis.asyncio as aioredis
from config import config
from db import queries_clientes, queries_validaciones, queries_whatsapp
from db.base import q
from db.redis import clave_canal_validaciones
from models.resultado import CanalOrigen
from redis.exceptions import RedisError

from services import whatsapp_client
from services.analizar_service import EXT_POR_MIME
from services.ocr import procesar_imagen
from services.r2_client import subir_imagen_async
from services.validacion_core import determinar_estado

_logger = logging.getLogger(__name__)

_MENSAJE_NO_ES_IMAGEN       = "Hola! Para validar un comprobante enviá una foto, captura de pantalla o PDF del comprobante de pago."
_MENSAJE_PROCESANDO         = (
    "📋 Recibimos tu comprobante. Estamos verificando el pago, te respondemos en unos segundos...\n\n"
    "Al enviarnos imágenes, aceptás que tus datos sean utilizados exclusivamente para validar pagos con el comercio. "
    "No compartimos tu información con terceros."
)
_MENSAJE_APROBADO           = "✅ Comprobante APROBADO. El pago fue acreditado correctamente."
_MENSAJE_DUPLICADO          = "⚠️ Este comprobante ya fue registrado anteriormente."
_MENSAJE_MONTO              = "❌ El monto del comprobante no coincide con el pago registrado. Comunicate con el vendedor."
_MENSAJE_NO_ACREDITADO      = "❌ El pago no pudo ser verificado. Comunicate con el vendedor."
_MENSAJE_REVISION_MANUAL    = "⚠️ No pudimos verificar el número de operación del comprobante. Si el pago fue realizado, comunicate con el vendedor."
_MENSAJE_SIN_NUMERO_OPERACION = "⚠️ No pudimos encontrar el número de operación en la imagen. Abrí el comprobante, tocá el botón 'Compartir comprobante' y envianos esa imagen."
_MENSAJE_DESTINATARIO       = "❌ El destinatario del pago no corresponde al comercio. Verificá que el pago esté dirigido correctamente y comunicate con el vendedor."
_MENSAJE_INVALIDA           = "❌ La imagen no parece ser un comprobante de pago. Asegurate de enviar la captura completa del mismo."
_MENSAJE_ERROR              = "⚠️ Hubo un error al procesar el comprobante. Por favor reintentá en unos minutos."

_TEXTO_POR_ESTADO: dict[str, str] = {
    "APROBADO":                _MENSAJE_APROBADO,
    "DUPLICADO":               _MENSAJE_DUPLICADO,
    "MONTO_ADULTERADO":        _MENSAJE_MONTO,
    "PAGO_NO_ACREDITADO":      _MENSAJE_NO_ACREDITADO,
    "REVISION_MANUAL":         _MENSAJE_REVISION_MANUAL,
    "NUMERO_OP_NO_ENCONTRADO": _MENSAJE_SIN_NUMERO_OPERACION,
    "ERROR_DESTINATARIO":      _MENSAJE_DESTINATARIO,
    "IMAGEN_INVALIDA":         _MENSAJE_INVALIDA,
    "ERROR_MP":                _MENSAJE_ERROR,
}


class WhatsAppService:
    # Atributo de clase: compartido entre todas las instancias del proceso.
    # Limita OCR/MP concurrente a 5 imágenes en vuelo.
    _semaphore: asyncio.Semaphore = asyncio.Semaphore(5)

    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool, redis: aioredis.Redis) -> None:
        self.pool = pool
        self.redis = redis

    async def procesar_mensaje(
        self,
        numero_remitente: str,
        media_id: str,
    ) -> None:
        """Background task: descarga imagen, OCR, determina estado, persiste en DB y responde."""
        _logger.info("[wpp] procesar_mensaje iniciado — remitente=...%s media_id=...%s",
                     numero_remitente[-4:], media_id[-6:])
        try:
            async with httpx.AsyncClient(timeout=30) as cliente_http:
                await self._responder_texto(numero_remitente, _MENSAJE_PROCESANDO, cliente_http)
                try:
                    imagen_bytes = await whatsapp_client.descargar_imagen(media_id, cliente_http)
                except Exception as e:  # noqa: BLE001
                    _logger.error("[wpp] Error descargando imagen media_id=...%s: %s", media_id[-6:], e)
                    await self._responder_texto(numero_remitente, _MENSAJE_ERROR, cliente_http)
                    return

                estado: str = "ERROR_MP"
                mp_status_code: int | None = None

                async with self._semaphore:
                    resultado_ocr = await procesar_imagen(imagen_bytes, CanalOrigen.WHATSAPP)
                    ops_aprobadas = await self._obtener_ops_aprobadas()
                    estado, mp_status_code, numero_op = await determinar_estado(
                        resultado_ocr, ops_aprobadas, self.redis
                    )

                    validacion_id = str(uuid.uuid4())
                    tipo_imagen = filetype.guess(imagen_bytes)
                    ext = EXT_POR_MIME.get(tipo_imagen.mime, ".jpg") if tipo_imagen else ".jpg"
                    r2_key = f"uploads/{config.tenant_id}/{validacion_id}{ext}"
                    try:
                        await subir_imagen_async(r2_key, imagen_bytes)
                        imagen_path = r2_key
                    except Exception:  # noqa: BLE001
                        imagen_path = None

                    cuit_remitente = resultado_ocr.cuit_remitente if resultado_ocr else None
                    cliente_id_vinculado, codigo_cliente_vinculado = await q(
                        queries_clientes.resolver_cliente_para_vinculacion,
                        self.pool, cuit_remitente, numero_remitente,
                    )
                    await q(
                        queries_validaciones.guardar_validacion_whatsapp,
                        self.pool,
                        validacion_id,
                        config.tenant_id,
                        numero_remitente,
                        estado,
                        numero_op,
                        resultado_ocr.monto_detectado,
                        resultado_ocr.cuit_destinatario_detectado,
                        resultado_ocr.es_comprobante_valido,
                        mp_status_code,
                        imagen_path,
                        resultado_ocr.error,
                        resultado_ocr,
                        cliente_id=cliente_id_vinculado,
                        codigo_cliente_vinculado=codigo_cliente_vinculado,
                    )
                    try:
                        await self.redis.publish(clave_canal_validaciones(config.tenant_id), "1")
                    except RedisError:
                        _logger.warning("[wpp] No se pudo publicar validación en Redis")

                await self._responder_texto(numero_remitente, _texto_respuesta(estado), cliente_http)
        except Exception:
            _logger.exception("[wpp] Error inesperado en procesar_mensaje — remitente=...%s", numero_remitente[-4:])
            await self._responder_texto(numero_remitente, _MENSAJE_ERROR)
        finally:
            await self._eliminar_pendiente(media_id)

    async def registrar_pendiente(self, media_id: str, numero_remitente: str) -> None:
        try:
            await q(queries_whatsapp.crear_mensaje_pendiente, self.pool, config.tenant_id, media_id, numero_remitente)
        except psycopg2.Error as e:
            _logger.error("[wpp] No se pudo registrar pendiente media_id=...%s: %s", media_id[-6:], e)

    async def _eliminar_pendiente(self, media_id: str) -> None:
        try:
            await q(queries_whatsapp.eliminar_mensaje_pendiente, self.pool, media_id)
        except psycopg2.Error as e:
            _logger.error("[wpp] No se pudo eliminar pendiente media_id=...%s: %s", media_id[-6:], e)

    async def manejar_mensaje_no_imagen(self, numero_remitente: str) -> None:
        """Responde al remitente indicando que debe enviar una imagen."""
        await self._responder_texto(numero_remitente, _MENSAJE_NO_ES_IMAGEN)

    async def _obtener_ops_aprobadas(self) -> set[str]:
        try:
            return await q(queries_validaciones.obtener_ops_aprobadas, self.pool, config.tenant_id)
        except psycopg2.Error as e:
            _logger.warning("No se pudieron cargar ops_aprobadas (WhatsApp): %s", e)
            return set()

    @staticmethod
    async def _responder_texto(
        numero_destino: str,
        texto: str,
        cliente_http: httpx.AsyncClient | None = None,
    ) -> None:
        try:
            if cliente_http is not None:
                await whatsapp_client.enviar_mensaje_texto(numero_destino, texto, cliente_http)
                return
            async with httpx.AsyncClient(timeout=10) as cliente:
                await whatsapp_client.enviar_mensaje_texto(numero_destino, texto, cliente)
        except Exception as e:  # noqa: BLE001
            _logger.error("Error al enviar respuesta WhatsApp a ...%s: %s", numero_destino[-4:], e)


def _texto_respuesta(estado: str) -> str:
    return _TEXTO_POR_ESTADO.get(estado, _MENSAJE_ERROR)
