import asyncio
import logging
import time
from datetime import datetime, timezone
from io import BytesIO

import pytesseract
from config import config
from models.resultado import CanalOrigen, FuenteOCR, ResultadoOCR
from PIL import Image

from services.llm_extractor import (
    CalidadImagen,
    ComprobanteLLM,
    TipoIdentificador,
    extraer_con_llm,
)
from services.ocr.extractors import (
    detectar_cuit_destinatario,
    detectar_monto,
    detectar_numero_operacion,
    extraer_monto_zona_mp,
)
from services.ocr.preprocessing import (
    invertir_si_oscura,
    preprocesar_imagen,
    recortar_pantalla_opencv,
)
from services.ocr.reader import (
    detectar_monto_easyocr,
    leer_detecciones_easyocr,
    texto_desde_detecciones,
)

_logger = logging.getLogger(__name__)


# ── Pipeline principal MVP11 (LLM → Tesseract fallback) ──────────────────────

def _obtener_timeouts(canal: CanalOrigen) -> tuple[float, int, float]:
    """Devuelve (llm_timeout_s, llm_intentos, tesseract_timeout_s) según el canal."""
    if canal == CanalOrigen.WHATSAPP:
        return (
            config.llm_timeout_whatsapp_segundos,
            config.llm_reintentos_whatsapp,
            config.tesseract_timeout_whatsapp_segundos,
        )
    return (
        config.llm_timeout_manual_segundos,
        config.llm_reintentos_manual,
        config.tesseract_timeout_manual_segundos,
    )


def _llm_dio_datos_utiles(comprobante: ComprobanteLLM) -> bool:
    tiene_identificador = (
        comprobante.numero_operacion is not None
        or comprobante.coelsa_id is not None
    )
    if comprobante.calidad_imagen == CalidadImagen.ILEGIBLE:
        # Si ILEGIBLE pero sin ningún dato extraído, puede ser una mala clasificación
        # (número tachado, foto con reflejo) → ceder a Tesseract para que intente.
        return (
            tiene_identificador
            or comprobante.monto is not None
            or comprobante.cuit_destinatario is not None
        )
    return (
        comprobante.confianza_extraccion >= 0.3
        and (tiene_identificador or comprobante.monto is not None)
    )


def _mapear_llm_a_resultado(comprobante: ComprobanteLLM) -> ResultadoOCR:
    es_valido = comprobante.calidad_imagen in (CalidadImagen.LEGIBLE, CalidadImagen.PARCIAL)

    if comprobante.tipo_identificador == TipoIdentificador.COELSA_ID:
        identificador = comprobante.coelsa_id_validado
        baja_confianza = comprobante.tiene_discrepancia_coelsa
    elif comprobante.tipo_identificador == TipoIdentificador.NUMERO_OP_MP:
        identificador = comprobante.numero_operacion_validado
        baja_confianza = comprobante.tiene_discrepancia_numero
    else:
        # SIN_IDENTIFICADOR_TRAZABLE — el pipeline de anti-duplicados lo maneja después
        identificador = None
        baja_confianza = False

    return ResultadoOCR(
        fuente=FuenteOCR.LLM_GEMINI,
        es_comprobante_valido=es_valido,
        tipo_identificador=comprobante.tipo_identificador.value if comprobante.tipo_identificador else None,
        identificador_pago=identificador,
        monto_detectado=comprobante.monto,
        cuit_destinatario_detectado=comprobante.cuit_destinatario,
        confianza=comprobante.confianza_extraccion,
        baja_confianza_identificador=baja_confianza,
        fecha_comprobante=comprobante.fecha,
        cvu_cbu_destinatario=comprobante.cvu_cbu_destinatario,
        entidad_emisora=comprobante.entidad_emisora,
        cuit_remitente=comprobante.cuit_remitente,
    )


def _mapear_tesseract_a_resultado(ocr_dict: dict) -> ResultadoOCR:
    es_valido = ocr_dict["es_comprobante_valido"]
    return ResultadoOCR(
        fuente=FuenteOCR.TESSERACT,
        es_comprobante_valido=es_valido,
        identificador_pago=ocr_dict.get("identificador_pago"),
        monto_detectado=ocr_dict.get("monto_detectado"),
        cuit_destinatario_detectado=ocr_dict.get("cuit_destinatario_detectado"),
        ocr_texto_crudo=ocr_dict.get("texto_crudo", ""),
        palabras_clave_encontradas=ocr_dict.get("keywords", []),
        confianza=0.5 if es_valido else 0.1,
    )


async def _intentar_llm(
    imagen_bytes: bytes,
    timeout_segundos: float,
    intentos: int,
) -> ResultadoOCR | None:
    for intento in range(intentos):
        try:
            comprobante = await asyncio.wait_for(
                extraer_con_llm(imagen_bytes),
                timeout=timeout_segundos,
            )
            if _llm_dio_datos_utiles(comprobante):
                return _mapear_llm_a_resultado(comprobante)
            _logger.warning("LLM datos no útiles — confianza=%.2f calidad=%s",
                            comprobante.confianza_extraccion, comprobante.calidad_imagen)
            return None
        except asyncio.TimeoutError:
            _logger.warning("LLM timeout intento %d/%d (%.0fs)", intento + 1, intentos, timeout_segundos)
        except Exception as e:  # noqa: BLE001
            _logger.warning("LLM error intento %d/%d: %s", intento + 1, intentos, e)
        if intento < intentos - 1:
            # 503 "high demand" necesita más tiempo que 500ms para recuperarse.
            await asyncio.sleep(2.0)
    _logger.error("LLM falló en todos los intentos (%d/%d) — Gemini no disponible o API key inválida", intentos, intentos)
    return None


def _pdf_a_imagen_bytes(pdf_bytes: bytes) -> bytes | None:
    """
    Convierte la primera página de un PDF a PNG antes de enviarlo a Gemini.

    Los PDFs de billeteras son pantallas renderizadas (no texto vectorial) — la
    conversión no pierde información. Gemini lee mejor la imagen que algunos PDFs
    con fondos oscuros. scale=2 produce ~144 DPI.
    """
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        bitmap = pdf[0].render(scale=2)
        buffer = BytesIO()
        bitmap.to_pil().save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as e:  # noqa: BLE001
        _logger.warning("PDF a imagen fallido: %s", e)
        return None


async def _intentar_tesseract(imagen_bytes: bytes, timeout_segundos: float) -> ResultadoOCR | None:
    if imagen_bytes[:4] == b"%PDF":
        _logger.info("Tesseract saltado — el archivo es un PDF")
        return None
    try:
        ocr_dict = await asyncio.wait_for(
            asyncio.to_thread(procesar_bytes, imagen_bytes),
            timeout=timeout_segundos,
        )
        return _mapear_tesseract_a_resultado(ocr_dict)
    except asyncio.TimeoutError:
        _logger.error("Tesseract timeout (%.0fs excedido)", timeout_segundos)
        return None
    except Exception as e:  # noqa: BLE001
        _logger.error("Tesseract error: %s", e)
        return None


async def procesar_imagen(imagen_bytes: bytes, canal_origen: CanalOrigen) -> ResultadoOCR:
    """
    Pipeline principal: intenta Gemini, cae a Tesseract si falla.
    Entry point para WhatsApp y carga manual.
    """
    inicio = time.monotonic()
    llm_timeout, llm_intentos, tesseract_timeout = _obtener_timeouts(canal_origen)

    if imagen_bytes[:4] == b"%PDF":
        convertida = _pdf_a_imagen_bytes(imagen_bytes)
        if convertida is not None:
            imagen_bytes = convertida
            _logger.info("PDF convertido a imagen PNG para OCR")

    resultado: ResultadoOCR | None = None

    if config.llm_habilitado and config.gemini_api_key:
        resultado = await _intentar_llm(imagen_bytes, llm_timeout, llm_intentos)
        if resultado is None:
            _logger.warning("LLM falló — REVISION_MANUAL directo, sin Tesseract (canal=%s)", canal_origen)
            resultado = ResultadoOCR(
                fuente=FuenteOCR.SIN_DATOS,
                es_comprobante_valido=False,
                forzar_revision_manual=True,
            )

    # Tesseract solo corre cuando LLM está desactivado (LLM_HABILITADO=false — circuit breaker)
    if resultado is None:
        resultado = await _intentar_tesseract(imagen_bytes, tesseract_timeout)

    if resultado is None:
        resultado = ResultadoOCR(
            fuente=FuenteOCR.SIN_DATOS,
            es_comprobante_valido=False,
            error="Todos los motores OCR fallaron",
        )

    resultado.tiempo_ms = int((time.monotonic() - inicio) * 1000)
    _logger.info(
        "OCR completado — fuente=%s confianza=%.2f tiempo=%dms canal=%s discrepancia_numero=%s",
        resultado.fuente, resultado.confianza, resultado.tiempo_ms,
        canal_origen, resultado.baja_confianza_identificador,
    )
    return resultado


def procesar_bytes(imagen_bytes: bytes) -> dict:
    """
    Corre el pipeline Tesseract sobre bytes crudos de imagen.
    Llamado desde _intentar_tesseract() cuando LLM_HABILITADO=false.
    Retorna un dict con los campos extraídos.
    """
    imagen_original = Image.open(BytesIO(imagen_bytes))
    return _pipeline_ocr(imagen_original)


def _pipeline_ocr(imagen_original: Image.Image) -> dict:
    """
    Los 4 intentos de OCR sobre una imagen PIL. Usado por procesar_bytes().

    Retorna un dict con:
      texto_crudo, identificador_pago, monto_detectado,
      cuit_destinatario_detectado, es_comprobante_valido, keywords
    """
    imagen = invertir_si_oscura(imagen_original)

    # Intento 1 — Tesseract sobre imagen original (o invertida si era oscura).
    texto = pytesseract.image_to_string(imagen, lang="spa+eng", config="--psm 6 --oem 3")
    numero_op_extraido = detectar_numero_operacion(texto)
    cuit_extraido = detectar_cuit_destinatario(texto)
    monto_extraido = detectar_monto(texto)
    textos_ocr = [texto]

    # Intento 2 — Tesseract sobre imagen preprocesada, si faltó número, CUIT o monto.
    # Monto se incluye porque PSM 6 pierde texto en fuente muy grande (el "$ N" decorativo
    # de comprobantes MP). La imagen preprocesada (contraste, escala) mejora la lectura.
    if numero_op_extraido is None or cuit_extraido is None or monto_extraido is None:
        imagen_mejorada = preprocesar_imagen(imagen)
        texto_mejorado = pytesseract.image_to_string(imagen_mejorada, lang="spa+eng", config="--psm 6 --oem 3")
        textos_ocr.append(texto_mejorado)
        if numero_op_extraido is None:
            numero_op_extraido = detectar_numero_operacion(texto_mejorado)
        if cuit_extraido is None:
            cuit_extraido = detectar_cuit_destinatario(texto_mejorado)
        if monto_extraido is None:
            monto_extraido = detectar_monto(texto_mejorado)

    # Fallback monto — crop dirigido a la zona del monto en comprobantes MP.
    # PSM 6 sobre la imagen completa pierde el "$ N" cuando la fuente es mucho
    # más grande que el resto. En un crop de esa franja sí lo lee.
    if monto_extraido is None:
        monto_extraido = extraer_monto_zona_mp(imagen)

    # Para fotos de celular: si el monto sigue sin detectarse, rectificamos la
    # perspectiva con OpenCV y corremos el crop sobre la pantalla rectificada.
    if monto_extraido is None:
        imagen_rectificada = recortar_pantalla_opencv(imagen_original)
        if imagen_rectificada is not None:
            monto_extraido = extraer_monto_zona_mp(imagen_rectificada)

    # Intento 3 — EasyOCR, si Tesseract falló en ambos intentos.
    if numero_op_extraido is None or cuit_extraido is None:
        detecciones_easy = leer_detecciones_easyocr(imagen)
        texto_easy = texto_desde_detecciones(detecciones_easy)
        textos_ocr.append(texto_easy)
        if numero_op_extraido is None:
            numero_op_extraido = detectar_numero_operacion(texto_easy)
        if cuit_extraido is None:
            cuit_extraido = detectar_cuit_destinatario(texto_easy)
        if monto_extraido is None:
            # Geometría primero: las bounding boxes distinguen "$ 8⁶⁶" de "$ 866",
            # cosa que el texto plano no puede. detectar_monto queda como fallback
            # (cubre el caso "número antes de Motivo" sin signo $).
            monto_extraido = detectar_monto_easyocr(detecciones_easy, imagen)
        if monto_extraido is None:
            monto_extraido = detectar_monto(texto_easy)

    # Intento 4 — OpenCV screen crop, si los 3 anteriores fallaron.
    if numero_op_extraido is None or cuit_extraido is None:
        imagen_crop = recortar_pantalla_opencv(imagen_original)
        if imagen_crop is not None:
            texto_crop = pytesseract.image_to_string(imagen_crop, lang="spa+eng", config="--psm 6 --oem 3")
            textos_ocr.append(texto_crop)
            if numero_op_extraido is None:
                numero_op_extraido = detectar_numero_operacion(texto_crop)
            if cuit_extraido is None:
                cuit_extraido = detectar_cuit_destinatario(texto_crop)
            if monto_extraido is None:
                monto_extraido = detectar_monto(texto_crop)

            if numero_op_extraido is None or cuit_extraido is None:
                detecciones_crop_easy = leer_detecciones_easyocr(imagen_crop)
                texto_crop_easy = texto_desde_detecciones(detecciones_crop_easy)
                textos_ocr.append(texto_crop_easy)
                if numero_op_extraido is None:
                    numero_op_extraido = detectar_numero_operacion(texto_crop_easy)
                if cuit_extraido is None:
                    cuit_extraido = detectar_cuit_destinatario(texto_crop_easy)
                if monto_extraido is None:
                    monto_extraido = detectar_monto_easyocr(detecciones_crop_easy, imagen_crop)
                if monto_extraido is None:
                    monto_extraido = detectar_monto(texto_crop_easy)

    texto_combinado = "\n".join(textos_ocr)
    texto_lower = texto_combinado.lower()
    keywords_encontradas = [kw for kw in config.keywords_ocr if kw.lower() in texto_lower]

    return {
        "texto_crudo": texto,
        "identificador_pago": numero_op_extraido,
        "monto_detectado": monto_extraido,
        "cuit_destinatario_detectado": cuit_extraido,
        "es_comprobante_valido": len(keywords_encontradas) > 0,
        "keywords": keywords_encontradas,
    }


