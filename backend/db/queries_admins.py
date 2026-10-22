"""
Queries de la tabla `admins`.

Todas las funciones son síncronas (psycopg2).
Llamar desde contexto async con el helper q() de db.base.
"""
import psycopg2.pool

from db.base import conexion_escritura, conexion_lectura


def _admin_resumen_a_dict(row: tuple) -> dict:
    return {
        "id": row[0], "nombre": row[1], "email": row[2],
        "activo": row[3], "creado_en": row[4].isoformat() if row[4] else None,
        "es_superadmin": row[5],
    }


def obtener_admin_por_email(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    email: str,
) -> dict | None:
    """
    Busca un admin activo por tenant + email.
    Devuelve None si no existe o está inactivo.

    Por qué filtramos activo=true acá y no en el router:
      Si el admin es desactivado (activo=false), el login debe fallar.
      Centralizar el filtro en la query evita que un router olvide chequearlo.
    """
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, tenant_id, email, nombre, password_hash, activo, es_superadmin
                FROM admins
                WHERE tenant_id = %s AND email = %s AND activo = true
                """,
                (tenant_id, email),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "tenant_id": row[1], "email": row[2],
        "nombre": row[3], "password_hash": row[4], "activo": row[5],
        "es_superadmin": row[6],
    }


def obtener_admin_por_id(
    pool: psycopg2.pool.ThreadedConnectionPool,
    admin_id: str,
) -> dict | None:
    """Busca un admin activo por UUID. Devuelve None si no existe o está inactivo."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, tenant_id, email, nombre, activo, es_superadmin, telefono
                FROM admins
                WHERE id = %s::uuid AND activo = true
                """,
                (admin_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "tenant_id": row[1], "email": row[2],
        "nombre": row[3], "activo": row[4], "es_superadmin": row[5],
        "telefono": row[6],
    }


def actualizar_telefono_admin(
    pool: psycopg2.pool.ThreadedConnectionPool,
    admin_id: str,
    telefono: str | None,
) -> dict | None:
    """Actualiza el teléfono de un admin. Devuelve la fila actualizada o None."""
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE admins SET telefono = %s
                WHERE id = %s::uuid AND activo = true
                RETURNING id::text, email, nombre, es_superadmin, telefono
                """,
                (telefono or None, admin_id),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "email": row[1], "nombre": row[2],
        "es_superadmin": row[3], "telefono": row[4],
    }


def listar_admins(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
) -> list[dict]:
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, nombre, email, activo, creado_en, es_superadmin
                FROM admins
                WHERE tenant_id = %s
                ORDER BY creado_en ASC
                """,
                (tenant_id,),
            )
            rows = cur.fetchall()
    return [_admin_resumen_a_dict(r) for r in rows]


def verificar_es_superadmin(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    admin_id: str,
) -> bool:
    """Retorna True si el admin existe y es superadmin, independientemente de si está activo."""
    with conexion_lectura(pool) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT es_superadmin FROM admins WHERE id = %s::uuid AND tenant_id = %s",
            (admin_id, tenant_id),
        )
        row = cur.fetchone()
    return bool(row and row[0])


def toggle_activo_admin(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    admin_id: str,
    activo: bool,
) -> dict | None:
    """
    Activa o desactiva un admin. Devuelve la fila actualizada, o None si no existe.
    El filtro por tenant_id garantiza aislamiento multi-tenant.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE admins SET activo = %s
                WHERE id = %s::uuid AND tenant_id = %s AND es_superadmin = false
                RETURNING id::text, nombre, email, activo, creado_en, es_superadmin
                """,
                (activo, admin_id, tenant_id),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return _admin_resumen_a_dict(row)


def crear_admin(
    pool: psycopg2.pool.ThreadedConnectionPool,
    tenant_id: str,
    email: str,
    nombre: str,
    password_hash: str,
    es_superadmin: bool = False,
) -> str:
    """
    Inserta un nuevo admin. Retorna su UUID como string.
    Lanza psycopg2.errors.UniqueViolation si el email ya existe para ese tenant.
    """
    with conexion_escritura(pool) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admins (tenant_id, email, nombre, password_hash, es_superadmin)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id::text
                """,
                (tenant_id, email, nombre, password_hash, es_superadmin),
            )
            result = cur.fetchone()
    return result[0]
