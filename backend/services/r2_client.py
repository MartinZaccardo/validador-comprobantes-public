"""
Cliente para Cloudflare R2 (object storage compatible con S3).

boto3 es síncrono — todas las operaciones públicas de este módulo son async
y delegan al ThreadPoolExecutor del event loop vía run_in_executor para no
bloquear el event loop durante transfers de red.
"""
import asyncio
import logging

import boto3
from botocore.config import Config as BotocoreConfig
from config import config

_logger = logging.getLogger(__name__)

_EXPIRACION_URL_SEGUNDOS = 3600  # presigned URLs válidas 1 hora


def _crear_cliente_r2():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=config.r2_access_key_id,
        aws_secret_access_key=config.r2_secret_access_key,
        config=BotocoreConfig(signature_version="s3v4"),
        region_name="auto",
    )


# Cliente boto3 compartido — thread-safe para operaciones de lectura/escritura.
_cliente = _crear_cliente_r2()


def _subir(key: str, imagen_bytes: bytes) -> None:
    _cliente.put_object(
        Bucket=config.r2_bucket_name,
        Key=key,
        Body=imagen_bytes,
    )


def _generar_url_firmada(key: str) -> str:
    return _cliente.generate_presigned_url(
        "get_object",
        Params={"Bucket": config.r2_bucket_name, "Key": key},
        ExpiresIn=_EXPIRACION_URL_SEGUNDOS,
    )


async def subir_imagen_async(key: str, imagen_bytes: bytes) -> None:
    """Sube imagen_bytes a R2 bajo la clave key. Lanza excepción si falla."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _subir, key, imagen_bytes)
    _logger.info(f"R2 upload OK: {key} ({len(imagen_bytes)} bytes)")


async def generar_url_firmada_async(key: str) -> str:
    """Devuelve una presigned URL válida por 1 hora para el objeto key."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _generar_url_firmada, key)


def _eliminar(key: str) -> None:
    _cliente.delete_object(Bucket=config.r2_bucket_name, Key=key)


async def eliminar_imagen_async(key: str) -> None:
    """Elimina el objeto key de R2. Lanza excepción si falla."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _eliminar, key)
    _logger.info("R2 delete OK: %s", key)
