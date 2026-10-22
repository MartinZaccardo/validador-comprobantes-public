"""
Lógica de negocio del análisis manual de comprobantes.

Los routers delegan acá. Este módulo no importa FastAPI.
La lógica de validación (MP, duplicados) vive en validacion_core.
"""
import logging
import uuid

import psycopg2
import psycopg2.pool
import redis.asyncio as aioredis
from config import config
from db import queries_clientes, queries_validaciones
from db.base import q
from db.redis import clave_canal_validaciones
from exceptions.exceptions import ErrorSubidaImagen
from models.resultado import CanalOrigen
from redis.exceptions import RedisError

from services.ocr import procesar_imagen
from services.r2_client import subir_imagen_async
from services.validacion_core import determinar_estado

_logger = logging.getLogger(__name__)

EXT_POR_MIME: dict[str, str] = {
    "image/jpeg":      ".jpg",
    "image/jpg":       ".jpg",
    "image/png":       ".png",
    "image/webp":      ".webp",
    "application/pdf": ".pdf",
}


class AnalizarService:
    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool, redis: aioredis.Redis) -> None:
        self.pool = pool
        self.redis = redis

    async def analizar_y_guardar(
        self,
        imagen_bytes: bytes,
        mime_type: str,
        codigo_cliente: str,
        tenant_id: str,
        admin_id: str,
    ) -> dict:
        resultado_ocr = await procesar_imagen(imagen_bytes, CanalOrigen.MANUAL)
        ops_aprobadas = await self._obtener_ops_aprobadas(tenant_id)
        estado, mp_status_code, identificador_final = await determinar_estado(
            resultado_ocr, ops_aprobadas, self.redis
        )

        validacion_id = str(uuid.uuid4())
        r2_key = f"uploads/{tenant_id}/{validacion_id}{EXT_POR_MIME.get(mime_type, '.jpg')}"

        try:
            await subir_imagen_async(r2_key, imagen_bytes)
        except Exception as e:  # noqa: BLE001
            _logger.error("Error al subir imagen a R2 (analizar): %s", e)
            raise ErrorSubidaImagen()

        if codigo_cliente:
            vinculado = await q(queries_clientes.obtener_cliente_por_codigo, self.pool, codigo_cliente)
            cliente_id_vinculado = vinculado["id"] if vinculado else None
        elif resultado_ocr and resultado_ocr.cuit_remitente:
            cliente_id_vinculado, _ = await q(
                queries_clientes.resolver_cliente_para_vinculacion,
                self.pool, resultado_ocr.cuit_remitente,
            )
        else:
            cliente_id_vinculado = None

        resultado = await q(
            queries_validaciones.guardar_validacion_manual,
            self.pool,
            validacion_id,
            tenant_id,
            codigo_cliente,
            estado,
            identificador_final,
            resultado_ocr.monto_detectado,
            resultado_ocr.cuit_destinatario_detectado,
            resultado_ocr.es_comprobante_valido,
            mp_status_code,
            r2_key,
            resultado_ocr=resultado_ocr,
            creado_por_admin_id=admin_id,
            cliente_id=cliente_id_vinculado,
        )
        try:
            await self.redis.publish(clave_canal_validaciones(config.tenant_id), "1")
        except RedisError:
            _logger.warning("No se pudo publicar validación manual en Redis")
        return resultado

    async def _obtener_ops_aprobadas(self, tenant_id: str) -> set[str]:
        try:
            return await q(queries_validaciones.obtener_ops_aprobadas, self.pool, tenant_id)
        except psycopg2.Error as e:
            _logger.warning("No se pudieron cargar ops_aprobadas (analizar): %s", e)
            return set()
