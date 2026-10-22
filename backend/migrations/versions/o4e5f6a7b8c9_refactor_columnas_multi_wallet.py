"""refactor_columnas_multi_wallet

Revision ID: o4e5f6a7b8c9
Revises: n3d4e5f6a7b8
Create Date: 2026-07-23

Cambios en esta migración:
- numero_operacion_detectado VARCHAR(20) → identificador_pago VARCHAR(50)
  Agrupa N° op MP, COELSA ID y payment_id de fuzzy match en un único campo genérico.
  VARCHAR(20) era insuficiente para COELSA IDs (22 chars).
- baja_confianza_numero → baja_confianza_identificador
  El flag aplica a cualquier tipo de identificador, no solo N° op MP.
- DROP coelsa_id_detectado: absorbido por identificador_pago.
- ADD entidad_emisora VARCHAR(50): banco/billetera detectado por Gemini ("MERCADO_PAGO",
  "GALICIA", "SUPERVIELLE", etc.). String libre — Gemini asigna lo que lee.
- ADD cuit_remitente VARCHAR(20): CUIT del pagador extraído del comprobante.
  Reservado para futura vinculación de clientes por CUIT.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'o4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'n3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('validaciones', 'numero_operacion_detectado',
                    new_column_name='identificador_pago')
    op.alter_column('validaciones', 'identificador_pago',
                    existing_type=sa.String(20),
                    type_=sa.String(50))

    op.alter_column('validaciones', 'baja_confianza_numero',
                    new_column_name='baja_confianza_identificador')

    op.drop_column('validaciones', 'coelsa_id_detectado')

    op.add_column('validaciones', sa.Column('entidad_emisora', sa.String(50), nullable=True))
    op.add_column('validaciones', sa.Column('cuit_remitente', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('validaciones', 'cuit_remitente')
    op.drop_column('validaciones', 'entidad_emisora')

    op.add_column('validaciones', sa.Column('coelsa_id_detectado', sa.String(22), nullable=True))

    op.alter_column('validaciones', 'baja_confianza_identificador',
                    new_column_name='baja_confianza_numero')

    op.alter_column('validaciones', 'identificador_pago',
                    existing_type=sa.String(50),
                    type_=sa.String(20))
    op.alter_column('validaciones', 'identificador_pago',
                    new_column_name='numero_operacion_detectado')
