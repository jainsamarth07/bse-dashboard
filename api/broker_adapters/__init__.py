"""
Broker adapter system — abstract interface + concrete adapters.

Each broker adapter normalises the broker-specific API into a uniform
interface so the trade routes are broker-agnostic.

Adding a new broker:
  1. Create a new file (e.g. broker_adapters/fyers.py)
  2. Subclass BrokerAdapter, implement all abstract methods
  3. Register in ADAPTER_REGISTRY below
"""

from __future__ import annotations

from typing import Optional

from api.broker_adapters.base import BrokerAdapter
from api.broker_adapters.upstox import UpstoxAdapter
from api.broker_adapters.angel_one import AngelOneAdapter
from api.broker_adapters.groww import GrowwAdapter
from api.broker_adapters.dhan import DhanAdapter
from api.broker_adapters.paper import PaperAdapter
from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse

ADAPTER_REGISTRY: dict[str, type[BrokerAdapter]] = {
    "upstox": UpstoxAdapter,
    "angel_one": AngelOneAdapter,
    "groww": GrowwAdapter,
    "dhan": DhanAdapter,
}


class _StubAdapter(BrokerAdapter):
    """Placeholder for brokers that are allowed but not yet fully integrated.
    Works in paper mode — test_connection returns a helpful message."""

    def __init__(self, broker_name: str, **kwargs):
        super().__init__(**kwargs)
        self._name = broker_name

    async def authenticate(self) -> str:
        return ""

    async def test_connection(self) -> TestConnectionResponse:
        return TestConnectionResponse(
            broker=self._name,
            connected=False,
            message=f"{self._name.title()} live integration coming soon. Paper trading works.",
        )

    async def place_order(self, **kwargs) -> TradeResponse:
        raise NotImplementedError(f"Live trading not yet supported for {self._name}")

    async def order_status(self, order_id: str) -> OrderStatusResponse:
        raise NotImplementedError(f"Live trading not yet supported for {self._name}")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError(f"Live trading not yet supported for {self._name}")


def get_adapter(
    broker: str,
    *,
    api_key: str = "",
    api_secret: str = "",
    totp_secret: str | None = None,
    redirect_uri: str | None = None,
    mode: str = "paper",
) -> BrokerAdapter:
    """Factory: return a ready-to-use adapter.

    If mode == "paper", wraps the real adapter with PaperAdapter
    so no actual orders hit the exchange.

    For brokers in SUPPORTED_BROKERS but not yet fully integrated (kite, dhan),
    returns a stub wrapped in PaperAdapter — paper trading still works.
    """
    cls = ADAPTER_REGISTRY.get(broker)

    if cls:
        real_adapter = cls(
            api_key=api_key,
            api_secret=api_secret,
            totp_secret=totp_secret,
            redirect_uri=redirect_uri,
        )
    else:
        # Known-but-stub broker (e.g. kite) — paper mode only
        real_adapter = _StubAdapter(
            broker,
            api_key=api_key,
            api_secret=api_secret,
        )

    if mode == "paper":
        return PaperAdapter(real_adapter)

    if not cls:
        raise ValueError(
            f"Live trading not supported for '{broker}' yet. Use paper mode."
        )

    return real_adapter
