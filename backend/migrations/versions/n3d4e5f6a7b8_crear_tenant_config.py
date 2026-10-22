"""crear_tenant_config

Revision ID: n3d4e5f6a7b8
Revises: m2c3d4e5f6a7
Create Date: 2026-07-19

Cambios en esta migración:
- Nueva tabla tenant_config: almacena configuración por tenant en un JSONB.
  Permite agregar nuevos clientes sin tocar variables de entorno del servidor.

Campos que se almacenan en el JSONB (definidos en config.py.aplicar_config_tenant):
  cuit_destinatario, mp_access_token,
  whatsapp_token, whatsapp_phone_number_id, whatsapp_verify_token, whatsapp_app_secret,
  llm_habilitado, gemini_api_key

Campos que quedan en .env (infraestructura o iguales para todos los tenants):
  DATABASE_URL, REDIS_URL, R2_*, JWT_SECRET_KEY, SENTRY_DSN,
  TENANT_ID, API_KEY, SECURE_COOKIES, etc.

Flujo de arranque:
  1. config.py lee .env → valores iniciales
  2. main.py lifespan lee tenant_config WHERE tenant_id = $TENANT_ID
  3. Si existe la fila → sobreescribe con DB (sin redeploy para cambios de config)
  4. Si no existe → .env sigue siendo la fuente (primer deploy del tenant)
"""
from alembic import op


revision = "n3d4e5f6a7b8"
down_revision = "m2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenant_config (
            tenant_id   TEXT PRIMARY KEY,
            config      JSONB NOT NULL DEFAULT '{}'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE tenant_config")
