import uuid
from typing import Annotated

from config import config
from db.base import q
from db.queries_admins import (
    listar_admins,
    toggle_activo_admin,
    verificar_es_superadmin,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from routers.deps import AdminsServiceDep, Pool, get_superadmin_actual

router = APIRouter(prefix="/admins", tags=["admins"])


def _validar_uuid(id_str: str, detalle: str = "Recurso no encontrado.") -> None:
    try:
        uuid.UUID(id_str)
    except ValueError:
        raise HTTPException(status_code=404, detail=detalle)


class AdminResumen(BaseModel):
    id: str
    nombre: str
    email: str
    activo: bool
    es_superadmin: bool
    creado_en: str | None


class ToggleActivoRequest(BaseModel):
    activo: bool


@router.get("", response_model=list[AdminResumen])
async def listar(
    pool: Pool,
    admin_payload: Annotated[dict, Depends(get_superadmin_actual)],
) -> list[AdminResumen]:
    admins = await q(listar_admins, pool, config.tenant_id)
    return [AdminResumen(**a) for a in admins]


@router.patch("/{admin_id}/activo", response_model=AdminResumen)
async def actualizar_activo(
    admin_id: str,
    body: ToggleActivoRequest,
    pool: Pool,
    admin_payload: Annotated[dict, Depends(get_superadmin_actual)],
) -> AdminResumen:
    _validar_uuid(admin_id, "Admin no encontrado.")
    if admin_id == admin_payload["sub"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podés desactivarte a vos mismo.",
        )
    es_super = await q(verificar_es_superadmin, pool, config.tenant_id, admin_id)
    if es_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No podés modificar el estado de un superadmin.",
        )

    admin_actualizado = await q(toggle_activo_admin, pool, config.tenant_id, admin_id, body.activo)

    if admin_actualizado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin no encontrado.",
        )

    return AdminResumen(**admin_actualizado)


@router.delete("/datos-usuario")
async def eliminar_datos_usuario(
    telefono: Annotated[str, Query(min_length=7)],
    servicio_admins: AdminsServiceDep,
    admin_payload: Annotated[dict, Depends(get_superadmin_actual)],
) -> dict:
    return await servicio_admins.eliminar_datos_usuario(config.tenant_id, telefono, admin_payload["sub"])
