"""add_modificado_por_admin_id

Revision ID: c7a8b9d0e1f2
Revises: b3e2a5f9c401
Create Date: 2026-05-26

Cambios en esta migración:
- validaciones: nueva columna modificado_por_admin_id (FK a admins)
  Se rellena solo cuando un admin edita la fila manualmente.
  NULL = nunca fue editada (o editada antes de esta migración).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7a8b9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'b3e2a5f9c401'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK nullable: las filas existentes no tienen admin que las haya editado.
    # ON DELETE SET NULL: si se borrara un admin (caso raro), las validaciones
    # no se borran — simplemente pierden la referencia al admin.
    op.execute(
        """
        ALTER TABLE validaciones
        ADD COLUMN modificado_por_admin_id UUID
        REFERENCES admins(id) ON DELETE SET NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE validaciones DROP COLUMN IF EXISTS modificado_por_admin_id"
    )
