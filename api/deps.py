"""
Shared dependencies: database handles, auth helpers, config.

Initialised at startup via lifespan hooks in main.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ── Postgres (async) ──────────────────────────────────────────────────────────
# Using asyncpg via databases library for non-blocking queries.
# For MVP you can also use SQLAlchemy async — swap as needed.

import asyncpg

_pg_pool: asyncpg.Pool | None = None

POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bse_user:bse_pass@localhost:5432/bse_web",
)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


async def init_postgres():
    global _pg_pool
    _pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)


async def close_postgres():
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()


async def get_pg() -> AsyncGenerator[asyncpg.Pool, None]:
    """FastAPI dependency — yields the Postgres connection pool."""
    if _pg_pool is None:
        raise HTTPException(500, "Database not initialised")
    yield _pg_pool


# ── app.db (sync psycopg2 pool, shared with the monitor/jobs scripts) ───────

from app.db import ping as pg_ping_sync  # noqa: E402


def init_pg_sync():
    """Verify the sync Postgres pool is reachable (called once at startup)."""
    if not pg_ping_sync():
        print("⚠️  Postgres (sync pool) not reachable at startup — will retry on demand")


# ── JWT Auth ──────────────────────────────────────────────────────────────────

_bearer = HTTPBearer()


def create_jwt(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """FastAPI dependency — returns decoded JWT payload (user_id, email)."""
    return decode_jwt(creds.credentials)


async def get_admin_user(
    user: dict = Depends(get_current_user),
    pg: asyncpg.Pool = Depends(get_pg),
) -> dict:
    """FastAPI dependency — ensures the current user has 'admin' role."""
    async with pg.acquire() as conn:
        role = await conn.fetchval(
            "SELECT role FROM users WHERE id = $1",
            int(user["sub"]),
        )
    if role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
