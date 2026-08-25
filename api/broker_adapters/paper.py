"""
Paper trading adapter — wraps any real adapter and simulates orders.

No actual market orders are placed.  Order IDs are locally generated UUIDs.
Useful for:
  - Testing the full flow without risking real money
  - Demo / dev environments
  - Users who haven't verified their broker connection yet
"""

from __future__ import annotations

import uuid
from typing import Optional

from api.broker_adapters.base import BrokerAdapter
from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse


class PaperAdapter(BrokerAdapter):
    """Decorator that intercepts order calls and simulates them."""

    def __init__(self, real_adapter: BrokerAdapter):
        # Don't call super().__init__ — we delegate to the wrapped adapter
        self._real = real_adapter
        self._simulated_orders: dict[str, dict] = {}

    # ── Delegate auth + test to real adapter ──────────────────────────────

    async def authenticate(self) -> str:
        return await self._real.authenticate()

    async def test_connection(self) -> TestConnectionResponse:
        result = await self._real.test_connection()
        result.message = f"[PAPER MODE] {result.message}"
        return result

    # ── Simulated orders ──────────────────────────────────────────────────

    async def place_order(
        self,
        *,
        symbol: str,
        exchange: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
    ) -> TradeResponse:
        order_id = f"PAPER-{uuid.uuid4().hex[:12].upper()}"

        self._simulated_orders[order_id] = {
            "symbol": symbol,
            "exchange": exchange,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": price,
            "status": "SIMULATED",
        }

        return TradeResponse(
            order_id=order_id,
            broker=f"paper_{self._real.__class__.__name__}",
            status="SIMULATED",
            message=f"Paper order: {side} {quantity}x {symbol} @ {price or 'MARKET'}",
            simulated=True,
        )

    async def order_status(self, order_id: str) -> OrderStatusResponse:
        sim = self._simulated_orders.get(order_id)
        if sim:
            return OrderStatusResponse(
                order_id=order_id,
                broker="paper",
                status="SIMULATED",
                filled_qty=sim["quantity"],
                avg_price=sim.get("price") or 0.0,
                message="Paper trade — no real execution",
            )
        return OrderStatusResponse(
            order_id=order_id,
            broker="paper",
            status="NOT_FOUND",
            message="Simulated order not found",
        )

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._simulated_orders:
            self._simulated_orders[order_id]["status"] = "CANCELLED"
            return True
        return False

    async def get_ltp(self, symbol: str, exchange: str = "BSE") -> Optional[float]:
        # Delegate LTP to real adapter (market data is read-only)
        return await self._real.get_ltp(symbol, exchange)
