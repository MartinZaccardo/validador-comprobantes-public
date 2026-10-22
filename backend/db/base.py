import asyncio
import functools
from contextlib import contextmanager

import psycopg2
import psycopg2.pool


async def q(func, *args, **kwargs):
    """
    Ejecuta una función síncrona (psycopg2) en el thread pool y la hace awaitable.

    Uso: resultado = await q(crear_run, pool, tenant_id)

    Por qué functools.partial y no lambda:
      run_in_executor solo acepta callables sin argumentos adicionales.
      functools.partial "congela" los argumentos en el callable — más
      eficiente que lambda y maneja correctamente keyword arguments.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


@contextmanager
def conexion_lectura(pool: psycopg2.pool.ThreadedConnectionPool):
    """Entrega una conexión del pool y la devuelve al terminar (sin commit)."""
    conn = pool.getconn()
    muerta = False
    try:
        yield conn
    except psycopg2.OperationalError:
        muerta = True
        raise
    finally:
        pool.putconn(conn, close=muerta)


@contextmanager
def conexion_escritura(pool: psycopg2.pool.ThreadedConnectionPool):
    """Entrega una conexión, hace commit si el bloque termina sin excepción, rollback si no."""
    conn = pool.getconn()
    muerta = False
    try:
        yield conn
        conn.commit()
    except psycopg2.OperationalError:
        muerta = True
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=muerta)
