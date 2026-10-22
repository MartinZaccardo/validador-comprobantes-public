"""crear_tablas_runs_validaciones

Revision ID: a6de1f4cbb10
Revises:
Create Date: 2026-05-25

Tablas:
- runs: cada ejecución del análisis (un "run" procesa todas las respuestas del censo)
- validaciones: resultado de cada imagen analizada dentro de un run
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a6de1f4cbb10'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE runs (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     VARCHAR(50)  NOT NULL,
            iniciado_en   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            finalizado_en TIMESTAMPTZ,
            estado        VARCHAR(20)  NOT NULL DEFAULT 'EN_PROCESO',
            total         INT,
            procesadas    INT NOT NULL DEFAULT 0
        )
    """)

    op.execute("""
        CREATE TABLE validaciones (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id                      UUID REFERENCES runs(id),
            tenant_id                   VARCHAR(50)  NOT NULL,
            respuesta_id                INT          NOT NULL,
            codigo_cliente              VARCHAR(50),
            estado                      VARCHAR(30)  NOT NULL,
            numero_operacion_detectado  VARCHAR(20),
            monto_detectado             FLOAT,
            cuit_destinatario_detectado VARCHAR(20),
            es_comprobante_valido       BOOL,
            mp_status_code              INT,
            error                       TEXT,
            procesado_en                TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            UNIQUE (tenant_id, respuesta_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS validaciones")
    op.execute("DROP TABLE IF EXISTS runs")
