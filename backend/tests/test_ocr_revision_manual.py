"""
Tests unitarios del fallback OCR cuando Gemini falla.

Cubre la regla: Gemini habilitado pero falla → REVISION_MANUAL directo,
sin pasar por Tesseract. Tesseract sigue activo solo como circuit breaker
(LLM_HABILITADO=false).

No tocan DB ni servicios externos — todo se mockea.
"""
import asyncio
from unittest.mock import AsyncMock, patch

from config import config
from models.resultado import CanalOrigen, FuenteOCR, ResultadoOCR
from services.ocr.service import procesar_imagen
from services.validacion_core import determinar_estado


def test_llm_habilitado_falla_devuelve_forzar_revision_manual():
    """Gemini habilitado pero falla (timeout/error) → forzar_revision_manual=True."""
    with (
        patch.object(config, "llm_habilitado", True),
        patch.object(config, "gemini_api_key", "fake-key"),
        patch("services.ocr.service._intentar_llm", new_callable=AsyncMock, return_value=None),
    ):
        resultado = asyncio.run(procesar_imagen(b"fake_imagen", CanalOrigen.WHATSAPP))

    assert resultado.forzar_revision_manual is True
    assert resultado.fuente == FuenteOCR.SIN_DATOS


def test_llm_desactivado_llama_tesseract_sin_revision_manual():
    """LLM_HABILITADO=false (circuit breaker) → Tesseract corre, no REVISION_MANUAL."""
    resultado_tesseract = ResultadoOCR(
        fuente=FuenteOCR.TESSERACT,
        es_comprobante_valido=True,
    )
    with (
        patch.object(config, "llm_habilitado", False),
        patch(
            "services.ocr.service._intentar_tesseract",
            new_callable=AsyncMock,
            return_value=resultado_tesseract,
        ) as mock_tesseract,
    ):
        resultado = asyncio.run(procesar_imagen(b"fake_imagen", CanalOrigen.WHATSAPP))

    mock_tesseract.assert_called_once()
    assert resultado.forzar_revision_manual is False
    assert resultado.fuente == FuenteOCR.TESSERACT


def test_determinar_estado_forzar_revision_manual_cortocircuita():
    """forzar_revision_manual=True → REVISION_MANUAL sin consultar Redis ni MP."""
    ocr = ResultadoOCR(
        fuente=FuenteOCR.SIN_DATOS,
        es_comprobante_valido=False,
        forzar_revision_manual=True,
    )
    mock_redis = AsyncMock()

    estado, mp_status, numero_op = asyncio.run(determinar_estado(ocr, set(), mock_redis))

    assert estado == "REVISION_MANUAL"
    assert mp_status is None
    assert numero_op is None
    mock_redis.sadd.assert_not_called()
