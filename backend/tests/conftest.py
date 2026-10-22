"""
Infraestructura de tests para el backend.

ORDEN DE OPERACIONES — MUY IMPORTANTE:
  config.py llama a _cargar_config() al ser importado (module-level).
  _cargar_config() lee DATABASE_URL del entorno en ese momento.
  Por eso este archivo setea DATABASE_URL ANTES de importar cualquier
  módulo del backend — Python ejecuta el cuerpo del módulo (conftest.py)
  antes de importar los archivos de test.

BASE DE DATOS DE TEST:
  Se usa 'validador_test' en lugar de 'validador'.
  La DB se crea automáticamente si no existe (fixture setup_test_db).
  Las migraciones se aplican con alembic upgrade head.
  Cada test limpia sus propios datos — no hay estado compartido entre tests.
"""
import os
import sys

# ── Paso 1: sobreescribir variables de entorno ANTES de cualquier import del backend ──
# python-dotenv usa override=False por defecto, así que los valores que seteamos
# acá tienen precedencia sobre el .env — la DB de dev nunca se toca en tests.
_TEST_DB_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql://validador:validador_dev@localhost:5433/validador_test",
)
os.environ["DATABASE_URL"] = _TEST_DB_URL

# El rate limiter usa la misma IP ficticia ("testclient") para todos los requests
# del TestClient. Un límite real de 5/minute haría fallar los tests de login
# existentes al 6to request. Seteamos un límite alto solo en tests.
os.environ.setdefault("RATE_LIMIT_LOGIN", "10000/minute")

# Sentry desactivado en tests — evita enviar errores falsos al proyecto real
# y desacopla los tests de la red.
os.environ["SENTRY_DSN"] = ""

# Redis desactivado en tests — no hay servidor Redis en CI ni en dev local básico.
# R2 y siguientes usan fakeredis cuando necesiten probar lógica con Redis.
os.environ["REDIS_URL"] = ""

# ── Paso 2: agregar backend/ al sys.path ──────────────────────────────────────
# Necesario para que los imports como `from config import config` funcionen
# cuando pytest corre desde backend/ o desde la raíz del proyecto.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── Paso 3: ahora sí importar módulos del backend ────────────────────────────
import psycopg2
import psycopg2.pool
import pytest
import fakeredis.aioredis
from fastapi.testclient import TestClient

from config import config           # config.database_url_sync → validador_test ✅
from main import app                # carga la app FastAPI completa
import db.connection as db_conn
import db.redis as db_redis
from db.redis import get_cliente_redis
from db import queries_admins
from services.auth_service import crear_access_token, hash_password

# Redis en memoria para tests: cubre tanto Depends(get_cliente_redis) en routers
# como las llamadas directas desde workers/analisis.py.
_fake_redis = fakeredis.aioredis.FakeRedis()
db_redis._cliente_redis = _fake_redis
app.dependency_overrides[get_cliente_redis] = lambda: _fake_redis

# ── Constantes de test ────────────────────────────────────────────────────────
_TEST_ADMIN_EMAIL    = "test_admin@validador-tests.com"  # .test es TLD reservado (RFC 2606), rechazado por email-validator
_TEST_ADMIN_PASSWORD = "TestPass_123!"
_TEST_DB_NAME        = "validador_test"

# DSN sin prefijo de SQLAlchemy (para psycopg2.connect directo)
_TEST_DSN  = config.database_url_sync.replace("postgresql+psycopg2://", "postgresql://")
# DSN apuntando a la DB principal (para poder crear la test DB)
_ADMIN_DSN = _TEST_DSN.rsplit("/", 1)[0] + "/validador"


# =============================================================================
# Fixtures de sesión — corren UNA vez por `pytest` run
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Crea 'validador_test' si no existe y aplica todas las migraciones.
    autouse=True: corre automáticamente antes de cualquier test, sin que
    los tests tengan que pedirlo explícitamente.
    """
    # 1. Crear la DB si no existe
    #    CREATE DATABASE no puede correr dentro de una transacción —
    #    necesitamos autocommit=True.
    conn = psycopg2.connect(_ADMIN_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (_TEST_DB_NAME,))
    if not cur.fetchone():
        cur.execute(f"CREATE DATABASE {_TEST_DB_NAME} OWNER validador")
        print(f"\n[test] DB '{_TEST_DB_NAME}' creada")
    cur.close()
    conn.close()

    # 2. Aplicar migraciones con alembic Python API
    #    Usamos la API directamente para evitar subprocesos y poder pasar
    #    la URL de test sin modificar alembic.ini.
    root_dir = os.path.dirname(_BACKEND_DIR)
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_cmd

    alembic_cfg = AlembicConfig(os.path.join(root_dir, "alembic.ini"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        _TEST_DSN.replace("postgresql://", "postgresql+psycopg2://"),
    )
    alembic_cmd.upgrade(alembic_cfg, "head")
    print(f"[test] Migraciones aplicadas en '{_TEST_DB_NAME}'")


@pytest.fixture(scope="session")
def client(setup_test_db):
    """
    TestClient de FastAPI que usa la DB de test.

    TestClient inicia el lifespan de la app (startup/shutdown).
    En startup, crear_pool() usa config.database_url_sync que ya apunta
    a validador_test (porque seteamos DATABASE_URL antes de importar config).
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _limpiar_cookies(client):
    """
    Limpia el jar de cookies del TestClient antes de cada test.

    TestClient se comporta como un browser: cuando el servidor responde con
    Set-Cookie (ej: POST /auth/login), el cliente guarda la cookie y la
    envía en todos los requests siguientes. Sin este fixture, los tests
    que verifican "sin token → 401" fallarían si corren después de un
    test de login, porque el cookie de sesión quedaría en el jar.
    """
    client.cookies.clear()
    yield


@pytest.fixture(scope="session")
def admin_test(client):
    """
    Crea el admin de test en la DB y lo elimina al final de la sesión.
    Depende de 'client' para asegurar que el pool ya existe.

    Devuelve el dict con los datos del admin (id, email, nombre).
    """
    pool = db_conn.get_pool()

    # Limpiar si quedó de una sesión anterior
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE email = %s", (_TEST_ADMIN_EMAIL,))
        conn.commit()
    finally:
        pool.putconn(conn)

    admin_id = queries_admins.crear_admin(
        pool,
        config.tenant_id,
        _TEST_ADMIN_EMAIL,
        "Admin Test",
        hash_password(_TEST_ADMIN_PASSWORD),
    )
    print(f"\n[test] Admin de test creado: {admin_id}")

    yield {"id": admin_id, "email": _TEST_ADMIN_EMAIL, "nombre": "Admin Test"}

    # Teardown: borrar auditoria del admin y luego el admin
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auditoria WHERE admin_id = %s::uuid", (admin_id,))
            cur.execute("DELETE FROM admins WHERE email = %s", (_TEST_ADMIN_EMAIL,))
        conn.commit()
    finally:
        pool.putconn(conn)


@pytest.fixture(scope="session")
def admin_token(admin_test):
    """JWT válido del admin de test. Se genera una vez y se reutiliza en todos los tests."""
    return crear_access_token(
        admin_id=admin_test["id"],
        email=admin_test["email"],
        nombre=admin_test["nombre"],
    )


@pytest.fixture(scope="session")
def api_key_header():
    """Header X-API-Key con la clave configurada en .env. Reutilizable en todos los tests."""
    return {"X-API-Key": config.api_key}


# =============================================================================
# Fixtures de función — corren por cada test
# =============================================================================

_TEST_SUPERADMIN_EMAIL    = "test_superadmin@validador-tests.com"
_TEST_ADMIN_TOGGLE_EMAIL  = "test_toggle@validador-tests.com"


@pytest.fixture(scope="session")
def superadmin_test(client):
    """
    Admin con es_superadmin=True para tests de /api/admins.
    Scope sesión: se crea una vez y se elimina al terminar todos los tests.
    """
    pool = db_conn.get_pool()

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE email = %s", (_TEST_SUPERADMIN_EMAIL,))
        conn.commit()
    finally:
        pool.putconn(conn)

    admin_id = queries_admins.crear_admin(
        pool,
        config.tenant_id,
        _TEST_SUPERADMIN_EMAIL,
        "Superadmin Test",
        hash_password(_TEST_ADMIN_PASSWORD),
        es_superadmin=True,
    )

    yield {"id": admin_id, "email": _TEST_SUPERADMIN_EMAIL, "nombre": "Superadmin Test"}

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auditoria WHERE admin_id = %s::uuid", (admin_id,))
            cur.execute("DELETE FROM admins WHERE email = %s", (_TEST_SUPERADMIN_EMAIL,))
        conn.commit()
    finally:
        pool.putconn(conn)


@pytest.fixture(scope="session")
def superadmin_token(superadmin_test):
    """JWT con es_superadmin=True. Se reutiliza en todos los tests de la sesión."""
    return crear_access_token(
        admin_id=superadmin_test["id"],
        email=superadmin_test["email"],
        nombre=superadmin_test["nombre"],
        es_superadmin=True,
    )


@pytest.fixture
def admin_para_toggle(client):
    """
    Admin desechable para tests de PATCH /api/admins/{id}/activo.
    Scope función: cada test recibe un admin fresco en estado activo=True.

    Por qué function scope y no session:
      Los tests de toggle cambian el estado activo del admin. Empezar siempre
      desde activo=True evita que tests se interfieran entre sí.
    """
    pool = db_conn.get_pool()

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE email = %s", (_TEST_ADMIN_TOGGLE_EMAIL,))
        conn.commit()
    finally:
        pool.putconn(conn)

    admin_id = queries_admins.crear_admin(
        pool,
        config.tenant_id,
        _TEST_ADMIN_TOGGLE_EMAIL,
        "Admin Toggle Test",
        hash_password(_TEST_ADMIN_PASSWORD),
    )

    yield {"id": admin_id, "email": _TEST_ADMIN_TOGGLE_EMAIL, "nombre": "Admin Toggle Test"}

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE email = %s", (_TEST_ADMIN_TOGGLE_EMAIL,))
        conn.commit()
    finally:
        pool.putconn(conn)


@pytest.fixture
def validacion_test(client):
    """
    Inserta una validación de test (IMAGEN_INVALIDA, canal MANUAL) y la elimina
    después de cada test que la use.

    Por qué function scope y no session:
      Cada test que edita la validación la deja en un estado diferente.
      Empezar con una fila fresca evita que tests se interfieran entre sí.
    """
    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO validaciones (tenant_id, estado, canal)
                VALUES (%s, 'IMAGEN_INVALIDA', 'MANUAL')
                RETURNING id::text
                """,
                (config.tenant_id,),
            )
            validacion_id = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)

    yield validacion_id

    # Teardown: primero la auditoría (FK), luego la validación
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM auditoria WHERE validacion_id = %s::uuid",
                (validacion_id,),
            )
            cur.execute(
                "DELETE FROM validaciones WHERE id = %s::uuid",
                (validacion_id,),
            )
        conn.commit()
    finally:
        pool.putconn(conn)


_TEST_CLIENTE_CODIGO = "TESTCLI001"


@pytest.fixture
def cliente_test(client):
    """
    Crea un cliente de test y lo elimina al finalizar.
    Function scope: cada test recibe un cliente en estado limpio.
    Teardown en orden FK: telefonos → cuits → cliente.
    """
    pool = db_conn.get_pool()

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM clientes WHERE codigo_cliente = %s",
                (_TEST_CLIENTE_CODIGO,),
            )
        conn.commit()
    finally:
        pool.putconn(conn)

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clientes (codigo_cliente, razon_social, direccion)
                VALUES (%s, 'Cliente Test SA', 'Corrientes 1234, CABA')
                RETURNING id::text
                """,
                (_TEST_CLIENTE_CODIGO,),
            )
            cliente_id = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)

    yield {"id": cliente_id, "codigo_cliente": _TEST_CLIENTE_CODIGO, "razon_social": "Cliente Test SA"}

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM clientes_telefonos WHERE cliente_id = %s::uuid", (cliente_id,))
            cur.execute("DELETE FROM clientes_cuits WHERE cliente_id = %s::uuid", (cliente_id,))
            cur.execute("DELETE FROM clientes WHERE id = %s::uuid", (cliente_id,))
        conn.commit()
    finally:
        pool.putconn(conn)


@pytest.fixture
def limpiar_clientes_importados(client):
    """
    Post-test: elimina todos los clientes cuyo codigo_cliente empiece con 'TESTIMPORT'.
    Usarlo en tests de importación CSV para no contaminar otros tests.
    """
    yield

    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM clientes_telefonos WHERE cliente_id IN (
                    SELECT id FROM clientes WHERE codigo_cliente LIKE 'TESTIMPORT%'
                )
                """
            )
            cur.execute(
                """
                DELETE FROM clientes_cuits WHERE cliente_id IN (
                    SELECT id FROM clientes WHERE codigo_cliente LIKE 'TESTIMPORT%'
                )
                """
            )
            cur.execute("DELETE FROM clientes WHERE codigo_cliente LIKE 'TESTIMPORT%'")
        conn.commit()
    finally:
        pool.putconn(conn)
