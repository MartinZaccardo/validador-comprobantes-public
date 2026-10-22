"""
Handlers que traducen excepciones de dominio a respuestas HTTP.

Registrar en main.py con app.add_exception_handler().
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from exceptions.exceptions import (
    ErrorSubidaImagen,
    EstadoNoReverificable,
    ValidacionNoEncontrada,
)


async def handler_error_subida_imagen(_request: Request, _exc: ErrorSubidaImagen) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Error interno al procesar la imagen"})


async def handler_validacion_no_encontrada(_request: Request, _exc: ValidacionNoEncontrada) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Validación no encontrada."})


async def handler_estado_no_reverificable(_request: Request, _exc: EstadoNoReverificable) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Solo se puede re-verificar un comprobante en estado 'Revisión manual' o 'N° op. no encontrado'."
        },
    )
