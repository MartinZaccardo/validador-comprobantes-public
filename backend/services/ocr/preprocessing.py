import logging

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

_logger = logging.getLogger(__name__)


def ordenar_puntos_cuadrilatero(pts: np.ndarray) -> np.ndarray:
    """
    Ordena 4 puntos en el orden: top-left, top-right, bottom-right, bottom-left.

    El truco de suma/diferencia:
      · top-left:     menor suma x+y  (está más cerca del origen 0,0)
      · bottom-right: mayor suma x+y
      · top-right:    menor diferencia y-x  (y pequeño, x grande)
      · bottom-left:  mayor diferencia y-x
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    sumas_coordenadas = pts.sum(axis=1)
    rect[0] = pts[np.argmin(sumas_coordenadas)]   # top-left
    rect[2] = pts[np.argmax(sumas_coordenadas)]   # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def invertir_si_oscura(imagen: Image.Image) -> Image.Image:
    """
    Invierte los colores si la imagen parece ser un screenshot en dark mode.

    Caso cubierto: historial de MP en modo oscuro — texto claro sobre fondo gris oscuro.
    Tesseract y EasyOCR esperan texto oscuro sobre fondo claro.

    Por qué dos condiciones en lugar de una sola:
        Una imagen de historial MP dark mode tiene brillo medio ~130-140 (fondo gris oscuro
        #1A1A1A ≈ brillo 26, pero con zonas más claras como tarjetas y texto).
        Una foto de celular tomada en un cuarto oscuro tiene brillo medio similar (~60-130),
        pero con muchos más píxeles verdaderamente negros (el fondo de la habitación ≈ 0).

        Condición 1 — brillo_medio < 145:
            Filtra screenshots claros (media > 150) que no necesitan inversión.

        Condición 2 — pct_muy_oscuro < 0.25:
            Distingue dark mode (fondo gris oscuro, ≈20% de píxeles < 80)
            de fotos en cuarto oscuro (fondo negro real, ≈40-83% de píxeles < 80).
            Invertir una foto de cuarto oscuro sería contraproducente: el contenido
            de la pantalla ya está en positivo y quedaría invertido.

        Verificado contra las 15 imágenes del conjunto: solo dispara en el historial
        MP oscuro, no en fotos de cuarto oscuro ni en screenshots limpios.

    Por qué convertir a RGB antes de invertir:
        ImageOps.invert no acepta RGBA (screenshots PNG con canal alfa).
        Convertir a RGB descarta el canal alfa de forma segura.
    """
    pixeles = np.array(imagen.convert("L"))
    brillo_medio = float(pixeles.mean())
    pct_muy_oscuro = float((pixeles < 80).mean())

    if brillo_medio < 145 and pct_muy_oscuro < 0.25:
        _logger.info(
            f"Dark mode detectado (brillo={brillo_medio:.0f}/255, "
            f"px<80={pct_muy_oscuro*100:.0f}%) — invirtiendo colores."
        )
        return ImageOps.invert(imagen.convert("RGB"))
    return imagen


def preprocesar_imagen(imagen: Image.Image) -> Image.Image:
    """
    Mejora la imagen para un segundo intento de OCR cuando el primero falló.

    Cuatro pasos en orden:
      1. Escalar: el texto de comprobantes en fotos de celular suele estar
         entre 300-500px de ancho efectivo. Tesseract rinde bien con 1200px+.
      2. Grises: elimina interferencia de colores (el amarillo de MP, fondo oscuro)
         y reduce la imagen de 3 canales RGB a 1 — más rápido para Tesseract.
      3. Contraste x2: texto negro → más negro, fondo blanco → más blanco.
      4. Sharpening (dos pasadas): acentúa bordes sin generar artefactos.
         Más de dos pasadas empieza a distorsionar los caracteres.
    """
    ANCHO_MINIMO = 1620  # 2.5x para imágenes de 648px — sweet spot verificado empíricamente
    if imagen.width < ANCHO_MINIMO:
        factor = ANCHO_MINIMO / imagen.width
        nuevo_tamano = (int(imagen.width * factor), int(imagen.height * factor))
        imagen = imagen.resize(nuevo_tamano, Image.Resampling.LANCZOS)

    imagen = imagen.convert("L")
    imagen = ImageEnhance.Contrast(imagen).enhance(2.0)
    imagen = imagen.filter(ImageFilter.SHARPEN)
    imagen = imagen.filter(ImageFilter.SHARPEN)

    return imagen


def recortar_pantalla_opencv(imagen: Image.Image) -> Image.Image | None:
    """
    Intenta detectar la pantalla del celular y retornar un crop rectificado.

    Pipeline:
      1. Autocontrast: normaliza el rango tonal (cubre imágenes con ICC profile que
         tienen max ≈195 en lugar de 255 — sin esto, Canny no ve los bordes).
      2. Escala a 1000px de ancho máximo: normaliza los parámetros de Canny
         independientemente de si la imagen es 648px o 1080px.
      3. Canny + dilate: detecta bordes y los cierra (gaps de 1-2px por compresión JPEG).
      4. Busca el contorno cuadrilátero más grande que cubra ≥20% de la imagen.
      5. Perspective warp: rectifica la perspectiva y retorna el crop como PIL Image.

    Retorna None si no encuentra ningún cuadrilátero suficientemente grande.
    Los callers deben tratar None como "no se pudo hacer crop" y continuar.

    Por qué usar imagen ORIGINAL (antes de invertir_si_oscura):
      La inversión convierte pantallas brillantes en oscuras, ocultando el contraste
      entre la pantalla y el cuerpo del celular. Siempre pasar la imagen sin invertir.
    """
    import cv2

    # 1. Autocontrast para normalizar rango tonal (soluciona ICC profile issue)
    imagen_ac = ImageOps.autocontrast(imagen.convert("RGB"))
    img_array = np.array(imagen_ac)
    h_orig, w_orig = img_array.shape[:2]

    # 2. Escalar a ancho máximo para parámetros Canny consistentes
    target_w = 1000
    scale = min(target_w / w_orig, 1.0)
    if scale < 1.0:
        new_w, new_h = int(w_orig * scale), int(h_orig * scale)
        img_small = cv2.resize(img_array, (new_w, new_h))
    else:
        img_small = img_array
        scale = 1.0

    # 3. Edge detection
    gray = cv2.cvtColor(img_small, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # 4. Buscar contorno cuadrilátero más grande
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours_sorted = sorted(contours, key=cv2.contourArea, reverse=True)
    img_area_small = img_small.shape[0] * img_small.shape[1]

    for contour in contours_sorted[:20]:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) != 4:
            continue

        area_small = cv2.contourArea(approx)
        if area_small < 0.20 * img_area_small:
            continue

        # Reescalar puntos al tamaño original
        pts = (approx.reshape(4, 2) / scale).astype(np.float32)
        rect = ordenar_puntos_cuadrilatero(pts)
        (tl, tr, br, bl) = rect

        # Dimensiones del rectángulo de salida
        ancho = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        alto = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))

        if ancho < 100 or alto < 100:
            continue

        dst = np.array(
            [[0, 0], [ancho - 1, 0], [ancho - 1, alto - 1], [0, alto - 1]],
            dtype=np.float32,
        )
        matriz_perspectiva = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img_array, matriz_perspectiva, (ancho, alto))

        _logger.info(
            f"Pantalla detectada: {ancho}×{alto}px "
            f"(cubre {area_small / img_area_small * 100:.0f}% de la imagen escalada)"
        )
        return Image.fromarray(warped)

    return None
