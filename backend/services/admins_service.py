"""
Lógica de negocio de administración.

Los routers delegan acá. Este módulo no importa FastAPI.
"""
import asyncio
import logging

import psycopg2.pool
from db.base import q
from db.queries_validaciones import eliminar_datos_telefono

from services.r2_client import eliminar_imagen_async

_logger = logging.getLogger(__name__)


class AdminsService:
    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool) -> None:
        self.pool = pool

    async def eliminar_datos_usuario(
        self,
        tenant_id: str,
        telefono: str,
        admin_id: str,
    ) -> dict:
        cantidad, imagen_paths = await q(
            eliminar_datos_telefono, self.pool, tenant_id, telefono
        )

        if imagen_paths:
            resultados = await asyncio.gather(
                *[eliminar_imagen_async(path) for path in imagen_paths],
                return_exceptions=True,
            )
            errores_r2 = sum(1 for resultado in resultados if isinstance(resultado, Exception))
            if errores_r2:
                _logger.warning(
                    "eliminar_datos_usuario: %d/%d imágenes R2 no pudieron borrarse (admin=%s)",
                    errores_r2, len(imagen_paths), admin_id,
                )

        _logger.info(
            "eliminar_datos_usuario: %d validaciones eliminadas (admin=%s)",
            cantidad, admin_id,
        )
        return {"eliminadas": cantidad, "imagenes_eliminadas": len(imagen_paths)}
