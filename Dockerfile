# ── Stage 1: build del frontend ──────────────────────────────────────────────
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 2: imagen de producción ────────────────────────────────────────────
FROM python:3.12-slim

# Tesseract 5.3.x viene en Debian Bookworm (imagen base de python:3.12-slim).
# tesseract-ocr-spa: sin este paquete lang="spa+eng" ignora el español silenciosamente.
# libglib2.0-0 / libsm6 / libxext6 / libxrender1 / libgl1: dependencias de OpenCV headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python — capa separada para cache de Docker.
# Solo se re-ejecuta cuando cambia requirements.txt.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Pre-descarga del modelo EasyOCR (~300 MB) en build time.
# Con nixpacks ocurría en el primer request → tardaba ~5 min.
# Aquí queda en la capa Docker → solo se re-descarga cuando cambia
# la versión de easyocr en requirements.txt.
RUN python -c "import easyocr; easyocr.Reader(['es', 'en'], gpu=False, verbose=True)"

# Código fuente — al final para no invalidar las capas de deps en cada push.
COPY alembic.ini ./
COPY backend/ backend/
COPY --from=frontend-builder /app/frontend/dist frontend/dist

# WORKDIR al directorio del backend: uvicorn corre desde acá, evita `cd` en el startCommand.
# alembic.ini queda en /app — se referencia con ruta absoluta en railway.toml.
WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Railway sobreescribe este CMD con startCommand de railway.toml.
# Se usa al correr la imagen localmente: docker run --env-file .env -p 8000:8000 <imagen>
CMD ["python", "run.py", "--prod"]
