"""
Pool de conexiones a PostgreSQL usando psycopg2 (sync).

Por qué psycopg2 en lugar de psycopg3 async:
  uvicorn en Windows + Python 3.14 usa ProactorEventLoop internamente,
  que psycopg3 rechaza. psycopg2 corre en threads (ThreadedConnectionPool)
  y se llama desde los handlers via run_in_executor — el event loop no se bloquea.

ThreadedConnectionPool:
  Mantiene entre min_conn y max_conn conexiones abiertas.
  getconn() asigna una conexión libre del pool (thread-safe).
  putconn() la devuelve al pool para que otro thread la reutilice.
"""
import psycopg2
import psycopg2.pool
from config import config

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def crear_pool() -> None:
    """Inicializa el pool de conexiones. Llamar una sola vez al arrancar."""
    global _pool
    # psycopg2 usa postgresql:// directo (sin el prefijo de SQLAlchemy)
    dsn = config.database_url_sync.replace("postgresql+psycopg2://", "postgresql://")
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        dsn=dsn,
        keepalives=1,
        keepalives_idle=60,
        keepalives_interval=10,
        keepalives_count=5,
    )
    print("[DB] Pool de conexiones creado")


def cerrar_pool() -> None:
    if _pool:
        _pool.closeall()
        print("[DB] Pool de conexiones cerrado")


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    if _pool is None:
        raise RuntimeError("Pool no inicializado. ¿Se llamó crear_pool()?")
    return _pool
