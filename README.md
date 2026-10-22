# Validador de Comprobantes de Pago

SaaS para validar comprobantes de transferencias de Mercado Pago vía WhatsApp y carga manual desde una interfaz web. Pensado para distribuidoras y comercios argentinos que reciben pagos y necesitan verificarlos antes de operar.

---

## Qué hace

El cliente manda una captura de pantalla del comprobante por WhatsApp. El sistema corre OCR para extraer el número de operación, lo verifica contra la API de Mercado Pago, chequea el CUIT destinatario y el monto, y en pocos segundos devuelve uno de los siguientes resultados:

- **Aprobado** — el pago existe, el monto y destinatario coinciden
- **Duplicado** — el número de operación ya fue validado antes
- **Monto adulterado** — el número de operación existe pero el monto no coincide
- **Pago no acreditado** — el número existe pero el pago no está acreditado en MP
- **Número de operación no encontrado** — el número extraído por OCR no existe en MP
- **Error de destinatario** — el CUIT receptor no coincide con el configurado
- **Imagen inválida** — el OCR no pudo extraer un número de operación legible
- **Revisión manual** — caso ambiguo que requiere que un admin lo revise

Los admins gestionan todo desde un dashboard web: feed en vivo de validaciones del día, historial completo con filtros, padrón de clientes, reverificación manual y actualizaciones en tiempo real vía SSE.

---

## Stack tecnológico

**Backend**

- Python 3.12 · FastAPI · uvicorn
- PostgreSQL (psycopg2 sync + `run_in_executor`) · Alembic
- Redis (Upstash) — fan-out SSE + deduplicación cross-réplica
- Cloudflare R2 (compatible boto3) — almacenamiento de imágenes
- WhatsApp Cloud API (Meta) — canal principal de entrada
- Gemini 2.5 Flash — LLM de visión para OCR (con fallback Tesseract + EasyOCR)
- API de Mercado Pago — verificación de pagos
- JWT HS256 (python-jose) + bcrypt — autenticación de admins
- slowapi — rate limiting · secure — headers HTTP de seguridad · Sentry

**Frontend**

- React 18 · TypeScript · Vite
- shadcn/ui · Tailwind v4
- React Router v7
- Server-Sent Events (SSE) — actualizaciones en tiempo real sin polling

**Infraestructura**

- Railway (backend + PostgreSQL + Redis)
- Cloudflare R2 (object storage)
- GitHub Actions CI (250 tests de integración)

---

## Arquitectura

```
┌──────────────────┐     ┌───────────────────────────────────────────────┐
│ Usuario WhatsApp │────▶│              FastAPI backend                  │
└──────────────────┘     │                                               │
                          │  ┌──────────────┐   ┌──────────────────────┐ │
┌──────────────────┐     │  │ Pipeline OCR  │   │  Núcleo validación   │ │
│  Admin (web UI)  │────▶│  │  Gemini 2.5   │──▶│  · Verificar MP API  │ │
│  (React + Vite)  │     │  │  Flash        │   │  · Chequeo CUIT      │ │
└──────────────────┘     │  │  + Tesseract  │   │  · Guard duplicados  │ │
        ▲                │  │  + EasyOCR    │   │  (Redis Set)         │ │
        │ SSE             │  └──────────────┘   └──────────────────────┘ │
        │                │                                               │
        │                │  ┌──────────┐  ┌───────┐  ┌───────────────┐ │
        └────────────────┤  │ PostgreSQL│  │ Redis │  │ Cloudflare R2 │ │
                          │  └──────────┘  └───────┘  └───────────────┘ │
                          └───────────────────────────────────────────────┘
```

**Modelo de deployment:** un servidor + una base de datos por cliente. Cada instalación está aislada a nivel de infraestructura. Configuración por deployment vía variables de entorno y tabla `tenant_config` en la DB.

---

## Features destacadas

### Pipeline OCR con fallback automático

`procesar_imagen()` corre Gemini 2.5 Flash primero. Si falla, supera el timeout o está desactivado con `LLM_HABILITADO=false`, el sistema cae automáticamente a Tesseract + EasyOCR. Los timeouts son diferenciados por canal: WhatsApp tiene un presupuesto estricto de 13 s (límite de 20 s del webhook de Meta menos margen); la carga manual es más tolerante.

### Guard anti-duplicados con Redis

Un Redis Set (`ops_pendientes:{tenant_id}`) impide que el mismo número de operación sea procesado dos veces de forma concurrente, incluso en escenarios con múltiples réplicas del servidor.

### Actualizaciones en tiempo real vía SSE

El dashboard se suscribe a un canal Redis pub/sub. Cuando una validación se completa (desde cualquier canal), se pushea un `event: validacion` a todas las sesiones de admin conectadas. Sin polling.

### Multi-wallet: soporte para transferencias interbancarias

No todas las transferencias recibidas tienen un ID de pago de Mercado Pago. Las que vienen de bancos externos (por ejemplo Galicia) llegan con un **COELSA ID** — el identificador que usa la cámara compensadora interbancaria argentina para identificar transferencias inmediatas. El sistema detecta el tipo de identificador a partir del output del OCR, clasifica el banco emisor y rutea al path de verificación correspondiente: para COELSA IDs usa el endpoint `/v1/payments/search` de MP para encontrar el pago original.

### Validación HMAC-SHA256 del webhook de WhatsApp

Cada mensaje entrante se verifica contra el header `X-Hub-Signature-256` usando el App Secret de Meta. Requests sin firma válida retornan 403 antes de cualquier procesamiento.

### Padrón de clientes

CRUD completo de clientes del operador: importación masiva por CSV, búsqueda y paginación server-side, y vinculación automática de validaciones a clientes por CUIT (extraído por OCR) o número de teléfono (del remitente en WhatsApp).

### Soft delete + auditoría

Las validaciones nunca se borran físicamente. Una tabla `auditoria` append-only registra cada cambio manual (campo, valor anterior, valor nuevo, quién, cuándo). Las filas eliminadas quedan excluidas de las consultas pero preservadas.

---

## Estructura del proyecto

```
validador-comprobantes/
├── alembic.ini              ← config de migraciones (correr desde la raíz)
├── docker-compose.yml       ← dev local: PostgreSQL en puerto 5433
├── backend/
│   ├── run.py               ← entry point
│   ├── main.py              ← FastAPI app + lifespan + SPA fallback
│   ├── config.py            ← config tipada desde variables de entorno
│   ├── routers/             ← auth · validaciones · analizar · admins · metricas · whatsapp · eventos
│   ├── db/                  ← pool de conexiones · redis · queries por dominio
│   ├── services/
│   │   ├── ocr/             ← paquete OCR (Gemini + Tesseract + EasyOCR)
│   │   ├── validacion_core.py
│   │   ├── mp_client.py
│   │   ├── whatsapp_client.py
│   │   ├── r2_client.py
│   │   └── ...
│   ├── models/              ← resultado.py · tipo_identificador.py
│   ├── migrations/          ← versiones Alembic
│   └── tests/               ← 250 tests de integración
└── frontend/
    ├── src/
    │   ├── pages/           ← Login · Dashboard · Historial · Perfil · Admins · Clientes
    │   ├── components/      ← Sidebar · TablaValidaciones · FiltrosDashboard · ...
    │   ├── api/             ← clientes API tipados
    │   └── lib/             ← utils · helpers de UI
    └── vite.config.ts       ← proxy /api → localhost:8000
```

---

## Desarrollo local

**Requisitos:** Docker Desktop, Python 3.12, Node 22.

```bash
# 1. Clonar el proyecto
git clone https://github.com/MartinZaccardo/validador-comprobantes-public.git
cd validador-comprobantes

# 2. Levantar PostgreSQL (puerto 5433 — evita conflicto con postgres nativo)
docker compose up -d

# 3. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 4. Variables de entorno
cp .env.example .env
# Editar .env — mínimo requerido: DATABASE_URL, TENANT_ID, MP_ACCESS_TOKEN,
# JWT_SECRET_KEY, CUIT_DESTINATARIO

# 5. Correr migraciones (desde la raíz del proyecto)
cd ..
alembic upgrade head

# 6. Crear primer admin
cd backend
python scripts/crear_admin.py

# 7. Levantar backend
py run.py        # Windows
# python run.py  # macOS/Linux
# → http://localhost:8000

# 8. Frontend (terminal aparte)
cd ../frontend
npm install
npm run dev
# → http://localhost:5173
```

**Redis es opcional en dev local.** Dejar `REDIS_URL` vacío en `.env` — la app usa una instancia `fakeredis` en memoria que soporta pub/sub dentro del proceso.

---

## Tests

Los tests requieren una instancia de PostgreSQL corriendo (la del `docker compose up -d` sirve).

```bash
cd backend
pytest tests/ -v
```

Los 250 tests son de integración contra una DB real — no hay mocks en la capa de datos. Los servicios externos (MP, R2, WhatsApp) se mockean en el boundary del servicio.

---

## Deploy en Railway

El repo incluye `nixpacks.toml` y `railway.toml` para deploy en Railway.

El build compila el frontend React (`npm ci && npm run build`) y FastAPI sirve el `dist/` resultante como SPA fallback — un solo servicio de Railway maneja tanto la API como la UI.

Variables de entorno requeridas: ver `.env.example`. Antes de ir a producción: `SECURE_COOKIES=true` y `WHATSAPP_APP_SECRET` no vacío.

---
