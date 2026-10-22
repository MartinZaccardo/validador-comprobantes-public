"""
Queries de la tabla `mensajes_whatsapp_pendientes`.

Todas las funciones son síncronas (psycopg2).
Llamar desde contexto async con el helper q() de db.base.
"""
import psycopg2.pool

from db.base import conexion_escritura, conexion_lectura


def crear_mensaje_pendiente(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    media_id: str,
    numero_remitente: str,
) -> None:
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mensajes_whatsapp_pendientes (tenant_id, media_id, numero_remitente)
            VALUES (%s, %s, %s)
            """,
            (tenant_id, media_id, numero_remitente),
        )


def eliminar_mensaje_pendiente(
    pool: psycopg2.pool.ThreadedConnectionPool,
    media_id: str,
) -> None:
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM mensajes_whatsapp_pendientes WHERE media_id = %s",
            (media_id,),
        )


def obtener_mensajes_pendientes(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
) -> list[dict]:
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT media_id, numero_remitente
            FROM mensajes_whatsapp_pendientes
            WHERE tenant_id = %s
            ORDER BY recibido_en
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()
    return [{"media_id": r[0], "numero_remitente": r[1]} for r in rows]
