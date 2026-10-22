"""add_index_tenant_procesado_en

Revision ID: j9a0b1c2d3e4
Revises: i8f9a0b1c2d3
Create Date: 2026-06-15

Cambios en esta migración:
- validaciones: nuevo índice compuesto (tenant_id, procesado_en DESC)
  Soporta el filtro por tenant_id + ORDER BY procesado_en DESC de
  listar_validaciones (Dashboard/Estadísticas), evitando sequential scan
  a medida que crece el volumen multi-tenant.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'j9a0b1c2d3e4'
down_revision: Union[str, Sequence[str], None] = 'h7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX idx_validaciones_tenant_procesado_en "
        "ON validaciones (tenant_id, procesado_en DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_validaciones_tenant_procesado_en")
