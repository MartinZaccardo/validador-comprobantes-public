"""soft_delete_validaciones

Revision ID: m2c3d4e5f6a7
Revises: l1b2c3d4e5f6
Create Date: 2026-07-18

Cambios en esta migración:
- validaciones: 2 columnas nuevas para soft delete
  - eliminado_en: timestamp de cuándo fue eliminado (NULL = activo)
  - eliminado_por: UUID del admin que lo eliminó (NULL = activo)

Por qué soft delete y no hard delete:
  Los registros financieros requieren trazabilidad. El admin puede eliminar
  por error; con soft delete la fila se puede recuperar desde la DB.
  La imagen en R2 también se preserva (no se borra al eliminar).

Queries afectadas por esta migración:
  - listar_validaciones:       AND eliminado_en IS NULL
  - obtener_metricas:          AND eliminado_en IS NULL
  - obtener_validacion_por_id: AND eliminado_en IS NULL
  - ya_procesada:              SIN filtro (no re-procesar imágenes eliminadas)
  - obtener_ops_aprobadas:     SIN filtro (APROBADO eliminado sigue bloqueando duplicados)
"""
from alembic import op


revision = "m2c3d4e5f6a7"
down_revision = "l1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE validaciones ADD COLUMN eliminado_en  TIMESTAMPTZ")
    op.execute("ALTER TABLE validaciones ADD COLUMN eliminado_por UUID")


def downgrade() -> None:
    op.execute("ALTER TABLE validaciones DROP COLUMN eliminado_por")
    op.execute("ALTER TABLE validaciones DROP COLUMN eliminado_en")
