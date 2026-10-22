"""crear_tablas_clientes

Revision ID: p5f6a7b8c9d0
Revises: o4e5f6a7b8c9
Create Date: 2026-08-03

Tablas:
- clientes: padrón de clientes del operador
- clientes_telefonos: teléfonos asociados a un cliente (N:1)
- clientes_cuits: CUITs asociados a un cliente (N:1)

Diseño:
- Sin tenant_id: arquitectura es un servidor + DB por cliente; no hay
  aislamiento por tenant necesario en esta DB.
- codigo_cliente: identificador único del sistema del operador; es el mismo
  código que viaja por WhatsApp y análisis manual.
- UNIQUE(telefono) y UNIQUE(cuit): un número/CUIT solo puede pertenecer
  a un cliente — garantizado a nivel de DB.
- ON DELETE CASCADE: si se elimina un cliente, sus teléfonos y CUITs
  se eliminan automáticamente.
"""
from alembic import op

revision: str = "p5f6a7b8c9d0"
down_revision = "o4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE clientes (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            codigo_cliente VARCHAR(50)  NOT NULL UNIQUE,
            razon_social   VARCHAR(200) NOT NULL,
            direccion      VARCHAR(300),
            activo         BOOL NOT NULL DEFAULT TRUE,
            creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE clientes_telefonos (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cliente_id UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            telefono   VARCHAR(30) NOT NULL,
            UNIQUE(telefono)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE clientes_cuits (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cliente_id UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            cuit       VARCHAR(20) NOT NULL,
            UNIQUE(cuit)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS clientes_cuits")
    op.execute("DROP TABLE IF EXISTS clientes_telefonos")
    op.execute("DROP TABLE IF EXISTS clientes")
