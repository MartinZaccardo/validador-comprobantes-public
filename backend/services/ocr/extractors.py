import logging
import re

import pytesseract
from PIL import Image

_logger = logging.getLogger(__name__)

# Montos reales tienen ≤ 9 dígitos enteros (~$999.999.999 máximo).
# Números de operación de MP siempre tienen 10-15 dígitos → se rechazan con este límite.
_MAX_DIGITOS_MONTO = 9


def detectar_monto(texto: str) -> str | None:
    # Intento 1: signo $ explícito seguido de número.
    match = re.search(r"\$\s*[\d.,]+", texto)
    if match:
        raw = match.group(0)
        if len(re.sub(r"[^\d]", "", raw)) <= _MAX_DIGITOS_MONTO:
            return raw

    # Intento 2: en comprobantes MP el monto ocupa la línea justo antes de "Motivo:".
    # Tesseract pierde el $ en la fuente grande/custom de MP → queda solo el número.
    match = re.search(r"([\d.,]+)\s*\n\s*Motivo\b", texto, re.IGNORECASE)
    if match:
        raw = match.group(1)
        if len(re.sub(r"[.,]", "", raw)) <= _MAX_DIGITOS_MONTO:
            return "$" + raw

    return None


def detectar_numero_operacion(texto: str) -> str | None:
    # Formato 1 (comprobante estándar): "Número de operación de Mercado Pago\n159649785954"
    # [uú]/[oó]/[eé] cubren tildes que el OCR a veces pierde o cambia.
    # [^0-9]* en lugar de [^\n]*[\n\s]+: cubre tanto el caso donde el número
    # está en la línea siguiente (más común) como cuando el OCR lo pone en la
    # misma línea que el label — en ese caso [^\n]* era greedy y consumía el número.
    match = re.search(
        r"[Nn][uú]mero\s+de\s+operaci[oóeé]n[^0-9]*(\d{10,15})",
        texto,
    )
    if match:
        return match.group(1)

    # Formato 2 (historial de MP): "N.° de operación\n159911039030"
    # El símbolo "°" puede ser leído por el OCR como "o", "0", "º" o simplemente omitido.
    match = re.search(
        r"N\.?\s*[°oº0]?\s*de\s+operaci[oóeé]n\s*\n?\s*(\d{10,15})",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    # Formato 3 (label cortado por OCR en imágenes preprocesadas):
    # "Nomero de\n159189747279" — el OCR captura "Número de" pero pierde el resto del label.
    # Cubre variantes como "Nomero", "Numero", "Nimero" (errores comunes de Tesseract con tilde).
    # [^0-9]* por el mismo motivo que Formato 1: evita que el match greedy
    # consuma el número si OCR lo pone en la misma línea que el label truncado.
    match = re.search(
        r"[Nn][uoúiíeé]m[ae]?ro?\s+de[^0-9]*(\d{10,15})",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    # Formato 4 (EasyOCR — label muy corrupto):
    # Cuando la parte "Número" del label queda irreconocible ("Nuf1no 9 ,"),
    # los formatos 1-3 no matchean. Este formato busca solo "de operaci?n"
    # y toma el primer número de 10-15 dígitos en las 80 posiciones siguientes.
    # [\s\S]{0,80}? cubre saltos de línea sin necesitar re.DOTALL.
    # Límite de 80 chars evita capturar números de otra sección del comprobante.
    match = re.search(
        r"de\s+operaci[oó0e]n[\s\S]{0,80}?(\d{10,15})",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    # Formato 5 (EasyOCR — label con "acion" pero irreconocible):
    # Caso observado: 9810 → EasyOCR lee "Ntnovo de ohttacion do Metcunlo"
    # en lugar de "Número de operación de Mercado Pago".
    # "operacion" comparte el sufijo "acion" con "ohttacion" — usamos ese patrón
    # como gancho: cualquier palabra de 3-12 chars que termine en "acion/ación"
    # después de "de", seguida en las 100 posiciones siguientes por el número.
    # Ventana de 100 (vs 80 en Formato 4) para absorber ruido adicional entre
    # el label y el número cuando el OCR inserta basura entremedio.
    match = re.search(
        r"de\s+[a-z]{3,12}aci[oó]n[\s\S]{0,100}?(\d{10,15})",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    # Formato 6 (EasyOCR muy corrupto — "de operación" fusionado en una palabra):
    # Caso observado: 9008 crop → EasyOCR lee "Numento coopuacion do Morcocio Porjo"
    # donde "coopuacion" fusiona "de operación" en un solo token corrupto.
    # A diferencia de Formato 5, aquí no hay "de" antes de la palabra con "acion".
    # Igual de permisivo pero sin requerir el prefijo "de" — último recurso.
    # Ventana de 100 chars; el riesgo de falso positivo es bajo porque
    # palabras que terminan en "acion" (confirmacion, notificacion) raramente
    # aparecen en comprobantes de pago seguidas de un número de 10-15 dígitos.
    match = re.search(
        r"[a-z]{3,15}aci[oó]n[\s\S]{0,100}?(\d{10,15})",
        texto,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    return None


def detectar_cuit_destinatario(texto: str) -> str | None:
    # Patrón de CUIT que acepta tres formatos de separador:
    #   · Guión: "20-45744727-3"  (estándar)
    #   · Punto: "20.45744727.3"  (EasyOCR confunde guión con punto)
    #   · Espacio: "20 457447273" (Tesseract en crop OpenCV: el separador se omite
    #              y los grupos 2do y 3er se fusionan → "45744727"+"3" = "457447273")
    # `[-.\s]?` cubre todos (el `-` al inicio del set evita interpretarse como rango).
    _CUIT_PATTERN = r"\d{2}[-.\s]?\d{8}[-.\s]?\d"

    # Estrategia 1: contexto "Para" + CUIT/CUIL del destinatario.
    # El comprobante tiene el nombre entre "Para" y "CUIT/CUIL:", por eso [^\n]* salta esa línea.
    match = re.search(
        rf"Para\s*\n[^\n]*\n\s*CUIT/CUIL\s*[-:]?\s*({_CUIT_PATTERN})",
        texto,
    )
    if match:
        return re.sub(r"[\s.]", "-", match.group(1))

    # Estrategia 2 (fallback comprobante estándar): siempre hay dos CUIT/CUIL —
    # primero el del emisor (sección "De"), luego el del destinatario (sección "Para").
    # Si el OCR no imprimió la palabra "Para", tomamos el último de los dos.
    todos = re.findall(rf"CUIT/CUIL\s*[-:]?\s*({_CUIT_PATTERN})", texto)
    if len(todos) >= 2:
        return re.sub(r"[\s.]", "-", todos[-1])

    # Estrategia 2b (fallback Tesseract en crop): un solo CUIT/CUIL detectado.
    # Caso: el emisor tiene CUIT corrupto ("CuUITICUR") y solo el destinatario es legible.
    # RIESGO: si el único CUIT detectado es el del EMISOR y no el del destinatario,
    # se retorna el CUIT incorrecto → ERROR_DESTINATARIO falso.
    # Aceptamos este riesgo porque ERROR_DESTINATARIO es recuperable (el operador puede
    # ver el CUIT en el resumen y verificar manualmente), mientras que None hace que
    # la verificación de destinatario sea silenciosamente omitida.
    if len(todos) == 1:
        return re.sub(r"[\s.]", "-", todos[0])

    # NOTA: Si `todos` está vacío, todas las estrategias basadas en "CUIT/CUIL" fallaron.
    # Continuamos con Estrategia 3 (historial MP).

    # Estrategia 3 (historial de MP): CUIT sin guiones después de un CVU.
    # Formato: "CVU: 0000003100065759326584\nCUIT: 24255982466"
    # Un CUIT argentino tiene exactamente 11 dígitos.
    match = re.search(r"CVU:[\s\d•.]+\n\s*CUIT:\s*(\d{11})", texto)
    if match:
        return match.group(1)

    # Estrategia 4 (fallback historial): cualquier "CUIT:" seguido de 11 dígitos.
    # Menos específico — solo se usa si las anteriores fallaron.
    match = re.search(r"\bCUIT:\s*(\d{11})\b", texto)
    if match:
        return match.group(1)

    return None


def extraer_monto_zona_mp(imagen: Image.Image) -> str | None:
    """
    Fallback de monto para comprobantes MP cuyo "$ N" está en fuente muy grande.

    PSM 6 trata el monto decorativo como outlier y lo omite al procesar la imagen
    completa. Solución: localizar "Motivo:" con image_to_data (que sí lo encuentra,
    como confirma el texto_crudo), recortar la franja inmediatamente superior donde
    MP siempre ubica el monto, y correr OCR sobre ese crop pequeño.
    """
    datos = pytesseract.image_to_data(
        imagen, lang="spa+eng", output_type=pytesseract.Output.DICT, config="--psm 6 --oem 3"
    )

    motivo_top = None
    for palabra, conf, top in zip(datos["text"], datos["conf"], datos["top"]):
        # conf=-1 = entrada de bloque sin palabra real (no filtrar conf=0)
        if "motivo" in palabra.lower() and int(conf) != -1:
            motivo_top = top
            break

    if motivo_top is None:
        return None

    # 250px cubre el monto en fuente grande (~150px) más margen para distintas resoluciones.
    y_inicio = max(0, motivo_top - 250)
    crop_monto = imagen.crop((0, y_inicio, imagen.width, motivo_top))

    texto_psm6 = pytesseract.image_to_string(
        crop_monto, lang="spa+eng", config="--psm 6 --oem 3"
    )
    monto = detectar_monto(texto_psm6)
    if monto is not None:
        return monto

    # PSM 11 (sparse text): detecta texto aislado rodeado de espacio en blanco,
    # donde PSM 6 falla por no encontrar un "bloque uniforme".
    texto_psm11 = pytesseract.image_to_string(
        crop_monto, lang="spa+eng", config="--psm 11 --oem 3"
    )
    _logger.debug(f"[monto_zona_mp] psm11={repr(texto_psm11[:120])}")
    return detectar_monto(texto_psm11)
