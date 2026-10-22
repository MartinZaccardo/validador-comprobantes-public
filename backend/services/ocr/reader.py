import logging
import re

import easyocr
import numpy as np
from PIL import Image

_logger = logging.getLogger(__name__)

# Lazy init: el Reader carga ~300 MB de modelo la primera vez.
# Se inicializa solo si alguna imagen llega al 3er intento (Tesseract falló dos veces).
_easyocr_reader: easyocr.Reader | None = None

# Montos reales tienen ≤ 9 dígitos enteros (~$999.999.999 máximo).
# Números de operación de MP siempre tienen 10-15 dígitos → se rechazan con este límite.
_MAX_DIGITOS_MONTO = 9


def pre_cargar_easyocr() -> None:
    """
    Fuerza la inicialización del modelo EasyOCR en el startup del servidor.

    Por qué existe esta función separada de obtener_reader_easyocr:
      · El lifespan de FastAPI llama a funciones públicas — no privadas.
      · Separar la intención ("pre-calentar al inicio") de la implementación
        ("obtener o inicializar el reader") hace cada función más clara.

    Primera ejecución: descarga ~300 MB de modelos a ~/.EasyOCR/ → tarda ~3-5 min.
    Ejecuciones siguientes: carga desde cache local → tarda ~3-5 segundos.
    """
    _logger.info("Pre-cargando modelo EasyOCR (primera vez ~5 min — luego ~5s desde cache)...")
    obtener_reader_easyocr()
    _logger.info("EasyOCR listo.")


def obtener_reader_easyocr() -> easyocr.Reader:
    """
    Devuelve el Reader de EasyOCR, inicializándolo la primera vez (lazy init).

    Por qué lazy y no al importar el módulo:
      · El modelo pesa ~300 MB y tarda 3-5s en cargar.
      · Si todas las imágenes del run son legibles para Tesseract, nunca se paga ese costo.
      · En Fase 5 (FastAPI), quedará en memoria mientras el server esté corriendo —
        el primer request OCR puede ser lento si llega antes de que terminen de cargar.

    gpu=False: no asumimos CUDA en el entorno. Si hay GPU disponible, cambiar a True.
    verbose=False: EasyOCR imprime sus propios logs de descarga; los silenciamos
                   para no mezclarlos con los del script.
    """
    global _easyocr_reader
    if _easyocr_reader is None:
        _logger.info("Cargando modelo EasyOCR (primera imagen que lo necesita — ~300 MB)...")
        _easyocr_reader = easyocr.Reader(["es", "en"], gpu=False, verbose=False)
        _logger.info("EasyOCR listo.")
    return _easyocr_reader


def leer_detecciones_easyocr(imagen: Image.Image) -> list:
    """
    Corre EasyOCR y devuelve las detecciones crudas en orden de lectura.

    EasyOCR retorna una lista de detecciones:
        [ [bbox, texto, confianza], ... ]
    donde bbox tiene 4 esquinas: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]].

    Ordenamos por coordenada Y de la esquina superior-izquierda (bbox[0][1])
    para reconstruir el orden de lectura de arriba a abajo.

    Se devuelven las detecciones completas (no solo el texto) porque las
    bounding boxes se necesitan para la detección geométrica del monto
    (detectar_monto_easyocr) sin correr EasyOCR dos veces.
    """
    reader = obtener_reader_easyocr()
    resultados = reader.readtext(np.array(imagen))
    return sorted(resultados, key=lambda r: r[0][0][1])


def texto_desde_detecciones(detecciones: list) -> str:
    """
    Aplana las detecciones de EasyOCR a texto plano multilínea.

    Unimos con '\\n' para que las regex de detección funcionen igual
    que con el output de Tesseract. El texto pasa por normalizar_easyocr
    para corregir errores sistemáticos del modelo (slash → I, espacios
    en números largos).
    """
    texto = "\n".join(texto_deteccion for _, texto_deteccion, _ in detecciones)
    return normalizar_easyocr(texto)


def normalizar_easyocr(texto: str) -> str:
    """
    Corrige errores sistemáticos del output de EasyOCR antes de aplicar las regex.

    Dos problemas observados en las imágenes de prueba:

    1. "CUITICUIL" en lugar de "CUIT/CUIL":
       EasyOCR confunde el slash "/" con la letra "I" en texto de bajo contraste.
       Aplica también a variantes: "CUiTICUIL", "CUIT I CUIL", "CUIT/CUIL" (ya correcto).
       Regex: CUIT + [espacio opcional] + [I/i//] + [espacio opcional] + CUIL

    2. Espacios internos en números largos:
       EasyOCR fragmenta "160471071168" → "1604 71071168".
       Consolidamos pares de dígitos separados por un espacio cuando el resultado
       tiene ≤ 22 caracteres (el CVU argentino tiene exactamente 22 dígitos).
       Si el par supera 22 caracteres, lo dejamos separado (son dos números distintos).
    """
    # 1. Normalizar el separador CUIT/CUIL
    texto = re.sub(r"CUIT\s*[Ii/]\s*CUIL", "CUIT/CUIL", texto, flags=re.IGNORECASE)

    # 2. Consolidar dígitos separados por un espacio
    texto = re.sub(
        r"(\d+) (\d+)",
        lambda m: m.group(1) + m.group(2) if len(m.group(1) + m.group(2)) <= 22 else m.group(0),
        texto,
    )

    return texto


def tiene_superindice_centavos(bbox: list, imagen: Image.Image) -> bool:
    """
    Mide los glifos dentro del bbox del monto y decide si los últimos son
    un superíndice de centavos.

    Cómo: binariza el crop (Otsu elige el umbral según la iluminación de cada
    foto) y extrae componentes conexas — cada "isla" de píxeles oscuros es
    aproximadamente un glifo, con su rectángulo (x, top, ancho, alto).

    Un superíndice cumple DOS condiciones a la vez:
      · chico:   altura < 60% de la altura máxima de la línea
      · elevado: su borde inferior queda bien por encima del de los glifos
        grandes (≥ 25% de la altura máxima)

    La segunda condición es la que evita falsos positivos: el punto de miles
    de "$ 1.500" también es chico, pero está abajo (en la base), no arriba.

    No se asume que una componente = un dígito (un "6" borroso puede partirse
    en 2 islas) — por eso la cantidad de centavos no se cuenta acá: la fija
    el formato de MP (siempre 2).
    """
    import cv2

    xs = [punto[0] for punto in bbox]
    ys = [punto[1] for punto in bbox]
    MARGEN = 5
    crop = imagen.crop((
        max(0, int(min(xs)) - MARGEN),
        max(0, int(min(ys)) - MARGEN),
        min(imagen.width, int(max(xs)) + MARGEN),
        min(imagen.height, int(max(ys)) + MARGEN),
    ))

    crop_gris = np.array(crop.convert("L"))
    _, crop_binario = cv2.threshold(crop_gris, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cantidad, _, stats, _ = cv2.connectedComponentsWithStats(crop_binario, connectivity=8)

    AREA_MINIMA = 15  # descarta ruido de compresión JPEG y motas de la foto
    glifos = [
        (x, top, ancho, alto)
        for x, top, ancho, alto, area in (stats[i] for i in range(1, cantidad))  # 0 = fondo
        if area >= AREA_MINIMA
    ]
    # Mínimo: 1 dígito grande + 2 componentes de superíndice.
    if len(glifos) < 3:
        return False

    altura_maxima = max(alto for _, _, _, alto in glifos)
    grandes = [g for g in glifos if g[3] >= 0.6 * altura_maxima]
    chicos = [g for g in glifos if g[3] < 0.6 * altura_maxima]
    if not grandes or len(chicos) < 2:
        return False

    # Los centavos van DESPUÉS del último glifo grande (a su derecha).
    fin_grandes = max(x + ancho for x, _, ancho, _ in grandes)
    chicos_finales = [g for g in chicos if g[0] >= fin_grandes]
    if len(chicos_finales) < 2:
        return False

    base_grandes = max(top + alto for _, top, _, alto in grandes)
    base_chicos = max(top + alto for _, top, _, alto in chicos_finales)
    return base_chicos <= base_grandes - 0.25 * altura_maxima


def detectar_monto_easyocr(detecciones: list, imagen: Image.Image) -> str | None:
    """
    Detecta el monto combinando el texto de EasyOCR con la geometría de sus glifos.

    Problema que resuelve: el monto decorativo de MP escribe los centavos en
    superíndice ("$ 8⁶⁶"). EasyOCR lee bien los dígitos pero los aplana en una
    línea sin separador decimal → "$ 866". Del texto plano es imposible saber
    si eso es $866 o $8,66 — la información está en la geometría: los dígitos
    de centavos son más chicos y están alineados arriba.

    Estrategia: el bbox de la detección localiza el monto en la imagen; sobre
    ese crop, tiene_superindice_centavos mide los glifos. Si hay superíndice,
    los últimos 2 dígitos son centavos (MP siempre muestra exactamente 2).

    Conservador por diseño: ante cualquier condición que no cierre, devuelve
    el texto tal como lo leyó EasyOCR — nunca empeora el comportamiento previo.
    """
    deteccion_monto = None
    for bbox, texto_deteccion, _confianza in detecciones:
        # Grupos de dígitos separados por espacio se aceptan: EasyOCR a veces
        # deja un hueco entre el entero y el superíndice ("$ 8 66").
        match = re.search(r"\$\s*([\d.,]+(?:\s+[\d.,]+)*)", texto_deteccion)
        if match:
            deteccion_monto = (bbox, match.group(1))
            break

    if deteccion_monto is None:
        return None

    bbox_monto, monto_crudo = deteccion_monto
    digitos = re.sub(r"[^\d]", "", monto_crudo)
    if not digitos or len(digitos) > _MAX_DIGITOS_MONTO:
        return None

    # Con separador decimal ya leído no hay nada que corregir; con < 3 dígitos
    # no hay dónde insertar la coma (ej: "$ 8" donde el superíndice se perdió).
    if "," in monto_crudo or "." in monto_crudo or len(digitos) < 3:
        return "$" + monto_crudo.replace(" ", "")

    if tiene_superindice_centavos(bbox_monto, imagen):
        return "$" + digitos[:-2] + "," + digitos[-2:]

    return "$" + monto_crudo.replace(" ", "")
