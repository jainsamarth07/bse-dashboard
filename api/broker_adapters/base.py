"""
Abstract base class for all broker adapters.

Every method is async to support non-blocking I/O in FastAPI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse


class BrokerAdapter(ABC):
    """Uniform interface that each broker must implement."""

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        totp_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.redirect_uri = redirect_uri

    # ── Authentication ────────────────────────────────────────────────────

    @abstractmethod
    async def authenticate(self) -> str:
        """Perform OAuth/TOTP login flow.  Returns access token."""
        ...

    # ── Connection test ───────────────────────────────────────────────────

    @abstractmethod
    async def test_connection(self) -> TestConnectionResponse:
        """Verify credentials + optional balance check."""
        ...

    # ── Order management ──────────────────────────────────────────────────

    @abstractmethod
    async def place_order(
        self,
        *,
        symbol: str,
        exchange: str,
        side: str,          # BUY | SELL
        quantity: int,
        order_type: str,    # LIMIT | MARKET | SL
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
    ) -> TradeResponse:
        """Place a new order.  Returns order_id + status."""
        ...

    @abstractmethod
    async def order_status(self, order_id: str) -> OrderStatusResponse:
        """Poll the broker for current order status."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Attempt to cancel an open order.  Returns True on success."""
        ...

    # ── Market data (optional — override if broker provides) ──────────────

    async def get_ltp(self, symbol: str, exchange: str = "BSE") -> Optional[float]:
        """Last traded price.  Returns None if not supported."""
        return None
