import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg2
import secure
import sentry_sdk
from config import config
from db import queries_whatsapp as queries_wpp
from db.connection import cerrar_pool, crear_pool, get_pool
from db.redis import cerrar_cliente_redis, crear_cliente_redis, get_cliente_redis
from exceptions import (
    ErrorSubidaImagen,
    EstadoNoReverificable,
    ValidacionNoEncontrada,
    handler_error_subida_imagen,
    handler_estado_no_reverificable,
    handler_validacion_no_encontrada,
)
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from limiter import limiter
from routers import (
    admins,
    analizar,
    auth,
    clientes,
    eventos,
    metricas,
    validaciones,
    whatsapp,
)
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from services.ocr import pre_cargar_easyocr
from services.whatsapp_service import WhatsAppService
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        max_request_body_size="never",   # no enviar cuerpos de request (passwords, datos de pago)
        include_local_variables=False,   # no enviar variables locales (imagen_bytes, teléfonos, CBU)
    )

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_pool()
    await crear_cliente_redis()

    if config.secure_cookies and not config.whatsapp_app_secret:
        _logger.warning(
            "[startup] WHATSAPP_APP_SECRET vacío en producción — "
            "validación de firma webhook Meta deshabilitada"
        )

    try:
        pendientes = queries_wpp.obtener_mensajes_pendientes(get_pool(), config.tenant_id)
        if pendientes:
            _logger.warning("[startup] %d mensaje(s) WhatsApp pendiente(s) — reencolando", len(pendientes))
            servicio_recuperacion = WhatsAppService(get_pool(), get_cliente_redis())
            for msg in pendientes:
                asyncio.create_task(
                    servicio_recuperacion.procesar_mensaje(msg["numero_remitente"], msg["media_id"])
                )
    except psycopg2.Error as e:
        _logger.error(f"[startup] No se pudo recuperar mensajes WhatsApp pendientes: {e}")

    # Pre-warm en background: no bloquea el startup ni el healthcheck de Railway.
    # El primer request OCR puede ser lento si llega antes de que terminen de cargar.
    async def _pre_cargar_con_logging() -> None:
        try:
            await asyncio.to_thread(pre_cargar_easyocr)
        except Exception:
            _logger.exception("[startup] Falló pre-carga de EasyOCR — OCR fallback sin EasyOCR")

    asyncio.create_task(_pre_cargar_con_logging())

    yield

    cerrar_pool()
    await cerrar_cliente_redis()


app = FastAPI(
    title="Validador de Comprobantes",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if config.secure_cookies else "/docs",
    redoc_url=None if config.secure_cookies else "/redoc",
    openapi_url=None if config.secure_cookies else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(ValidacionNoEncontrada, handler_validacion_no_encontrada)
app.add_exception_handler(EstadoNoReverificable, handler_estado_no_reverificable)
app.add_exception_handler(ErrorSubidaImagen, handler_error_subida_imagen)

_secure_headers = secure.Secure(
    server=secure.Server(),
    hsts=secure.StrictTransportSecurity(),
    xfo=secure.XFrameOptions(),
    xcto=secure.XContentTypeOptions(),
    referrer=secure.ReferrerPolicy(),
    csp=(
        secure.ContentSecurityPolicy()
        .default_src("'self'")
        .script_src("'self'")
        .style_src("'self'", "'unsafe-inline'")
        .img_src("'self'", "data:", "blob:", f"https://{config.r2_account_id}.r2.cloudflarestorage.com")
        .font_src("'self'")
        .connect_src("'self'")
        .object_src("'none'")
        .base_uri("'self'")
        .frame_ancestors("'none'")
        .form_action("'self'")
    ),
)


@app.middleware("http")
async def agregar_security_headers(request: Request, call_next):
    response = await call_next(request)
    await _secure_headers.set_headers_async(response)
    return response


@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(validaciones.router, prefix="/api")
app.include_router(analizar.router, prefix="/api")
app.include_router(admins.router, prefix="/api")
app.include_router(metricas.router, prefix="/api")
app.include_router(eventos.router, prefix="/api")
app.include_router(whatsapp.router)
app.include_router(clientes.router, prefix="/api")

frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    _frontend_dist_real = frontend_dist.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        archivo = (frontend_dist / full_path).resolve()
        if archivo.is_relative_to(_frontend_dist_real) and archivo.is_file():
            return FileResponse(str(archivo))
        return FileResponse(str(frontend_dist / "index.html"))
