import logging

import redis.asyncio as aioredis
from config import config

_logger = logging.getLogger(__name__)
_cliente_redis: aioredis.Redis | None = None

async def crear_cliente_redis() -> None:
    """
    Inicializa el cliente Redis. Llamar una sola vez al arrancar.

    Sin REDIS_URL en producción (secure_cookies=True) falla rápido.
    Sin REDIS_URL en dev local usa fakeredis: pub/sub funciona dentro del proceso,
    sin necesidad de levantar un servidor Redis real.
    """
    global _cliente_redis
    if not config.redis_url:
        if config.secure_cookies:
            raise RuntimeError("REDIS_URL es obligatorio en producción")
        import fakeredis.aioredis
        _cliente_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        _logger.warning("[redis] REDIS_URL no configurado — usando fakeredis (solo dev local)")
        return
    _cliente_redis = aioredis.Redis.from_url(config.redis_url, decode_responses=True)
    await _cliente_redis.ping()
    _logger.info("[redis] Conexión establecida")


async def cerrar_cliente_redis() -> None:
    if _cliente_redis:
        await _cliente_redis.aclose()
        _logger.info("[redis] Conexión cerrada")


def get_cliente_redis() -> aioredis.Redis:
    if _cliente_redis is None:
        raise RuntimeError("Redis no inicializado. ¿Se llamó crear_cliente_redis()?")
    return _cliente_redis


def clave_ops_pendientes(tenant_id: str) -> str:
    """Clave del Set Redis de operaciones en vuelo (anti-duplicados cross-canal)."""
    return f"ops_pendientes:{tenant_id}"


def clave_canal_validaciones(tenant_id: str) -> str:
    """Canal Pub/Sub Redis para notificar al SSE endpoint cuando se guarda una validación."""
    return f"validaciones:{tenant_id}"
