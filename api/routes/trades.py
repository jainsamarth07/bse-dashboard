"""
Trade routes — place orders, check status, get LTP.

Enforces paper mode by default.  Live orders require verified connection
and X-Trade-Confirm header.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from api.deps import get_current_user, get_pg
from api.schemas import (
    LtpResponse,
    OrderListItem,
    OrderStatusResponse,
    TradeRequest,
    TradeResponse,
)
from api.crypto import decrypt_value
from api.broker_adapters import get_adapter

router = APIRouter()


@router.post("", response_model=TradeResponse, status_code=201)
async def place_trade(
    body: TradeRequest,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
    x_trade_confirm: Optional[str] = Header(None),
):
    """Place a trade order. Uses paper mode unless broker key is set to live."""
    user_id = int(user["sub"])

    # Find the user's key for this broker
    row = await pg.fetchrow(
        "SELECT * FROM broker_keys WHERE user_id=$1 AND broker=$2 LIMIT 1",
        user_id,
        body.broker,
    )
    if not row:
        raise HTTPException(400, f"No {body.broker} API key configured")

    is_paper = row["mode"] == "paper"

    # Live trade requires confirmation header
    if not is_paper:
        if x_trade_confirm != "true":
            raise HTTPException(
                400,
                "Live trade requires X-Trade-Confirm: true header",
            )
        if not row["is_connected"]:
            raise HTTPException(
                400,
                f"Broker {body.broker} not verified. Test connection first or use paper mode.",
            )

    adapter = get_adapter(
        row["broker"],
        api_key=decrypt_value(row["api_key_enc"]),
        api_secret=decrypt_value(row["api_secret_enc"]),
        totp_secret=decrypt_value(row["totp_secret_enc"]) if row["totp_secret_enc"] else None,
        redirect_uri=row["redirect_uri"],
        mode=row["mode"],
    )

    # Execute via adapter — catch broker-level errors so they return 400, not 500
    try:
        result = await adapter.place_order(
            symbol=body.symbol,
            exchange=body.exchange,
            side=body.side,
            quantity=body.quantity,
            order_type=body.order_type,
            price=body.price,
            trigger_price=body.trigger_price,
        )
    except HTTPException:
        raise
    except Exception as exc:
        err = str(exc)
        if "unregistered ip" in err.lower() or "ip address" in err.lower():
            raise HTTPException(
                400,
                "Groww rejected request: IP address not whitelisted. "
                "Go to groww.in/trade-api → API Keys and add your server's public IP.",
            ) from exc
        raise HTTPException(400, f"Order placement failed: {exc}") from exc

    # Persist order to Postgres
    await pg.execute(
        """
        INSERT INTO orders
            (user_id, broker, order_id, scrip_code, symbol, exchange,
             side, quantity, order_type, price, status, simulated, created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        """,
        user_id,
        body.broker,
        result.order_id,
        body.scrip_code,
        body.symbol,
        body.exchange,
        body.side,
        body.quantity,
        body.order_type,
        body.price or 0.0,
        result.status,
        result.simulated,
        datetime.now(timezone.utc),
    )

    return result


@router.get("", response_model=list[OrderListItem])
async def list_orders(
    user=Depends(get_current_user),
    pg=Depends(get_pg),
    limit: int = 50,
    status: Optional[str] = None,
    broker: Optional[str] = None,
    simulated: Optional[bool] = None,
):
    """List recent orders for the authenticated user. Filterable by status, broker, simulated."""
    query = """SELECT id, order_id, broker, scrip_code, symbol, exchange,
                      side, quantity, order_type, price, status,
                      filled_qty, avg_price, simulated, broker_order_id, created_at
               FROM orders WHERE user_id=$1"""
    params: list = [int(user["sub"])]
    idx = 2

    if status:
        query += f" AND status=${idx}"
        params.append(status)
        idx += 1
    if broker:
        query += f" AND broker=${idx}"
        params.append(broker)
        idx += 1
    if simulated is not None:
        query += f" AND simulated=${idx}"
        params.append(simulated)
        idx += 1

    query += f" ORDER BY created_at DESC LIMIT ${idx}"
    params.append(limit)

    rows = await pg.fetch(query, *params)
    return [
        OrderListItem(
            id=r["id"],
            order_id=r["order_id"],
            broker=r["broker"],
            scrip_code=r.get("scrip_code", ""),
            symbol=r.get("symbol", ""),
            exchange=r.get("exchange", "BSE"),
            side=r.get("side", ""),
            quantity=r.get("quantity", 0),
            order_type=r.get("order_type", ""),
            price=r.get("price"),
            status=r["status"],
            filled_qty=r.get("filled_qty", 0),
            avg_price=r.get("avg_price", 0.0),
            simulated=r.get("simulated", False),
            broker_order_id=r.get("broker_order_id"),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]


@router.get("/ltp/{scrip_code}", response_model=LtpResponse)
async def get_ltp(
    scrip_code: str,
    broker_id: Optional[int] = None,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Get last traded price from connected broker or BSE quote as fallback."""
    ltp = None
    exchange = "BSE"

    # Try broker LTP first
    if broker_id:
        row = await pg.fetchrow(
            "SELECT * FROM broker_keys WHERE id=$1 AND user_id=$2",
            broker_id,
            int(user["sub"]),
        )
        if row:
            adapter = get_adapter(
                row["broker"],
                api_key=decrypt_value(row["api_key_enc"]),
                api_secret=decrypt_value(row["api_secret_enc"]),
                mode=row["mode"],
            )
            ltp = await adapter.get_ltp(scrip_code, "BSE")

    # Fallback: use BSE quote
    if ltp is None:
        try:
            from app.bse import BSE
            with BSE("./") as bse:
                q = bse.quote(scrip_code)
                if q and isinstance(q, dict):
                    ltp = float(q.get("CurrRate", {}).get("LTP", 0))
        except Exception:
            pass

    return LtpResponse(
        scrip_code=scrip_code,
        ltp=ltp,
        exchange=exchange,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/{order_id}", response_model=OrderStatusResponse)
async def get_order_status(
    order_id: str,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Check status of a previously placed order."""
    row = await pg.fetchrow(
        "SELECT * FROM orders WHERE order_id=$1 AND user_id=$2",
        order_id,
        int(user["sub"]),
    )
    if not row:
        raise HTTPException(404, "Order not found")

    # If not simulated and still pending, poll the broker for live status
    if not row["simulated"] and row["status"] in ("PLACED", "PENDING"):
        broker_row = await pg.fetchrow(
            "SELECT * FROM broker_keys WHERE user_id=$1 AND broker=$2 LIMIT 1",
            int(user["sub"]),
            row["broker"],
        )
        if broker_row:
            adapter = get_adapter(
                broker_row["broker"],
                api_key=decrypt_value(broker_row["api_key_enc"]),
                api_secret=decrypt_value(broker_row["api_secret_enc"]),
                mode=broker_row["mode"],
            )
            live_status = await adapter.order_status(order_id)
            # Update local record
            await pg.execute(
                "UPDATE orders SET status=$1, filled_qty=$2, avg_price=$3 WHERE order_id=$4",
                live_status.status,
                live_status.filled_qty,
                live_status.avg_price,
                order_id,
            )
            return live_status

    return OrderStatusResponse(
        order_id=row["order_id"],
        broker=row["broker"],
        status=row["status"],
        filled_qty=row.get("filled_qty", 0),
        avg_price=row.get("avg_price", 0.0),
    )
