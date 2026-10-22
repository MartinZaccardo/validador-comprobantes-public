import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Annotated

import psycopg2.errors
from db import queries_clientes, queries_validaciones
from db.base import q
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from routers.deps import Pool, get_admin_actual

router = APIRouter(prefix="/clientes", tags=["clientes"])

_MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB
_CSV_FORMULA_CHARS = ("=", "+", "-", "@", "|", "\t", "\r")


def _validar_uuid(id_str: str, detalle: str = "Recurso no encontrado.") -> None:
    try:
        uuid.UUID(id_str)
    except ValueError:
        raise HTTPException(status_code=404, detail=detalle)


def _sanitizar_campo_csv(valor: object) -> str:
    """Previene CSV injection: prefija con comilla simple campos que Excel interpretaría como fórmula."""
    texto = str(valor) if valor is not None else ""
    if texto and texto[0] in _CSV_FORMULA_CHARS:
        return "'" + texto
    return texto


class ClienteResumen(BaseModel):
    id: str
    codigo_cliente: str
    razon_social: str
    direccion: str | None
    activo: bool
    creado_en: str | None


class TelefonoItem(BaseModel):
    id: str
    telefono: str


class CuitItem(BaseModel):
    id: str
    cuit: str


class ClienteDetalle(ClienteResumen):
    telefonos: list[TelefonoItem]
    cuits: list[CuitItem]


class ClientesPaginadosResponse(BaseModel):
    items: list[ClienteResumen]
    total: int


class ClienteSinActividad(BaseModel):
    id: str
    codigo_cliente: str
    razon_social: str
    ultimo_comprobante: str | None


class CrearClienteRequest(BaseModel):
    codigo_cliente: str
    razon_social: str
    direccion: str | None = None


class ActualizarClienteRequest(BaseModel):
    razon_social: str | None = None
    direccion: str | None = None
    activo: bool | None = None


class AgregarTelefonoRequest(BaseModel):
    telefono: str


class AgregarCuitRequest(BaseModel):
    cuit: str


class PreviewImportacion(BaseModel):
    total_csv: int
    filas_invalidas: int
    nuevos: int
    con_cambios: int
    sin_cambios: int


class ResultadoImportacion(BaseModel):
    insertados: int
    actualizados: int
    errores: list[str]


class ValidacionClienteResumen(BaseModel):
    id: str
    estado: str
    identificador_pago: str | None
    monto_detectado: float | None
    procesado_en: str | None
    canal: str
    entidad_emisora: str | None
    codigo_cliente: str | None
    imagen_path: str | None


def _analizar_csv(contenido: str) -> tuple[list[dict], int]:
    """
    Parsea el CSV y retorna (clientes_validos, filas_invalidas).
    Una fila es inválida si le falta codigo_cliente o razon_social.
    Formato de columnas provisional — ajustar al CSV oficial del cliente.
    """
    reader = csv.DictReader(io.StringIO(contenido))
    clientes: list[dict] = []
    filas_invalidas = 0
    for fila in reader:
        codigo = fila.get("codigo_cliente", "").strip()
        razon = fila.get("razon_social", "").strip()
        if not codigo or not razon:
            filas_invalidas += 1
            continue
        telefonos = [t.strip().lstrip("+") for t in (fila.get("telefonos") or "").split(";") if t.strip()]
        cuits = [c.strip() for c in (fila.get("cuits") or "").split(";") if c.strip()]
        clientes.append({
            "codigo_cliente": codigo,
            "razon_social": razon,
            "direccion": fila.get("direccion", "").strip() or None,
            "telefonos": telefonos,
            "cuits": cuits,
        })
    return clientes, filas_invalidas


def _parsear_csv(contenido: str) -> list[dict]:
    clientes, _ = _analizar_csv(contenido)
    return clientes


AdminDep = Annotated[dict, Depends(get_admin_actual)]


@router.get("", response_model=ClientesPaginadosResponse)
async def listar(
    pool: Pool,
    _: AdminDep,
    texto: str | None = Query(default=None, alias="q", min_length=1, max_length=100),
    solo_activos: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ClientesPaginadosResponse:
    resultado = await q(queries_clientes.listar_clientes, pool, texto, solo_activos, page, page_size)
    return ClientesPaginadosResponse(
        items=[ClienteResumen(**c) for c in resultado["items"]],
        total=resultado["total"],
    )


@router.get("/sin-actividad", response_model=list[ClienteSinActividad])
async def sin_actividad(
    pool: Pool,
    _: AdminDep,
    dias: int = Query(default=7, ge=1),
) -> list[ClienteSinActividad]:
    clientes = await q(queries_clientes.listar_clientes_sin_actividad, pool, dias)
    return [ClienteSinActividad(**c) for c in clientes]


@router.get("/sin-comprobantes", response_model=list[ClienteSinActividad])
async def sin_comprobantes(
    pool: Pool,
    _: AdminDep,
) -> list[ClienteSinActividad]:
    clientes = await q(queries_clientes.listar_clientes_sin_comprobantes, pool)
    return [ClienteSinActividad(**c) for c in clientes]


@router.get("/exportar")
async def exportar_csv(
    pool: Pool,
    _: AdminDep,
) -> Response:
    clientes = await q(queries_clientes.exportar_clientes, pool)
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(["codigo_cliente", "razon_social", "direccion", "telefonos", "cuits"])
    for c in clientes:
        writer.writerow([
            _sanitizar_campo_csv(c["codigo_cliente"]),
            _sanitizar_campo_csv(c["razon_social"]),
            _sanitizar_campo_csv(c["direccion"]),
            _sanitizar_campo_csv(c["telefonos"]),
            _sanitizar_campo_csv(c["cuits"]),
        ])
    filename = f"clientes_{datetime.now(tz=timezone.utc).date().isoformat()}.csv"
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/buscar", response_model=list[ClienteResumen])
async def buscar(
    pool: Pool,
    _: AdminDep,
    texto: str = Query(alias="q", min_length=2, max_length=100),
) -> list[ClienteResumen]:
    resultados = await q(queries_clientes.buscar_clientes, pool, texto)
    return [ClienteResumen(**c) for c in resultados]


@router.get("/{cliente_id}/validaciones", response_model=list[ValidacionClienteResumen])
async def listar_validaciones_de_cliente(
    cliente_id: str,
    pool: Pool,
    _: AdminDep,
) -> list[ValidacionClienteResumen]:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    validaciones = await q(
        queries_validaciones.listar_validaciones_por_cliente, pool, cliente_id
    )
    return [ValidacionClienteResumen(**v) for v in validaciones]


@router.get("/{cliente_id}", response_model=ClienteDetalle)
async def obtener(
    cliente_id: str,
    pool: Pool,
    _: AdminDep,
) -> ClienteDetalle:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    cliente = await q(queries_clientes.obtener_cliente_con_detalle, pool, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")
    return ClienteDetalle(**cliente)


@router.post("", response_model=ClienteDetalle, status_code=status.HTTP_201_CREATED)
async def crear(
    body: CrearClienteRequest,
    pool: Pool,
    _: AdminDep,
) -> ClienteDetalle:
    try:
        cliente_id = await q(
            queries_clientes.crear_cliente, pool,
            body.codigo_cliente, body.razon_social, body.direccion,
        )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un cliente con el código '{body.codigo_cliente}'. Usá un código distinto o editá el cliente existente.",
        )
    cliente = await q(queries_clientes.obtener_cliente_con_detalle, pool, cliente_id)
    return ClienteDetalle(**cliente)


@router.patch("/{cliente_id}", response_model=ClienteResumen)
async def actualizar(
    cliente_id: str,
    body: ActualizarClienteRequest,
    pool: Pool,
    _: AdminDep,
) -> ClienteResumen:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    if body.razon_social is None and body.direccion is None and body.activo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere al menos un campo para actualizar.",
        )
    cliente = await q(
        queries_clientes.actualizar_cliente, pool,
        cliente_id, body.razon_social, body.direccion, body.activo,
    )
    if cliente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado.")
    return ClienteResumen(**cliente)


@router.post("/{cliente_id}/telefonos", response_model=TelefonoItem, status_code=status.HTTP_201_CREATED)
async def agregar_telefono(
    cliente_id: str,
    body: AgregarTelefonoRequest,
    pool: Pool,
    _: AdminDep,
) -> TelefonoItem:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    try:
        telefono = await q(queries_clientes.agregar_telefono, pool, cliente_id, body.telefono)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El teléfono '{body.telefono}' ya está asociado a un cliente.",
        )
    return TelefonoItem(**telefono)


@router.delete("/{cliente_id}/telefonos/{telefono_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_telefono(
    cliente_id: str,
    telefono_id: str,
    pool: Pool,
    _: AdminDep,
) -> None:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    _validar_uuid(telefono_id, "Teléfono no encontrado.")
    eliminado = await q(queries_clientes.eliminar_telefono, pool, telefono_id, cliente_id)
    if not eliminado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teléfono no encontrado.")


@router.post("/{cliente_id}/cuits", response_model=CuitItem, status_code=status.HTTP_201_CREATED)
async def agregar_cuit(
    cliente_id: str,
    body: AgregarCuitRequest,
    pool: Pool,
    _: AdminDep,
) -> CuitItem:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    try:
        cuit = await q(queries_clientes.agregar_cuit, pool, cliente_id, body.cuit)
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El CUIT '{body.cuit}' ya está asociado a un cliente.",
        )
    return CuitItem(**cuit)


@router.delete("/{cliente_id}/cuits/{cuit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cuit(
    cliente_id: str,
    cuit_id: str,
    pool: Pool,
    _: AdminDep,
) -> None:
    _validar_uuid(cliente_id, "Cliente no encontrado.")
    _validar_uuid(cuit_id, "CUIT no encontrado.")
    eliminado = await q(queries_clientes.eliminar_cuit, pool, cuit_id, cliente_id)
    if not eliminado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CUIT no encontrado.")


@router.post("/importar/preview", response_model=PreviewImportacion, status_code=status.HTTP_200_OK)
async def preview_importar_csv(
    pool: Pool,
    _: AdminDep,
    archivo: Annotated[UploadFile, File()],
) -> PreviewImportacion:
    if not archivo.filename or not archivo.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un CSV (.csv).",
        )
    contenido_bytes = await archivo.read()
    if len(contenido_bytes) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo CSV es demasiado grande (máximo 5 MB).",
        )
    try:
        contenido = contenido_bytes.decode("utf-8")
    except UnicodeDecodeError:
        contenido = contenido_bytes.decode("latin-1")

    clientes, filas_invalidas = _analizar_csv(contenido)
    if not clientes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El CSV no contiene filas válidas (verificá que tenga las columnas codigo_cliente y razon_social).",
        )
    resultado = await q(queries_clientes.preview_importacion, pool, clientes)
    return PreviewImportacion(
        total_csv=len(clientes),
        filas_invalidas=filas_invalidas,
        **resultado,
    )


@router.post("/importar", response_model=ResultadoImportacion, status_code=status.HTTP_200_OK)
async def importar_csv(
    pool: Pool,
    _: AdminDep,
    archivo: Annotated[UploadFile, File()],
) -> ResultadoImportacion:
    if not archivo.filename or not archivo.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un CSV (.csv).",
        )
    contenido_bytes = await archivo.read()
    if len(contenido_bytes) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo CSV es demasiado grande (máximo 5 MB).",
        )
    try:
        contenido = contenido_bytes.decode("utf-8")
    except UnicodeDecodeError:
        contenido = contenido_bytes.decode("latin-1")

    clientes = _parsear_csv(contenido)
    if not clientes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El CSV no contiene filas válidas (verificá que tenga las columnas codigo_cliente y razon_social).",
        )
    resultado = await q(queries_clientes.importar_clientes, pool, clientes)
    return ResultadoImportacion(**resultado)
