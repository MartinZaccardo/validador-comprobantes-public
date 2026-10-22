"""schema_v2_admins_canal_vendedor

Revision ID: b3e2a5f9c401
Revises: a6de1f4cbb10
Create Date: 2026-05-26

Cambios en esta migración:
- validaciones: nuevas columnas (codigo_vendedor, canal, fecha_modificacion, imagen_path)
- validaciones: respuesta_id pasa a ser nullable (para uploads manuales)
- validaciones: la constraint UNIQUE pasa a ser un índice PARCIAL que solo aplica
                cuando respuesta_id IS NOT NULL (permite múltiples rows manuales)
- Nueva tabla: admins  (login de administradores con email + password_hash)
- Nueva tabla: auditoria  (log inmutable de cambios manuales en validaciones)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3e2a5f9c401'
down_revision: Union[str, Sequence[str], None] = 'a6de1f4cbb10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Nuevas columnas en validaciones
    # ------------------------------------------------------------------

    # codigo_vendedor: identificador del remitente en integraciones externas.
    # Nullable porque los datos históricos ya en DB no lo tienen.
    op.execute("ALTER TABLE validaciones ADD COLUMN codigo_vendedor VARCHAR(50)")

    # canal: origen del comprobante (MANUAL | WhatsApp).
    # NOT NULL garantiza que nunca tengamos filas sin origen.
    op.execute(
        "ALTER TABLE validaciones ADD COLUMN canal VARCHAR(20) NOT NULL DEFAULT 'MANUAL'"
    )

    # fecha_modificacion: se rellena solo cuando un admin edita la fila manualmente.
    # Nullable: NULL significa "nunca fue editada manualmente".
    op.execute("ALTER TABLE validaciones ADD COLUMN fecha_modificacion TIMESTAMPTZ")

    # imagen_path: ruta relativa a la imagen guardada en disco.
    # Solo se usa cuando canal = 'MANUAL'. Nullable para los demás canales.
    op.execute("ALTER TABLE validaciones ADD COLUMN imagen_path TEXT")

    # ------------------------------------------------------------------
    # 2. respuesta_id pasa a nullable
    # ------------------------------------------------------------------
    # Los uploads manuales no tienen respuesta_id. Necesitamos permitir NULL.
    op.execute(
        "ALTER TABLE validaciones ALTER COLUMN respuesta_id DROP NOT NULL"
    )

    # ------------------------------------------------------------------
    # 3. Reemplazar el UNIQUE constraint por un índice PARCIAL
    # ------------------------------------------------------------------
    # El constraint original era: UNIQUE (tenant_id, respuesta_id)
    # Problema: con respuesta_id nullable, dos filas con NULL violarían
    # el constraint en algunos motores (PostgreSQL trata NULLs como distintos
    # en índices UNIQUE, así que técnicamente no habría conflicto, pero
    # es más claro y explícito usar un índice PARCIAL que solo aplica
    # cuando respuesta_id IS NOT NULL).
    op.execute(
        "ALTER TABLE validaciones DROP CONSTRAINT validaciones_tenant_id_respuesta_id_key"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX validaciones_tenant_respuesta_unique
        ON validaciones (tenant_id, respuesta_id)
        WHERE respuesta_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 4. Tabla admins
    # ------------------------------------------------------------------
    # Cada admin pertenece a un tenant. El email es único por tenant
    # (dos tenants distintos pueden tener admin@empresa.com).
    # password_hash: bcrypt hash de la contraseña. NUNCA se guarda la
    # contraseña en texto plano.
    op.execute("""
        CREATE TABLE admins (
            id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     VARCHAR(50) NOT NULL,
            email         VARCHAR(255) NOT NULL,
            nombre        VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            activo        BOOL        NOT NULL DEFAULT true,
            creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, email)
        )
    """)

    # ------------------------------------------------------------------
    # 5. Tabla auditoria
    # ------------------------------------------------------------------
    # Log append-only de cambios manuales en validaciones.
    # Campos:
    #   campo          — qué se modificó: 'numero_operacion' | 'estado'
    #   valor_anterior — valor antes del cambio (NULL si era NULL)
    #   valor_nuevo    — valor después del cambio
    #   timestamp      — cuándo ocurrió
    #
    # Por qué no usamos ON DELETE CASCADE en validacion_id:
    #   La auditoría debe sobrevivir aunque se borre la validación
    #   (en el futuro). Si se borran validaciones históricas, queremos
    #   el log igual. ON DELETE RESTRICT (default) evita borrados
    #   accidentales que perderían historial.
    op.execute("""
        CREATE TABLE auditoria (
            id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            admin_id      UUID        NOT NULL REFERENCES admins(id),
            validacion_id UUID        NOT NULL REFERENCES validaciones(id),
            campo         TEXT        NOT NULL,
            valor_anterior TEXT,
            valor_nuevo   TEXT        NOT NULL,
            timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Índice para consultas frecuentes: "dame la auditoría de esta validación"
    op.execute(
        "CREATE INDEX idx_auditoria_validacion_id ON auditoria (validacion_id)"
    )


def downgrade() -> None:
    # Revertir en orden inverso al upgrade

    op.execute("DROP INDEX IF EXISTS idx_auditoria_validacion_id")
    op.execute("DROP TABLE IF EXISTS auditoria")
    op.execute("DROP TABLE IF EXISTS admins")

    op.execute("DROP INDEX IF EXISTS validaciones_tenant_respuesta_unique")

    # Restaurar el constraint original (solo funciona si no hay NULLs en respuesta_id)
    op.execute(
        "ALTER TABLE validaciones ADD CONSTRAINT validaciones_tenant_id_respuesta_id_key "
        "UNIQUE (tenant_id, respuesta_id)"
    )

    op.execute(
        "ALTER TABLE validaciones ALTER COLUMN respuesta_id SET NOT NULL"
    )

    op.execute("ALTER TABLE validaciones DROP COLUMN IF EXISTS imagen_path")
    op.execute("ALTER TABLE validaciones DROP COLUMN IF EXISTS fecha_modificacion")
    op.execute("ALTER TABLE validaciones DROP COLUMN IF EXISTS canal")
    op.execute("ALTER TABLE validaciones DROP COLUMN IF EXISTS codigo_vendedor")
