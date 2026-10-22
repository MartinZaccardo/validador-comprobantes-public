"""
Dependencias reutilizables de FastAPI.

SEGURIDAD — Por qué 401 y no 403:
  401 Unauthorized = "no sé quién sos" (credencial ausente o inválida).
  403 Forbidden    = "sé quién sos pero no tenés permiso".
  Acá el API Key es la credencial de identidad → 401.

SEGURIDAD — Por qué Cookie en lugar de Authorization: Bearer:
  Las cookies httpOnly no son accesibles desde JavaScript — eliminan el
  vector de robo de token por XSS. SameSite=Strict bloquea CSRF.
"""
from typing import Annotated

import psycopg2.pool
import redis.asyncio as aioredis
from config import config
from db import queries_admins
from db.base import q
from db.connection import get_pool as _get_pool
from db.redis import get_cliente_redis
from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError
from services.admins_service import AdminsService
from services.analizar_service import AnalizarService
from services.auth_service import decodificar_token
from services.validaciones_service import ValidacionesService
from services.whatsapp_service import WhatsAppService

def get_db_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """
    Dependencia FastAPI que provee el pool de conexiones a la DB.

    Usar en endpoints como: pool: Annotated[Pool, Depends(get_db_pool)]
    Para tests: app.dependency_overrides[get_db_pool] = lambda: mock_pool
    """
    return _get_pool()


# Alias reutilizable para inyección del pool en endpoints y dependencias.
Pool = Annotated[psycopg2.pool.ThreadedConnectionPool, Depends(get_db_pool)]

Redis = Annotated[aioredis.Redis, Depends(get_cliente_redis)]


async def get_admin_actual(
    pool: Pool,
    access_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    """
    Lee el JWT de la cookie httpOnly, verifica firma y expiración,
    y confirma en DB que el admin sigue activo.
    La consulta a DB garantiza que desactivar un admin tiene efecto inmediato,
    sin esperar a que expire el token.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decodificar_token(access_token)
        admin_id: str | None = payload.get("sub")
        if not admin_id:
            raise JWTError("Token sin campo 'sub'")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin = await q(queries_admins.obtener_admin_por_id, pool, admin_id)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_superadmin_actual(
    admin_payload: Annotated[dict, Depends(get_admin_actual)],
) -> dict:
    """
    Extiende get_admin_actual con un chequeo de rol superadmin.
    Devuelve 403 si el admin autenticado no tiene es_superadmin=True en su JWT.

    Nota: es_superadmin se lee del JWT (no de la DB). Si se agrega un endpoint
    para revocar el rol, hay que agregar un chequeo contra la DB igual que activo.
    Hoy no existe ese endpoint, así que el riesgo es nulo.
    """
    if not admin_payload.get("es_superadmin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de superadmin.",
        )
    return admin_payload


def get_admins_service(pool: Pool) -> AdminsService:
    return AdminsService(pool)


def get_analizar_service(pool: Pool, redis: Redis) -> AnalizarService:
    return AnalizarService(pool, redis)


def get_validaciones_service(pool: Pool) -> ValidacionesService:
    return ValidacionesService(pool)


def get_whatsapp_service(pool: Pool, redis: Redis) -> WhatsAppService:
    return WhatsAppService(pool, redis)


AdminsServiceDep = Annotated[AdminsService, Depends(get_admins_service)]
AnalizarServiceDep = Annotated[AnalizarService, Depends(get_analizar_service)]
ValidacionesServiceDep = Annotated[ValidacionesService, Depends(get_validaciones_service)]
WhatsAppServiceDep = Annotated[WhatsAppService, Depends(get_whatsapp_service)]
