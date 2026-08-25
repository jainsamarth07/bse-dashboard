"""
Broker key management routes.

Users can add/remove/test their broker API keys.
Keys are AES-256-GCM encrypted before storage in Postgres.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user, get_pg
from api.schemas import (
    BrokerKeyCreate,
    BrokerKeyResponse,
    ModeToggleRequest,
    TestConnectionResponse,
)
from api.crypto import encrypt_value, decrypt_value
from api.broker_adapters import get_adapter

router = APIRouter()

SUPPORTED_BROKERS = {"upstox", "angel_one", "kite", "dhan", "groww"}


def _mask(val: str) -> str:
    """Show first 4 and last 3 characters only."""
    if len(val) <= 8:
        return "****"
    return val[:4] + "****" + val[-3:]


@router.get("", response_model=list[BrokerKeyResponse])
async def list_broker_keys(user=Depends(get_current_user), pg=Depends(get_pg)):
    rows = await pg.fetch(
        "SELECT id, broker, api_key_enc, mode, is_connected, created_at "
        "FROM broker_keys WHERE user_id=$1 ORDER BY created_at DESC",
        int(user["sub"]),
    )
    results = []
    for r in rows:
        api_key = decrypt_value(r["api_key_enc"])
        results.append(
            BrokerKeyResponse(
                id=r["id"],
                broker=r["broker"],
                api_key_masked=_mask(api_key),
                mode=r["mode"],
                is_connected=r["is_connected"],
                created_at=r["created_at"],
            )
        )
    return results


@router.post("", response_model=BrokerKeyResponse, status_code=201)
async def add_broker_key(
    body: BrokerKeyCreate,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    if body.broker not in SUPPORTED_BROKERS:
        raise HTTPException(400, f"Unsupported broker: {body.broker}")

    key_enc = encrypt_value(body.api_key)
    secret_enc = encrypt_value(body.api_secret)
    totp_enc = encrypt_value(body.totp_secret) if body.totp_secret else None

    row = await pg.fetchrow(
        """
        INSERT INTO broker_keys
            (user_id, broker, api_key_enc, api_secret_enc, totp_secret_enc,
             redirect_uri, mode, is_connected, created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7, false, $8)
        ON CONFLICT (user_id, broker)
        DO UPDATE SET
            api_key_enc = EXCLUDED.api_key_enc,
            api_secret_enc = EXCLUDED.api_secret_enc,
            totp_secret_enc = EXCLUDED.totp_secret_enc,
            redirect_uri = EXCLUDED.redirect_uri,
            mode = EXCLUDED.mode,
            is_connected = false,
            created_at = EXCLUDED.created_at
        RETURNING id, broker, mode, is_connected, created_at
        """,
        int(user["sub"]),
        body.broker,
        key_enc,
        secret_enc,
        totp_enc,
        body.redirect_uri,
        body.mode,
        datetime.now(timezone.utc),
    )
    return BrokerKeyResponse(
        id=row["id"],
        broker=row["broker"],
        api_key_masked=_mask(body.api_key),
        mode=row["mode"],
        is_connected=row["is_connected"],
        created_at=row["created_at"],
    )


@router.delete("/{key_id}", status_code=204)
async def delete_broker_key(
    key_id: int,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    result = await pg.execute(
        "DELETE FROM broker_keys WHERE id=$1 AND user_id=$2",
        key_id,
        int(user["sub"]),
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Key not found")


@router.post("/{key_id}/test", response_model=TestConnectionResponse)
async def test_connection(
    key_id: int,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Test broker connection and optionally fetch balance."""
    row = await pg.fetchrow(
        "SELECT * FROM broker_keys WHERE id=$1 AND user_id=$2",
        key_id,
        int(user["sub"]),
    )
    if not row:
        raise HTTPException(404, "Key not found")

    adapter = get_adapter(
        row["broker"],
        api_key=decrypt_value(row["api_key_enc"]),
        api_secret=decrypt_value(row["api_secret_enc"]),
        totp_secret=decrypt_value(row["totp_secret_enc"]) if row["totp_secret_enc"] else None,
        redirect_uri=row["redirect_uri"],
        mode=row["mode"],
    )

    result = await adapter.test_connection()

    # Update connection status in DB
    await pg.execute(
        "UPDATE broker_keys SET is_connected=$1 WHERE id=$2",
        result.connected,
        key_id,
    )

    return result


@router.patch("/{key_id}/mode")
async def toggle_mode(
    key_id: int,
    body: ModeToggleRequest,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    if body.mode not in ("paper", "live"):
        raise HTTPException(400, "mode must be 'paper' or 'live'")

    # Switching to live requires password confirmation
    if body.mode == "live":
        if not body.confirm or not body.password:
            raise HTTPException(
                400, "Switching to live mode requires confirm=true and password"
            )
        # Re-verify password
        row = await pg.fetchrow(
            "SELECT password_hash FROM users WHERE id=$1", int(user["sub"])
        )
        if not row:
            raise HTTPException(404, "User not found")

        import bcrypt
        if not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
            raise HTTPException(401, "Invalid password")

    result = await pg.execute(
        "UPDATE broker_keys SET mode=$1 WHERE id=$2 AND user_id=$3",
        body.mode,
        key_id,
        int(user["sub"]),
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Key not found")

    # Return the updated broker key
    updated_row = await pg.fetchrow(
        "SELECT id, broker, api_key_enc, mode, is_connected, created_at "
        "FROM broker_keys WHERE id=$1",
        key_id,
    )
    if not updated_row:
        raise HTTPException(404, "Key not found")

    api_key = decrypt_value(updated_row["api_key_enc"])
    return BrokerKeyResponse(
        id=updated_row["id"],
        broker=updated_row["broker"],
        api_key_masked=_mask(api_key),
        mode=updated_row["mode"],
        is_connected=updated_row["is_connected"],
        created_at=updated_row["created_at"],
    )
