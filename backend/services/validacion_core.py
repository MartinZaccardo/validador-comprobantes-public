"""
Núcleo de validación de comprobantes — compartido por todos los canales.

Cualquier cambio en la lógica de consulta a MP, detección de duplicados
o fuzzy match se hace aquí y aplica automáticamente a WhatsApp
y carga manual.
"""
import logging

import httpx
import redis.asyncio as aioredis
from config import config
from db.redis import clave_ops_pendientes
from models.resultado import ResultadoOCR
from redis.exceptions import RedisError

from services.llm_extractor import TipoIdentificador
from services.mp_client import MpClient

_logger = logging.getLogger(__name__)


def estado_sin_numero_op(resultado_ocr: ResultadoOCR) -> str:
    """Determina el estado cuando el OCR no encontró identificador de pago."""
    tiene_evidencia = (
        resultado_ocr.es_comprobante_valido
        or resultado_ocr.monto_detectado is not None
        or resultado_ocr.cuit_destinatario_detectado is not None
    )
    return "NUMERO_OP_NO_ENCONTRADO" if tiene_evidencia else "IMAGEN_INVALIDA"


async def determinar_estado(
    resultado_ocr: ResultadoOCR,
    ops_aprobadas: set[str],
    redis: aioredis.Redis,
) -> tuple[str, int | None, str | None]:
    """
    Determina el estado de validación de un comprobante consultando MP.

    Recibe el resultado del OCR y el contexto de deduplicación (ops ya aprobadas
    en DB + cliente Redis para el anti-duplicado en vuelo).

    Retorna (estado, mp_status_code, identificador_final).
    identificador_final puede diferir del OCR en el path SIN_IDENTIFICADOR_TRAZABLE,
    donde se resuelve al payment ID de MP encontrado por monto+fecha.

    Orden de decisión:
      1. SIN_IDENTIFICADOR_TRAZABLE → fuzzy match por monto+fecha
      2. Sin identificador → NUMERO_OP_NO_ENCONTRADO o IMAGEN_INVALIDA
      3. Baja confianza en identificador → REVISION_MANUAL
      4. Duplicado histórico (ops_aprobadas de DB) → DUPLICADO
      5. Duplicado en vuelo (Redis SADD) → DUPLICADO
      6. Consultar MP (COELSA_ID o NUMERO_OP_MP) → estado final
    """
    if resultado_ocr.forzar_revision_manual:
        return "REVISION_MANUAL", None, None

    tipo = resultado_ocr.tipo_identificador
    numero_op = resultado_ocr.identificador_pago

    # ── Path SIN_IDENTIFICADOR_TRAZABLE ──────────────────────────────────────
    if tipo == TipoIdentificador.SIN_IDENTIFICADOR_TRAZABLE.value:
        if not resultado_ocr.monto_detectado or not resultado_ocr.fecha_comprobante:
            return estado_sin_numero_op(resultado_ocr), None, None
        try:
            mp = MpClient()
            estado, mp_status_code, pago_id = await mp.buscar_pago_por_monto_fecha(
                resultado_ocr.monto_detectado,
                resultado_ocr.fecha_comprobante,
                resultado_ocr.cuit_destinatario_detectado,
                resultado_ocr.cuit_remitente,
            )
        except httpx.HTTPError as e:
            _logger.error("Error fuzzy-match MP: %s", e)
            return "ERROR_MP", None, None

        if estado != "APROBADO" or not pago_id:
            return estado, mp_status_code, None

        if pago_id in ops_aprobadas:
            return "DUPLICADO", mp_status_code, pago_id

        clave = clave_ops_pendientes(config.tenant_id)
        if await redis.sadd(clave, pago_id) == 0:
            return "DUPLICADO", mp_status_code, pago_id
        await redis.srem(clave, pago_id)
        return "APROBADO", mp_status_code, pago_id

    # ── Sin identificador extraíble ───────────────────────────────────────────
    if not numero_op:
        return estado_sin_numero_op(resultado_ocr), None, None

    # ── Baja confianza (LLM extrajo el ID dos veces con valores distintos) ────
    if resultado_ocr.baja_confianza_identificador:
        return "REVISION_MANUAL", None, numero_op

    # ── Duplicado histórico ───────────────────────────────────────────────────
    if numero_op in ops_aprobadas:
        return "DUPLICADO", None, numero_op

    # ── Duplicado en vuelo ────────────────────────────────────────────────────
    clave = clave_ops_pendientes(config.tenant_id)
    if await redis.sadd(clave, numero_op) == 0:
        return "DUPLICADO", None, numero_op

    # ── Consulta a MP ─────────────────────────────────────────────────────────
    estado: str = "ERROR_MP"
    mp_status_code: int | None = None
    try:
        mp = MpClient()
        if tipo == TipoIdentificador.COELSA_ID.value:
            estado, mp_status_code = await mp.buscar_pago_por_coelsa_id(
                numero_op,
                resultado_ocr.monto_detectado,
                resultado_ocr.fecha_comprobante,
                resultado_ocr.cuit_destinatario_detectado,
            )
        else:
            estado, mp_status_code = await mp.verificar_pago(
                numero_op,
                resultado_ocr.monto_detectado,
                resultado_ocr.cuit_destinatario_detectado,
            )
    except httpx.HTTPError as e:
        _logger.error("Error consultando MP (tipo=%s id=...%s): %s",
                      tipo, str(numero_op or "")[-6:], e)
        estado, mp_status_code = "ERROR_MP", None
    finally:
        try:
            await redis.srem(clave, numero_op)
        except RedisError:
            _logger.error("No se pudo liberar op pendiente de Redis (posible falso DUPLICADO futuro): ...%s", str(numero_op or "")[-6:])

    return estado, mp_status_code, numero_op
