"""rename_canal_wpp_to_whatsapp

Revision ID: k0b1c2d3e4f5
Revises: j9a0b1c2d3e4
Create Date: 2026-06-15

Cambios en esta migración:
- validaciones: actualiza canal='WPP' a canal='WhatsApp' (migración de datos).
  Acompaña el rename WPP -> WhatsApp en código/UI.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'k0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'j9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE validaciones SET canal = 'WhatsApp' WHERE canal = 'WPP'")


def downgrade() -> None:
    op.execute("UPDATE validaciones SET canal = 'WPP' WHERE canal = 'WhatsApp'")
