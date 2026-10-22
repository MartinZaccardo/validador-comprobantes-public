"""add_creado_por_admin_id

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-05-29

Cambios en esta migración:
- validaciones: nueva columna creado_por_admin_id (FK a admins, NULL permitido)
  Se rellena solo en canal='MANUAL' con el id del admin que subió la imagen.
  NULL en canal='WhatsApp' — ese canal no tiene admin creador.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validaciones",
        sa.Column(
            "creado_por_admin_id",
            sa.UUID(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("validaciones", "creado_por_admin_id")
