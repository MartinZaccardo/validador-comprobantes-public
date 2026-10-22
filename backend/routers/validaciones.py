"""
Endpoints de validaciones individuales.
"""
import logging
import uuid
from typing import Annotated

import filetype
from config import config
from db import queries_validaciones
from db.base import q
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from limiter import limiter
from pydantic import BaseModel, field_validator, model_validator
from services.r2_client import generar_url_firmada_async, subir_imagen_async

from routers.deps import Pool, ValidacionesServiceDep, get_admin_actual

router = APIRouter(tags=["validaciones"])

_logger = logging.getLogger(__name__)

_ESTADOS_VALIDOS = {
    "APROBADO", "DUPLICADO", "MONTO_ADULTERADO", "PAGO_NO_ACREDITADO",
    "REVISION_MANUAL", "NUMERO_OP_NO_ENCONTRADO",
    "ERROR_DESTINATARIO", "IMAGEN_INVALIDA", "ERROR_MP",
}

_CANALES_VALIDOS = {"MANUAL", "WhatsApp"}

_TIPOS_IMAGEN_PERMITIDOS = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_MAX_BYTES = 10 * 1024 * 1024
_EXT_POR_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg":  ".jpg",
    "image/png":  ".png",
    "image/webp": ".webp",
}


@router.get("/validaciones")
async def listar_validaciones(
    pool: Pool,
    _admin: Annotated[dict, Depends(get_admin_actual)],
    estado: str | None = Query(default=None),
    canal: str | None = Query(default=None),
    fecha_desde: str | None = Query(default=None, description="YYYY-MM-DD"),
    fecha_hasta: str | None = Query(default=None, description="YYYY-MM-DD"),
    fecha_mod_desde: str | None = Query(default=None, description="YYYY-MM-DD"),
    fecha_mod_hasta: str | None = Query(default=None, description="YYYY-MM-DD"),
    codigo_cliente: str | None = Query(default=None),
    numero_operacion: str | None = Query(default=None),
    usuario: str | None = Query(default=None),
    entidad_emisora: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=2500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    if estado and estado not in _ESTADOS_VALIDOS:
        raise HTTPException(status_code=400, detail="Estado no reconocido.")
    if canal and canal not in _CANALES_VALIDOS:
        raise HTTPException(status_code=400, detail="Canal no reconocido.")

    return await q(
        queries_validaciones.listar_validaciones,
        pool, config.tenant_id,
        estado=estado, canal=canal,
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        fecha_mod_desde=fecha_mod_desde, fecha_mod_hasta=fecha_mod_hasta,
        codigo_cliente=codigo_cliente, numero_operacion=numero_operacion, modificado_por=usuario,
        entidad_emisora=entidad_emisora,
        limit=limit, offset=offset,
    )


@router.get("/validaciones/bancos")
async def listar_bancos(
    pool: Pool,
    _admin: Annotated[dict, Depends(get_admin_actual)],
) -> list[str]:
    return await q(queries_validaciones.obtener_entidades_emisoras, pool, config.tenant_id)


@router.get("/validaciones/{validacion_id}")
async def obtener_validacion(
    validacion_id: str,
    pool: Pool,
    _admin: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    """Devuelve el detalle de una validación por ID."""
    try:
        uuid.UUID(validacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    validacion = await q(queries_validaciones.obtener_validacion_por_id, pool, validacion_id, config.tenant_id)
    if validacion is None:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")
    return validacion


# ---------------------------------------------------------------------------
# Re-verificación manual
# ---------------------------------------------------------------------------

class ReverificarBody(BaseModel):
    """
    Body del POST /api/validaciones/{id}/reverificar.

    numero_operacion: el número corregido por el operador.
    Pydantic valida automáticamente que el campo existe y es string no vacío.
    FastAPI devuelve 422 si el JSON está mal formado o falta el campo.
    """
    numero_operacion: str

    @field_validator("numero_operacion")
    @classmethod
    def formato_valido(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("numero_operacion no puede estar vacío")
        if not v.isdigit():
            raise ValueError("numero_operacion debe contener solo dígitos")
        if len(v) > 20:
            raise ValueError("numero_operacion excede la longitud máxima (20 dígitos)")
        return v


@router.post("/validaciones/{validacion_id}/reverificar")
@limiter.limit("20/minute")
async def reverificar(
    request: Request,
    validacion_id: str,
    body: ReverificarBody,
    servicio_validaciones: ValidacionesServiceDep,
    _admin: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    try:
        uuid.UUID(validacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    return await servicio_validaciones.reverificar(config.tenant_id, validacion_id, body.numero_operacion)


# ---------------------------------------------------------------------------
# Edición manual por admin (sin llamar a MP)
# ---------------------------------------------------------------------------

class EditarValidacionBody(BaseModel):
    """
    Body del PATCH /api/validaciones/{id}.

    Todos los campos son opcionales, pero al menos uno debe estar presente.
    El admin puede cambiar cualquier combinación de los tres campos.
    observaciones: None = no tocar, "" = borrar, "texto" = actualizar.
    """
    numero_operacion: str | None = None
    estado: str | None = None
    observaciones: str | None = None
    _actualizar_observaciones: bool = False

    @model_validator(mode="after")
    def al_menos_un_campo(self) -> "EditarValidacionBody":
        if self.numero_operacion is None and self.estado is None and self.observaciones is None:
            raise ValueError("Debés especificar al menos un campo para actualizar")
        if self.numero_operacion is not None:
            self.numero_operacion = self.numero_operacion.strip()
            if not self.numero_operacion:
                raise ValueError("numero_operacion no puede ser una cadena vacía")
            if not self.numero_operacion.isdigit():
                raise ValueError("numero_operacion debe contener solo dígitos")
            if len(self.numero_operacion) > 20:
                raise ValueError("numero_operacion excede la longitud máxima (20 dígitos)")
        return self


@router.patch("/validaciones/{validacion_id}")
async def editar_validacion(
    validacion_id: str,
    body: EditarValidacionBody,
    servicio_validaciones: ValidacionesServiceDep,
    admin: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    try:
        uuid.UUID(validacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    if body.estado and body.estado not in _ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail="Estado no reconocido.",
        )

    return await servicio_validaciones.editar(
        config.tenant_id, validacion_id,
        body.numero_operacion, body.estado, body.observaciones, admin["sub"],
    )


# ---------------------------------------------------------------------------
# Eliminación
# ---------------------------------------------------------------------------

@router.delete("/validaciones/{validacion_id}", status_code=204)
async def eliminar_validacion(
    validacion_id: str,
    pool: Pool,
    admin: Annotated[dict, Depends(get_admin_actual)],
) -> None:
    """
    Soft-delete de una validación: marca eliminado_en/eliminado_por y registra en auditoría.
    La imagen en R2 se preserva para eventual recuperación.
    """
    try:
        uuid.UUID(validacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    encontrada = await q(
        queries_validaciones.eliminar_validacion,
        pool, validacion_id, config.tenant_id, admin["sub"],
    )

    if not encontrada:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")


# ---------------------------------------------------------------------------
# Imagen de validaciones
# ---------------------------------------------------------------------------

@router.get("/validaciones/{validacion_id}/imagen")
async def obtener_imagen_validacion(
    validacion_id: str,
    pool: Pool,
    _admin: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    """
    Devuelve una presigned URL de R2 para que el frontend cargue la imagen.

    Aplica a validaciones que tengan imagen_path en DB.
    El JWT se valida aquí. El frontend usa la URL directamente como <img src>,
    lo que evita CORS — los tags <img> no disparan preflight cross-origin.
    """
    try:
        uuid.UUID(validacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    validacion = await q(queries_validaciones.obtener_validacion_por_id, pool, validacion_id, config.tenant_id)
    if validacion is None:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    if not validacion.get("imagen_path"):
        raise HTTPException(
            status_code=404,
            detail="Esta validación no tiene imagen asociada",
        )

    url_firmada = await generar_url_firmada_async(validacion["imagen_path"])
    return {"url": url_firmada}


@router.patch("/validaciones/{validacion_id}/imagen")
async def reemplazar_imagen_validacion(
    validacion_id: str,
    imagen: Annotated[UploadFile, File(description="Nueva imagen del comprobante (JPEG, PNG o WebP)")],
    pool: Pool,
    admin: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    """
    Reemplaza (o agrega por primera vez) la imagen de una validación existente.

    Sube la nueva imagen a R2 y actualiza imagen_path en DB.
    Si la extensión cambia, el objeto anterior en R2 queda huérfano — aceptable
    al volumen actual.
    """
    try:
        uuid.UUID(validacion_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    if imagen.content_type not in _TIPOS_IMAGEN_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Usá JPEG, PNG o WebP.",
        )

    imagen_bytes = await imagen.read()

    if len(imagen_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Imagen demasiado grande ({len(imagen_bytes) // 1024} KB). Máximo: 10 MB.",
        )

    tipo_real = filetype.guess(imagen_bytes)
    if tipo_real is None or tipo_real.mime not in _TIPOS_IMAGEN_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail="El contenido del archivo no corresponde a una imagen válida (JPEG, PNG o WebP).",
        )

    validacion = await q(queries_validaciones.obtener_validacion_por_id, pool, validacion_id, config.tenant_id)
    if validacion is None:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    # Extensión del objeto R2 basada en el MIME verificado (filetype.guess),
    # no en imagen.filename ni content_type (ambos son user-controlled).
    ext = _EXT_POR_MIME.get(tipo_real.mime, ".jpg")
    nueva_imagen_path = f"uploads/{config.tenant_id}/{validacion_id}{ext}"

    try:
        await subir_imagen_async(nueva_imagen_path, imagen_bytes)
    except Exception as e:  # noqa: BLE001
        _logger.error("Error al subir imagen a R2 (validaciones): %s", e)
        raise HTTPException(status_code=500, detail="Error interno al procesar la imagen")

    encontrada = await q(
        queries_validaciones.actualizar_imagen_validacion,
        pool, validacion_id, config.tenant_id, nueva_imagen_path,
    )
    if not encontrada:
        raise HTTPException(status_code=404, detail="Validación no encontrada.")

    await q(
        queries_validaciones.guardar_auditoria,
        pool, admin["sub"], validacion_id,
        "imagen_path",
        validacion.get("imagen_path") or "",
        nueva_imagen_path,
    )

    validacion_actualizada = await q(queries_validaciones.obtener_validacion_por_id, pool, validacion_id, config.tenant_id)
    return validacion_actualizada
