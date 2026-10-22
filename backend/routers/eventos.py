import asyncio
import time
from typing import Annotated

from config import config
from db.redis import clave_canal_validaciones, get_cliente_redis
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from routers.deps import get_admin_actual

router = APIRouter()

_HEARTBEAT_INTERVALO_SEGUNDOS = 15


@router.get("/eventos")
async def eventos(
    _admin: Annotated[dict, Depends(get_admin_actual)],
) -> StreamingResponse:
    """
    Endpoint SSE: el browser se suscribe aquí y recibe eventos tipados cuando
    se guarda una validación nueva (cualquier canal: WhatsApp o manual).

    Tipos de evento:
      event: validacion  →  validación guardada
    """
    canal_validaciones = clave_canal_validaciones(config.tenant_id)

    async def generar_eventos():
        redis = get_cliente_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(canal_validaciones)
        ultimo_heartbeat = time.monotonic()
        try:
            while True:
                mensaje = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                ahora = time.monotonic()
                if mensaje:
                    yield "event: validacion\ndata: {}\n\n"
                    ultimo_heartbeat = ahora
                elif ahora - ultimo_heartbeat >= _HEARTBEAT_INTERVALO_SEGUNDOS:
                    yield ": heartbeat\n\n"
                    ultimo_heartbeat = ahora
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(canal_validaciones)
            await pubsub.aclose()

    return StreamingResponse(
        generar_eventos(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # deshabilita buffering en nginx/Railway
        },
    )
