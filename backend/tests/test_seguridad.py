"""
Ciberataque controlado — vectores de seguridad del sistema.

Cubre los vectores no testeados en otros módulos:
  · JWT Forgery: token firmado con clave incorrecta
  · JWT expirado: el backend rechaza tokens con exp en el pasado
  · Admin desactivado mid-session: JWT válido pero admin ya inactivo en DB
  · SQL injection en filtros de texto libre: numero_operacion y codigo_cliente
  · Path traversal: SPA handler no sirve archivos fuera de frontend/dist

Vectores YA cubiertos en otros test modules (no se duplican aquí):
  · IDOR / aislamiento multi-tenant  → test_validaciones.py
  · Escalada de privilegios (403)    → test_admins.py
  · Upload de archivos no-imagen     → test_analizar.py
  · Whitelist de estado/canal (400)  → test_validaciones.py
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jose import jwt as jose_jwt

import db.connection as db_conn
from config import config
from db import queries_admins
from services.auth_service import crear_access_token, hash_password


# =============================================================================
# JWT Forgery — token con firma inválida o payload expirado
# =============================================================================

def test_jwt_con_clave_incorrecta_devuelve_401(client, admin_test):
    """
    Atacante construye un token usando una clave secreta falsa.
    decodificar_token verifica la firma con config.jwt_secret_key →
    la firma no coincide → JWTError → 401.
    """
    token_falso = jose_jwt.encode(
        {
            "sub": str(admin_test["id"]),
            "email": admin_test["email"],
            "nombre": admin_test["nombre"],
        },
        "clave_falsa_del_atacante_32bytes!!",
        algorithm=config.jwt_algorithm,
    )
    resp = client.get(
        "/api/validaciones",
        cookies={"access_token": token_falso},
    )
    assert resp.status_code == 401


def test_jwt_expirado_devuelve_401(client, admin_test):
    """
    Token firmado con la clave correcta pero con exp en el pasado.
    jose verifica el campo exp antes de devolver el payload → 401.
    """
    token_expirado = jose_jwt.encode(
        {
            "sub": str(admin_test["id"]),
            "email": admin_test["email"],
            "nombre": admin_test["nombre"],
            "es_superadmin": False,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
    )
    resp = client.get(
        "/api/validaciones",
        cookies={"access_token": token_expirado},
    )
    assert resp.status_code == 401


def test_jwt_superadmin_falso_rechazado_en_endpoint_superadmin(client, admin_test):
    """
    Atacante crea un token con es_superadmin=True firmado con clave incorrecta.
    La firma inválida causa 401 antes de llegar al check de permisos.
    Verifica que el payload nunca se acepta sin validar la firma primero.
    """
    token_falso = jose_jwt.encode(
        {
            "sub": str(admin_test["id"]),
            "email": admin_test["email"],
            "nombre": admin_test["nombre"],
            "es_superadmin": True,
        },
        "clave_falsa_del_atacante_32bytes!!",
        algorithm=config.jwt_algorithm,
    )
    resp = client.get(
        "/api/admins",
        cookies={"access_token": token_falso},
    )
    assert resp.status_code == 401


# =============================================================================
# Admin desactivado mid-session
# =============================================================================

_EMAIL_ADMIN_DESACTIVADO = "seg_desactivado@validador-tests.com"


@pytest.fixture
def admin_con_token_activo(client):
    """
    Crea un admin activo y devuelve su JWT. Scope función: fixture fresco por test.
    El admin se borra en teardown (no re-activamos, directamente se elimina).
    """
    pool = db_conn.get_pool()

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE email = %s", (_EMAIL_ADMIN_DESACTIVADO,))
        conn.commit()
    finally:
        pool.putconn(conn)

    admin_id = queries_admins.crear_admin(
        pool,
        config.tenant_id,
        _EMAIL_ADMIN_DESACTIVADO,
        "Admin Desactivado Test",
        hash_password("TestPass_123!"),
    )
    token = crear_access_token(
        admin_id=admin_id,
        email=_EMAIL_ADMIN_DESACTIVADO,
        nombre="Admin Desactivado Test",
    )

    yield {"id": admin_id, "token": token}

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE email = %s", (_EMAIL_ADMIN_DESACTIVADO,))
        conn.commit()
    finally:
        pool.putconn(conn)


def test_jwt_valido_pero_admin_desactivado_devuelve_401(client, admin_con_token_activo):
    """
    get_admin_actual consulta la DB para verificar activo=True en cada request.
    Si el admin fue desactivado después de emitir el JWT, el token se rechaza
    inmediatamente — sin esperar a que expire el token (7 días).

    Flujo del ataque:
      1. Admin recibe un JWT válido.
      2. Superadmin desactiva al admin en la plataforma.
      3. Admin intenta usar el mismo JWT → debe recibir 401.
    """
    pool = db_conn.get_pool()
    token = admin_con_token_activo["token"]
    admin_id = admin_con_token_activo["id"]

    # Con el admin activo el JWT funciona normalmente
    resp = client.get("/api/validaciones", cookies={"access_token": token})
    assert resp.status_code == 200

    # Desactivar el admin directamente en DB (simula el PATCH /api/admins/{id}/activo)
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE admins SET activo = FALSE WHERE id = %s::uuid", (admin_id,))
        conn.commit()
    finally:
        pool.putconn(conn)

    # El mismo JWT ahora debe ser rechazado
    resp = client.get("/api/validaciones", cookies={"access_token": token})
    assert resp.status_code == 401


# =============================================================================
# SQL injection en filtros de texto libre (ILIKE)
# =============================================================================

_PAYLOADS_SQL_INJECTION = [
    "'; DROP TABLE validaciones; --",
    "' OR '1'='1",
    "\" OR 1=1--",
    "%' OR 1=1--",
    "' UNION SELECT id, email, password_hash FROM admins--",
]


@pytest.mark.parametrize("payload", _PAYLOADS_SQL_INJECTION)
def test_sql_injection_en_numero_operacion_no_produce_error(client, admin_token, payload):
    """
    numero_operacion se pasa como parámetro %s en la cláusula ILIKE.
    psycopg2 escapa el input → el payload se trata como string literal,
    no como SQL → sin error 500, sin data leak.
    """
    resp = client.get(
        "/api/validaciones",
        params={"numero_operacion": payload},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.parametrize("payload", _PAYLOADS_SQL_INJECTION)
def test_sql_injection_en_codigo_cliente_no_produce_error(client, admin_token, payload):
    """
    codigo_cliente también usa ILIKE con parámetro %s → mismo escenario.
    El payload no puede escapar del contexto ILIKE ni ejecutar SQL arbitrario.
    """
    resp = client.get(
        "/api/validaciones",
        params={"codigo_cliente": payload},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# =============================================================================
# Path traversal en SPA handler
# =============================================================================

_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

_PATHS_TRAVERSAL = [
    "../../.env",
    "../../../etc/passwd",
    "../.env",
]


@pytest.mark.parametrize("path_malicioso", _PATHS_TRAVERSAL)
def test_path_traversal_bloqueado_por_is_relative_to(path_malicioso: str):
    """
    Reproduce la guarda de serve_frontend: (dist / path).resolve().is_relative_to(dist).
    Para paths con '../', el path resuelto escapa de dist → is_relative_to devuelve
    False → el handler no sirve el archivo y cae al fallback index.html.

    Los clientes HTTP normalizan '../' en URLs antes de enviar, así que este test
    valida la lógica de path directamente en lugar de hacerlo vía HTTP.
    """
    if not _FRONTEND_DIST.exists():
        pytest.skip("frontend/dist no existe en CI — sin build del frontend")

    dist_real = _FRONTEND_DIST.resolve()
    archivo = (_FRONTEND_DIST / path_malicioso).resolve()

    # is_relative_to debe devolver False → el handler usa el fallback, no sirve el archivo
    assert not archivo.is_relative_to(dist_real)
