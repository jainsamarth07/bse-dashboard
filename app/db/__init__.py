"""
PostgreSQL connection manager (sync).

Used by app.core.monitor and jobs/* — plain scripts that run outside
FastAPI's event loop, so a blocking psycopg2 pool is used here rather than
asyncpg (which api/deps.py uses for the FastAPI request path against the
same database).

    from app.db import ping, get_conn, close
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bse_user:bse_pass@localhost:5432/bse_web",
)

# Decode NUMERIC columns as float instead of Decimal — the rest of the
# codebase (market_cap arithmetic, f-string formatting, JSON responses)
# assumes plain floats throughout, matching what pymongo/BSON returned.
_NUMERIC_OID = 1700
psycopg2.extensions.register_type(
    psycopg2.extensions.new_type(
        (_NUMERIC_OID,), "NUMERIC_FLOAT", lambda v, c: float(v) if v is not None else None
    )
)

# Singleton – created once per process
_pool: ThreadedConnectionPool | None = None


def get_pool() -> ThreadedConnectionPool:
    """Return (or lazily create) the shared connection pool."""
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(1, 10, dsn=DATABASE_URL, connect_timeout=5)
    return _pool


@contextmanager
def get_conn():
    """Context manager yielding a pooled connection; commits on success."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        conn.cursor().execute("SET TIME ZONE 'UTC'")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor: bool = True):
    """Context manager yielding a cursor (RealDictCursor by default)."""
    cursor_factory = psycopg2.extras.RealDictCursor if dict_cursor else None
    with get_conn() as conn:
        with conn.cursor(cursor_factory=cursor_factory) as cur:
            yield cur


def ping() -> bool:
    """Return True when Postgres is reachable, False otherwise."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def close() -> None:
    """Close the connection pool and reset the singleton."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
