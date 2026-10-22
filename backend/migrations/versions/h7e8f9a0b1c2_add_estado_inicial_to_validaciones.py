"""add_estado_inicial_to_validaciones

Revision ID: h7e8f9a0b1c2
Revises: g6d7e8f9a0b1
Create Date: 2026-06-01

Cambios en esta migración:
- validaciones: nueva columna estado_inicial (VARCHAR(50), NULL permitido)
  Registra el estado que determinó el sistema al procesar el comprobante.
  Las filas existentes se backfillan con el valor actual de 'estado'.
  Las filas nuevas lo reciben explícitamente en el INSERT.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'g6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validaciones",
        sa.Column("estado_inicial", sa.String(50), nullable=True),
    )
    op.execute("UPDATE validaciones SET estado_inicial = estado WHERE estado_inicial IS NULL")


def downgrade() -> None:
    op.drop_column("validaciones", "estado_inicial")
