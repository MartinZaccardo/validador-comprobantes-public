"""crear_mensajes_whatsapp_pendientes

Revision ID: r7b8c9d0e1f2
Revises: q6a7b8c9d0e1
Create Date: 2026-08-22

Tabla:
- mensajes_whatsapp_pendientes: registro de mensajes WhatsApp recibidos pero
  aún no procesados. Se inserta antes de lanzar el background task y se borra
  al terminar. En caso de reinicio del servidor, permite recuperar mensajes
  interrumpidos sin pérdida silenciosa.
"""
from alembic import op

revision: str = "r7b8c9d0e1f2"
down_revision = "q6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE mensajes_whatsapp_pendientes (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        TEXT        NOT NULL,
            media_id         TEXT        NOT NULL,
            numero_remitente TEXT        NOT NULL,
            recibido_en      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mensajes_whatsapp_pendientes")
