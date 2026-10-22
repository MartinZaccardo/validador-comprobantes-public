"""
Endpoints de autenticación de administradores.

Seguridad: el mensaje de error en login es genérico tanto si el email no existe
como si la contraseña es incorrecta — evita user enumeration (timing attack).
El JWT se entrega como cookie httpOnly: JavaScript no puede leerlo, lo que
elimina el riesgo de robo por XSS. SameSite=Strict bloquea CSRF.
"""
import re
from typing import Annotated

from config import config
from db.base import q
from db.queries_admins import (
    actualizar_telefono_admin,
    obtener_admin_por_email,
    obtener_admin_por_id,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from limiter import limiter
from pydantic import BaseModel, EmailStr, field_validator
from services.auth_service import crear_access_token, verify_password

from routers.deps import Pool, get_admin_actual

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "access_token"
_COOKIE_MAX_AGE = 60 * 60 * 24  # 24 horas en segundos
# Hash dummy para que verify_password siempre corra y el tiempo sea uniforme (anti-timing attack)
_DUMMY_HASH = "$2b$12$KIXoGW4n3WxMZPdMpHC6/.oXMpHV4nPlcBr9oGLy2l.8r55Y5ZN7e"


# ---------------------------------------------------------------------------
# Modelos de request / response
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminInfo(BaseModel):
    id: str
    nombre: str
    email: str
    es_superadmin: bool = False
    telefono: str | None = None


class LoginResponse(BaseModel):
    admin: AdminInfo


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
@limiter.limit(config.rate_limit_login)
async def login(request: Request, body: LoginRequest, response: Response, pool: Pool) -> LoginResponse:
    """Autentica un admin y establece una cookie httpOnly con el JWT."""
    admin = await q(obtener_admin_por_email, pool, config.tenant_id, body.email)

    hash_a_verificar = admin["password_hash"] if admin else _DUMMY_HASH

    contrasena_ok = verify_password(body.password, hash_a_verificar)

    if not admin or not contrasena_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = crear_access_token(
        admin_id=admin["id"],
        email=admin["email"],
        nombre=admin["nombre"],
        es_superadmin=admin["es_superadmin"],
    )

    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=config.secure_cookies,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )

    return LoginResponse(
        admin=AdminInfo(
            id=admin["id"],
            nombre=admin["nombre"],
            email=admin["email"],
            es_superadmin=admin["es_superadmin"],
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Elimina la cookie de sesión del browser."""
    response.delete_cookie(
        key=_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=config.secure_cookies,
        samesite="strict",
    )


@router.get("/me", response_model=AdminInfo)
async def me(
    pool: Pool,
    admin_payload: Annotated[dict, Depends(get_admin_actual)],
) -> AdminInfo:
    """
    Devuelve la información del admin autenticado.
    Consulta la DB para incluir telefono fresco (puede cambiar sin renovar el JWT).
    """
    admin = await q(obtener_admin_por_id, pool, admin_payload["sub"])
    return AdminInfo(
        id=admin_payload["sub"],
        email=admin_payload["email"],
        nombre=admin_payload.get("nombre", ""),
        es_superadmin=admin_payload.get("es_superadmin", False),
        telefono=admin["telefono"] if admin else None,
    )


class ActualizarPerfilBody(BaseModel):
    telefono: str | None = None

    @field_validator("telefono", mode="before")
    @classmethod
    def validar_telefono(cls, v: object) -> str | None:
        if v is None or str(v).strip() == "":
            return None
        solo_digitos = re.sub(r"[^\d+]", "", str(v))
        if not (7 <= len(solo_digitos) <= 15):
            raise ValueError("Formato de teléfono inválido (7-15 dígitos)")
        return str(v).strip()


@router.patch("/me", response_model=AdminInfo)
async def actualizar_perfil(
    body: ActualizarPerfilBody,
    pool: Pool,
    admin_payload: Annotated[dict, Depends(get_admin_actual)],
) -> AdminInfo:
    """Actualiza datos editables del perfil propio (por ahora: teléfono)."""
    admin = await q(
        actualizar_telefono_admin,
        pool,
        admin_payload["sub"],
        body.telefono,
    )
    if admin is None:
        raise HTTPException(status_code=404, detail="Admin no encontrado.")
    return AdminInfo(
        id=admin["id"],
        email=admin["email"],
        nombre=admin["nombre"],
        es_superadmin=admin["es_superadmin"],
        telefono=admin["telefono"],
    )
