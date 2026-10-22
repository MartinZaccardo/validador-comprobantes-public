"""add_observaciones_to_validaciones

Revision ID: f5c6d7e8a9b0
Revises: e2f3a4b5c6d7
Create Date: 2026-05-29

Cambios en esta migración:
- validaciones: nueva columna observaciones (TEXT, NULL permitido)
  El admin puede anotar contexto libre sobre el comprobante:
  "cliente llamó para aclarar", "foto borrosa, re-enviar", etc.
  NULL = sin observaciones. String vacío no se persiste desde el frontend.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5c6d7e8a9b0'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validaciones",
        sa.Column("observaciones", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("validaciones", "observaciones")
