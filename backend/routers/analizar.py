"""
Endpoint de análisis manual de un comprobante individual.

Recibe una imagen de un admin autenticado, la procesa en el momento
y persiste la validación en DB con canal='MANUAL'.

El resultado queda disponible en el dashboard junto al resto de validaciones.
"""
from typing import Annotated

import filetype
from config import config
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from routers.deps import AnalizarServiceDep, get_admin_actual

router = APIRouter(tags=["analizar"])

_TIPOS_IMAGEN_PERMITIDOS = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_MAX_BYTES = 10 * 1024 * 1024


@router.post("/analizar")
async def analizar_imagen_manual(
    archivo: Annotated[UploadFile, File(description="Imagen del comprobante (JPEG, PNG o WebP)")],
    codigo_cliente: Annotated[str, Form(description="Código de cliente del comprobante")],
    servicio_analizar: AnalizarServiceDep,
    admin: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    codigo_cliente_limpio = codigo_cliente.strip()
    if not codigo_cliente_limpio:
        raise HTTPException(status_code=422, detail="El código de cliente es obligatorio.")

    if archivo.content_type not in _TIPOS_IMAGEN_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Usá JPEG, PNG o WebP.",
        )

    imagen_bytes = await archivo.read()

    if len(imagen_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Imagen demasiado grande ({len(imagen_bytes) // 1024} KB). Máximo: 10 MB.",
        )

    # Validar MIME real leyendo los magic bytes — el content_type anterior
    # es declarado por el cliente y puede ser falso (MIME spoofing).
    tipo_real = filetype.guess(imagen_bytes)
    if tipo_real is None or tipo_real.mime not in _TIPOS_IMAGEN_PERMITIDOS:
        raise HTTPException(
            status_code=400,
            detail="El contenido del archivo no corresponde a una imagen válida (JPEG, PNG o WebP).",
        )

    return await servicio_analizar.analizar_y_guardar(
        imagen_bytes, tipo_real.mime, codigo_cliente_limpio,
        config.tenant_id, admin["sub"],
    )
