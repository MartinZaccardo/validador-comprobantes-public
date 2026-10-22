"""
Queries de la tabla `tenant_config`.

Lee la configuración específica de un tenant desde la DB.
Al arrancar, main.py llama a cargar_config_tenant() para sobreescribir los
valores de .env con los de DB si existe una fila para el tenant activo.
"""
import psycopg2.extras
import psycopg2.pool

from db.base import conexion_escritura, conexion_lectura


def cargar_config_tenant(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
) -> dict | None:
    """
    Devuelve el JSONB de config para el tenant, o None si no existe la fila.
    psycopg2 deserializa JSONB a dict automáticamente.
    """
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT config FROM tenant_config WHERE tenant_id = %s",
            (tenant_id,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def guardar_config_tenant(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    config_dict: dict,
) -> None:
    """
    Inserta o actualiza la config de un tenant (upsert).
    Usado para sembrar la configuración inicial desde .env o actualizarla.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO tenant_config (tenant_id, config)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (tenant_id) DO UPDATE SET config = EXCLUDED.config
                """,
            (tenant_id, psycopg2.extras.Json(config_dict)),
        )
