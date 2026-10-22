from typing import Annotated

from config import config
from db.base import q
from db.queries_validaciones import obtener_metricas
from fastapi import APIRouter, Depends, Query

from routers.deps import Pool, get_admin_actual

router = APIRouter(tags=["metricas"])


@router.get("/metricas")
async def metricas(
    pool: Pool,
    _admin: Annotated[dict, Depends(get_admin_actual)],
    fecha_desde: str | None = Query(default=None, description="YYYY-MM-DD"),
    fecha_hasta: str | None = Query(default=None, description="YYYY-MM-DD"),
) -> dict:
    return await q(obtener_metricas, pool, config.tenant_id, fecha_desde, fecha_hasta)
