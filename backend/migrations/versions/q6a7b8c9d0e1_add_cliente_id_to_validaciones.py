"""add_cliente_id_to_validaciones

Revision ID: q6a7b8c9d0e1
Revises: p5f6a7b8c9d0
Create Date: 2026-08-06

Vinculación validaciones → clientes:
- cliente_id: FK nullable a clientes.id, ON DELETE SET NULL.
  Se llena por auto-vinculación (CUIT o teléfono) o resolución de codigo_cliente en el pipeline.
  NULL cuando el comprobante no matchea ningún cliente registrado.
- ON DELETE SET NULL: si se elimina un cliente en el futuro, las validaciones históricas
  no se pierden — solo pierden la referencia FK.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "q6a7b8c9d0e1"
down_revision = "p5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("validaciones", sa.Column("cliente_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_validaciones_cliente_id",
        "validaciones",
        "clientes",
        ["cliente_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_validaciones_cliente_id", "validaciones", ["cliente_id"])


def downgrade() -> None:
    op.drop_index("ix_validaciones_cliente_id", table_name="validaciones")
    op.drop_constraint("fk_validaciones_cliente_id", "validaciones", type_="foreignkey")
    op.drop_column("validaciones", "cliente_id")
