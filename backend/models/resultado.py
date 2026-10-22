from enum import Enum

from pydantic import BaseModel


class CanalOrigen(str, Enum):
    WHATSAPP = "whatsapp"  # límite duro de 20s para responder el webhook de Meta
    MANUAL   = "manual"   # carga manual por admin, sin límite de tiempo percibido


class FuenteOCR(str, Enum):
    LLM_GEMINI = "llm_gemini"  # Gemini 2.5 Flash extrajo los datos
    TESSERACT  = "tesseract"   # LLM falló o está desactivado, usó el pipeline anterior
    SIN_DATOS  = "sin_datos"   # ambos motores fallaron


class ResultadoOCR(BaseModel):
    """Resultado del pipeline de extracción de imagen, independiente del canal de origen."""
    fuente: FuenteOCR
    es_comprobante_valido: bool
    tipo_identificador: str | None = None   # "NUMERO_OP_MP" | "COELSA_ID" | "SIN_IDENTIFICADOR_TRAZABLE"
    identificador_pago: str | None = None
    monto_detectado: str | None = None
    cuit_destinatario_detectado: str | None = None
    ocr_texto_crudo: str = ""                      # solo Tesseract lo completa
    palabras_clave_encontradas: list[str] = []     # solo Tesseract lo completa
    confianza: float = 0.0
    baja_confianza_identificador: bool = False
    forzar_revision_manual: bool = False
    fecha_comprobante: str | None = None           # ISO: "YYYY-MM-DD"
    cvu_cbu_destinatario: str | None = None
    entidad_emisora: str | None = None
    cuit_remitente: str | None = None
    tiempo_ms: int = 0
    error: str | None = None
