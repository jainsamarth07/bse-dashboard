"""
Auth routes — signup, login, me.

Passwords hashed with bcrypt.  JWT issued on successful login.
"""

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import create_jwt, get_current_user, get_pg
from api.schemas import LoginRequest, SignupRequest, TokenResponse

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, pg=Depends(get_pg)):
    # Check duplicate
    existing = await pg.fetchrow("SELECT id FROM users WHERE email=$1", body.email)
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    row = await pg.fetchrow(
        "INSERT INTO users (email, password_hash, name) VALUES ($1,$2,$3) RETURNING id",
        body.email,
        hashed,
        body.name,
    )
    token = create_jwt(row["id"], body.email)
    return TokenResponse(access_token=token, user_id=row["id"], email=body.email)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, pg=Depends(get_pg)):
    row = await pg.fetchrow(
        "SELECT id, email, password_hash FROM users WHERE email=$1", body.email
    )
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = create_jwt(row["id"], row["email"])
    return TokenResponse(access_token=token, user_id=row["id"], email=row["email"])


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"user_id": user["sub"], "email": user["email"]}
