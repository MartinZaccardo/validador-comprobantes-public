"""
Hashing de contraseñas y tokens JWT.

bcrypt es intencionalmente lento — fuerza bruta impracticable. El cost factor
(rounds=12) se puede subir si el hardware lo permite en el futuro.

JWT usa HS256 (firma simétrica): misma clave para firmar y verificar.
Correcto para una API centralizada. Si hubiera múltiples emisores, migrar a RS256.
"""
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from config import config
from jose import jwt

_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas


def validar_fortaleza_password(password: str) -> None:
    """
    Valida que la contraseña cumpla la política mínima antes de hashearla.
    Lanza ValueError con mensaje descriptivo si no cumple.

    Política: mínimo 8 caracteres + al menos 3 de 4 clases de caracteres.
    "3 de 4" es el estándar de muchas aplicaciones bancarias: es más flexible
    que exigir las 4 clases (permite passphrases largas sin especiales) y más
    fuerte que solo pedir longitud.
    """
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")

    tiene_mayuscula = any(c.isupper() for c in password)
    tiene_minuscula = any(c.islower() for c in password)
    tiene_digito    = any(c.isdigit() for c in password)
    tiene_especial  = any(not c.isalnum() for c in password)

    clases = sum([tiene_mayuscula, tiene_minuscula, tiene_digito, tiene_especial])
    if clases < 3:
        raise ValueError(
            "La contraseña debe incluir al menos 3 de estas 4 clases: "
            "mayúsculas, minúsculas, dígitos, caracteres especiales (!@#$ etc.)."
        )


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def crear_access_token(admin_id: str, email: str, nombre: str, es_superadmin: bool = False) -> str:
    """
    Genera un JWT firmado con los datos del admin.
    sub/email/nombre en el payload evitan requests extra a DB en cada endpoint.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": admin_id,
        "email": email,
        "nombre": nombre,
        "es_superadmin": es_superadmin,
        "exp": expire,
    }
    return jwt.encode(payload, config.jwt_secret_key, algorithm=config.jwt_algorithm)


def decodificar_token(token: str) -> dict:
    """Decodifica y valida un JWT. Lanza JWTError si la firma, expiración o formato son inválidos."""
    return jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
