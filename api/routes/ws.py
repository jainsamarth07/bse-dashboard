"""
WebSocket endpoint for real-time updates.

Uses the Postgres `notifications` table as the event source, polled every
2 seconds. Monitor inserts events after each financial_results insert; the
WS endpoint tails new rows.

Redis upgrade path: swap the poll loop for a Redis pub/sub subscriber
(aioredis). The message format stays the same.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.deps import decode_jwt
from app.db.models import NotificationStore

router = APIRouter()


async def _authenticate_ws(ws: WebSocket, token: str | None) -> dict | None:
    """Validate JWT from query param. Returns decoded payload or None."""
    if not token:
        return None
    try:
        return decode_jwt(token)
    except Exception:
        return None


@router.websocket("/ws/updates")
async def updates_ws(ws: WebSocket, token: str | None = Query(None)):
    """
    WebSocket endpoint for real-time financial result updates.

    Connect with: ws://host/ws/updates?token=<JWT>

    Messages sent to client:
    {
      "event": "new_result" | "updated_result" | "deleted_result",
      "data": { ... FinancialResultResponse ... },
      "timestamp": "2026-04-12T18:00:00Z"
    }
    """
    user = await _authenticate_ws(ws, token)
    if not user:
        await ws.close(code=4001, reason="Authentication required")
        return

    await ws.accept()

    try:
        await _polling_fallback(ws)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.close(code=1011, reason=str(e)[:120])
        except Exception:
            pass


async def _polling_fallback(ws: WebSocket):
    """Poll the notifications table every 2 seconds."""
    last_check = datetime.now(timezone.utc)

    while True:
        try:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

            recent = await asyncio.get_event_loop().run_in_executor(
                None, NotificationStore.get_recent, 1
            )
            for doc in recent:
                created = doc.get("created_at")
                if created and created > last_check:
                    msg = {
                        "event": doc.get("event", "new_result"),
                        "data": _serialize_data(doc.get("data", {})),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await ws.send_json(msg)

            last_check = datetime.now(timezone.utc)
            await asyncio.sleep(2)

        except WebSocketDisconnect:
            return
        except Exception:
            await asyncio.sleep(5)


def _serialize_data(data: dict) -> dict:
    """Ensure all values are JSON-serializable."""
    result = {}
    for k, v in data.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, dict):
            result[k] = _serialize_data(v)
        else:
            result[k] = v
    return result
