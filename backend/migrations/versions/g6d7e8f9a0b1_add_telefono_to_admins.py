"""add_telefono_to_admins

Revision ID: g6d7e8f9a0b1
Revises: f5c6d7e8a9b0
Create Date: 2026-05-30

Cambios en esta migración:
- admins: nueva columna telefono (VARCHAR(20), NULL permitido)
  El admin puede registrar su número de contacto desde la página de perfil.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g6d7e8f9a0b1'
down_revision: Union[str, Sequence[str], None] = 'f5c6d7e8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("telefono", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("admins", "telefono")
