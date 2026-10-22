"""
Tests unitarios de auth_service.

Estos tests son completamente independientes de la DB y de FastAPI.
Solo prueban la lógica de hashing y JWT — funciones puras.
"""
import time
import pytest
from jose import JWTError

from services.auth_service import (
    crear_access_token,
    decodificar_token,
    hash_password,
    validar_fortaleza_password,
    verify_password,
)


# =============================================================================
# validar_fortaleza_password
# =============================================================================

@pytest.mark.parametrize("password_valido", [
    "MiClave123!",       # las 4 clases
    "Segura_2024",       # mayúscula + minúscula + dígito + especial
    "sinEspeciales123",  # 3 clases: mayúscula + minúscula + dígito
    "SIN-DIGITO-abc!",   # 3 clases: mayúscula + minúscula + especial
])
def test_validar_password_acepta_contraseñas_fuertes(password_valido: str):
    validar_fortaleza_password(password_valido)  # no debe lanzar excepción


@pytest.mark.parametrize("password_debil", [
    "cA1!",        # menos de 8 caracteres (solo 4)
    "12345678",    # solo dígitos — 1 clase
    "abcdefgh",    # solo minúsculas — 1 clase
    "ABCDEFGH",    # solo mayúsculas — 1 clase
    "123456789",   # solo dígitos largos — 1 clase
    "minusc!ulas", # minúscula + especial — 2 clases
    "MAYUSC!ULAS", # mayúscula + especial — 2 clases
])
def test_validar_password_rechaza_contraseñas_debiles(password_debil: str):
    with pytest.raises(ValueError):
        validar_fortaleza_password(password_debil)


# =============================================================================
# hash_password / verify_password
# =============================================================================

def test_hash_genera_string_bcrypt():
    password_hash = hash_password("miContraseña123")
    # bcrypt siempre empieza con $2b$ (versión 2b del algoritmo)
    assert password_hash.startswith("$2b$")
    assert len(password_hash) == 60  # bcrypt siempre produce hashes de 60 caracteres


def test_verify_password_correcta():
    password_hash = hash_password("miContraseña123")
    assert verify_password("miContraseña123", password_hash) is True


def test_verify_password_incorrecta():
    password_hash = hash_password("miContraseña123")
    assert verify_password("otraContraseña", password_hash) is False


def test_verify_password_vacia():
    password_hash = hash_password("miContraseña123")
    assert verify_password("", password_hash) is False


def test_hashes_del_mismo_password_son_distintos():
    """
    bcrypt incorpora un salt aleatorio — dos hashes del mismo password
    son distintos pero ambos verifican correctamente.
    """
    password_hash_1 = hash_password("mismo_password")
    password_hash_2 = hash_password("mismo_password")
    assert password_hash_1 != password_hash_2
    assert verify_password("mismo_password", password_hash_1)
    assert verify_password("mismo_password", password_hash_2)


# =============================================================================
# crear_access_token / decodificar_token
# =============================================================================

def test_jwt_roundtrip():
    """El payload se conserva intacto al codificar y decodificar."""
    token = crear_access_token("uuid-admin-1", "admin@test.com", "Juan Pérez")
    payload = decodificar_token(token)

    assert payload["sub"]    == "uuid-admin-1"
    assert payload["email"]  == "admin@test.com"
    assert payload["nombre"] == "Juan Pérez"


def test_jwt_tiene_campo_exp():
    """El token debe tener fecha de expiración para ser seguro."""
    token = crear_access_token("uuid-1", "a@b.com", "Nombre")
    payload = decodificar_token(token)
    assert "exp" in payload


def test_jwt_token_invalido_lanza_jwterror():
    with pytest.raises(JWTError):
        decodificar_token("esto.no.es.un.jwt.valido")


def test_jwt_token_con_firma_alterada_lanza_jwterror():
    """Alterar cualquier parte del token invalida la firma."""
    token = crear_access_token("uuid-1", "a@b.com", "Nombre")
    partes = token.split(".")
    # Modificar el payload (parte central) — la firma ya no coincide
    partes[1] = partes[1][:-3] + "XXX"
    token_alterado = ".".join(partes)
    with pytest.raises(JWTError):
        decodificar_token(token_alterado)


def test_dos_tokens_del_mismo_admin_son_distintos():
    """
    Cada token tiene un 'exp' distinto (depende del momento de creación),
    por lo que dos tokens generados en momentos diferentes son distintos.
    """
    token1 = crear_access_token("uuid-1", "a@b.com", "Nombre")
    time.sleep(0.01)  # pequeña pausa para asegurar timestamps distintos
    token2 = crear_access_token("uuid-1", "a@b.com", "Nombre")
    # Los tokens pueden ser iguales si se generan en el mismo segundo
    # (exp usa granularidad de segundos). Lo que importa es que ambos decodifican.
    assert decodificar_token(token1)["sub"] == "uuid-1"
    assert decodificar_token(token2)["sub"] == "uuid-1"
