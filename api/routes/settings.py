"""
User settings routes — CRUD for per-user settings stored in PG.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_pg
from api.schemas import UserSettings

router = APIRouter()


@router.get("/me/settings", response_model=UserSettings)
async def get_settings(
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Get current user's settings."""
    row = await pg.fetchrow(
        "SELECT settings FROM users WHERE id=$1", int(user["sub"])
    )
    if not row:
        raise HTTPException(404, "User not found")

    settings_raw = row["settings"]
    if not settings_raw:
        return UserSettings()

    # Parse JSON if stored as string
    if isinstance(settings_raw, str):
        try:
            settings_dict = json.loads(settings_raw)
        except json.JSONDecodeError:
            return UserSettings()
    else:
        settings_dict = settings_raw

    return UserSettings(**settings_dict)


@router.patch("/me/settings", response_model=UserSettings)
async def update_settings(
    body: UserSettings,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Update current user's settings (full replace)."""
    settings_json = json.dumps(body.model_dump())

    await pg.execute(
        "UPDATE users SET settings=$1::jsonb, updated_at=NOW() WHERE id=$2",
        settings_json,
        int(user["sub"]),
    )

    return body
