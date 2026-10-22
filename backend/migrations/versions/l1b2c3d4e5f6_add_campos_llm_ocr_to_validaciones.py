"""add_campos_llm_ocr_to_validaciones

Revision ID: l1b2c3d4e5f6
Revises: k0b1c2d3e4f5
Create Date: 2026-06-18

Cambios en esta migración:
- validaciones: 6 columnas nuevas para el pipeline Vision LLM (MVP11)
  - ocr_fuente: qué motor extrajo los datos ("llm_gemini" / "tesseract" / "sin_datos")
  - ocr_confianza: score 0.0–1.0 reportado por el LLM (NULL si usó Tesseract)
  - fecha_comprobante: fecha del comprobante en formato DATE (para auditoría y Excel)
  - cvu_cbu_destinatario: CVU/CBU del receptor detectado en la imagen (22 dígitos)
  - baja_confianza_numero: True si las dos extracciones del número de operación
    difieren — indica que no se llamó a MP y el estado es OPERACION_SOSPECHOSA
  - coelsa_id_detectado: ID COELSA de 22 chars (reservado para soporte multi-banco,
    sin lógica activa en esta fase)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'k0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('validaciones', sa.Column('ocr_fuente', sa.String(20), nullable=True))
    op.add_column('validaciones', sa.Column('ocr_confianza', sa.Float(), nullable=True))
    op.add_column('validaciones', sa.Column('fecha_comprobante', sa.Date(), nullable=True))
    op.add_column('validaciones', sa.Column('cvu_cbu_destinatario', sa.String(22), nullable=True))
    op.add_column('validaciones', sa.Column(
        'baja_confianza_numero',
        sa.Boolean(),
        nullable=False,
        server_default='false',
    ))
    op.add_column('validaciones', sa.Column('coelsa_id_detectado', sa.String(22), nullable=True))


def downgrade() -> None:
    op.drop_column('validaciones', 'coelsa_id_detectado')
    op.drop_column('validaciones', 'baja_confianza_numero')
    op.drop_column('validaciones', 'cvu_cbu_destinatario')
    op.drop_column('validaciones', 'fecha_comprobante')
    op.drop_column('validaciones', 'ocr_confianza')
    op.drop_column('validaciones', 'ocr_fuente')
