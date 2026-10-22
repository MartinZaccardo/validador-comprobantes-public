import os
from dataclasses import dataclass

from dotenv import load_dotenv

# El .env vive en la raíz del proyecto (un nivel arriba de backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


@dataclass
class Config:
    # --- Mercado Pago ---
    mp_access_token: str
    cuit_destinatario: str

    # --- Base de datos ---
    database_url: str          # asyncpg DSN: postgresql://user:pass@host/db
    database_url_sync: str     # SQLAlchemy DSN para Alembic: postgresql+psycopg2://...

    # --- Aplicación ---
    tenant_id: str             # Identificador del tenant (hardcodeado en .env)
    api_key: str               # Clave que el frontend envía en X-API-Key
    keywords_ocr: list[str]    # Palabras clave para validar comprobante por Tesseract

    # --- Autenticación de admins ---
    jwt_secret_key: str        # Clave secreta para firmar/verificar JWTs
    jwt_algorithm: str         # Algoritmo de firma (HS256 por defecto)
    secure_cookies: bool       # True en prod (HTTPS), False en dev local (HTTP)

    # --- Rate limiting ---
    rate_limit_login: str      # Formato slowapi: "5/minute", "100/hour", etc.

    # --- Observabilidad ---
    sentry_dsn: str            # Vacío → Sentry desactivado (local dev)

    # --- Cloudflare R2 ---
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str

    # --- WhatsApp (Meta Cloud API) ---
    whatsapp_token: str           # Token de acceso (temporal 24h o permanente de System User)
    whatsapp_phone_number_id: str # ID numérico del número de teléfono en Meta
    whatsapp_verify_token: str    # String secreto para verificar el webhook
    whatsapp_app_secret: str      # App Secret de Meta — para validar firma X-Hub-Signature-256

    # --- Redis (anti-duplicados, SSE Pub/Sub) ---
    redis_url: str                # Vacío → Redis desactivado (dev local sin Redis)

    # --- Vision LLM (Gemini) ---
    gemini_api_key: str           # Vacío → LLM desactivado, cae a Tesseract
    llm_habilitado: bool          # Flag de emergencia — desactivar sin redesplegar
    llm_timeout_whatsapp_segundos: float   # Límite duro: Meta espera < 20s
    llm_reintentos_whatsapp: int
    tesseract_timeout_whatsapp_segundos: float
    llm_timeout_manual_segundos: float     # Carga manual — sin límite percibido
    llm_reintentos_manual: int
    tesseract_timeout_manual_segundos: float


def _cargar_config() -> Config:
    def requerir(nombre: str) -> str:
        valor = os.getenv(nombre, "").strip()
        if not valor:
            raise ValueError(f"{nombre} no configurada. Ver .env.example")
        return valor

    def _requerir_minimo(nombre: str, minimo: int) -> str:
        valor = requerir(nombre)
        if len(valor) < minimo:
            raise ValueError(
                f"{nombre} debe tener al menos {minimo} caracteres. "
                f"Generar con: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return valor

    # psycopg3 usa postgresql://, Alembic/SQLAlchemy usa postgresql+psycopg2://
    # Railway a veces entrega postgres:// (sin ql) — normalizamos antes de derivar.
    raw_db_url = requerir("DATABASE_URL")
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    sync_db_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return Config(
        mp_access_token=requerir("MP_ACCESS_TOKEN"),
        cuit_destinatario=requerir("CUIT_DESTINATARIO"),
        database_url=raw_db_url,
        database_url_sync=sync_db_url,
        tenant_id=requerir("TENANT_ID"),
        api_key=_requerir_minimo("API_KEY", 32),
        keywords_ocr=os.getenv("KEYWORDS_OCR", "$,monto,importe,total,transferencia,acreditado,pago").split(","),
        jwt_secret_key=_requerir_minimo("JWT_SECRET_KEY", 32),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        secure_cookies=os.getenv("SECURE_COOKIES", "false").lower() == "true",
        rate_limit_login=os.getenv("RATE_LIMIT_LOGIN", "5/minute"),
        sentry_dsn=os.getenv("SENTRY_DSN", ""),
        r2_account_id=requerir("R2_ACCOUNT_ID"),
        r2_access_key_id=requerir("R2_ACCESS_KEY_ID"),
        r2_secret_access_key=requerir("R2_SECRET_ACCESS_KEY"),
        r2_bucket_name=requerir("R2_BUCKET_NAME"),
        whatsapp_token=requerir("WHATSAPP_TOKEN"),
        whatsapp_phone_number_id=requerir("WHATSAPP_PHONE_NUMBER_ID"),
        whatsapp_verify_token=requerir("WHATSAPP_VERIFY_TOKEN"),
        whatsapp_app_secret=os.getenv("WHATSAPP_APP_SECRET", ""),
        redis_url=os.getenv("REDIS_URL", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        llm_habilitado=os.getenv("LLM_HABILITADO", "true").lower() == "true",
        llm_timeout_whatsapp_segundos=float(os.getenv("LLM_TIMEOUT_WHATSAPP_SEGUNDOS", "15")),
        llm_reintentos_whatsapp=int(os.getenv("LLM_REINTENTOS_WHATSAPP", "1")),
        tesseract_timeout_whatsapp_segundos=float(os.getenv("TESSERACT_TIMEOUT_WHATSAPP_SEGUNDOS", "8")),
        llm_timeout_manual_segundos=float(os.getenv("LLM_TIMEOUT_MANUAL_SEGUNDOS", "30")),
        llm_reintentos_manual=int(os.getenv("LLM_REINTENTOS_MANUAL", "2")),
        tesseract_timeout_manual_segundos=float(os.getenv("TESSERACT_TIMEOUT_MANUAL_SEGUNDOS", "12")),
    )


config = _cargar_config()
