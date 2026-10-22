"""add_es_superadmin

Revision ID: d1e2f3a4b5c6
Revises: c7a8b9d0e1f2
Create Date: 2026-05-29

Cambios en esta migración:
- admins: nueva columna es_superadmin BOOLEAN NOT NULL DEFAULT false
  El data-migration marca como superadmin al primer admin creado por tenant,
  para que el operador que ya existe no quede sin acceso a la gestión de admins.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c7a8b9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("es_superadmin", sa.Boolean(), nullable=False, server_default="false"))

    # Data migration: el primer admin de cada tenant (el que ya existe) pasa a ser superadmin.
    # En un tenant con un solo admin, esto garantiza que no quede nadie bloqueado.
    op.execute("""
        UPDATE admins SET es_superadmin = true
        WHERE id IN (
            SELECT DISTINCT ON (tenant_id) id
            FROM admins
            ORDER BY tenant_id, creado_en ASC
        )
    """)


def downgrade() -> None:
    op.drop_column("admins", "es_superadmin")
