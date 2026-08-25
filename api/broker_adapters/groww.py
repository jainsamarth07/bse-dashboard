"""
Groww broker adapter.

Uses the official growwapi Python package (pip install growwapi).

Official authentication flow (from Groww-OSS sample):
  1. access_token = GrowwAPI.get_access_token(api_key="...", secret="...")
  2. groww = GrowwAPI(access_token)
  3. groww.place_order(trading_symbol=..., quantity=..., validity=...,
                       exchange=..., segment=..., product=...,
                       order_type=..., transaction_type=...)
  → response contains {"groww_order_id": "..."}

The growwapi package is synchronous; all calls are wrapped in
asyncio.get_event_loop().run_in_executor() so the adapter remains async-safe.

Official docs : https://groww.in/trade-api
Official repo : https://github.com/Groww-OSS/growwapi
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from api.broker_adapters.base import BrokerAdapter
from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse

BASE_URL = "https://api.groww.in/v1"


class GrowwAdapter(BrokerAdapter):
    """Concrete adapter for the Groww Broker API."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._access_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────

    async def authenticate(self) -> str:
        """Get an access token using the official growwapi package.

        Equivalent to the official sample:
            access_token = GrowwAPI.get_access_token(api_key=..., secret=...)
        """
        from growwapi import GrowwAPI

        api_key = self.api_key
        secret = self.api_secret

        token: str = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: GrowwAPI.get_access_token(api_key=api_key, secret=secret),
        )
        self._access_token = token
        return token

    def _headers(self, token: str | None = None) -> dict:
        bearer = token or self._access_token or self.api_key
        return {
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── Connection test ───────────────────────────────────────────────────

    async def test_connection(self) -> TestConnectionResponse:
        """Verify credentials by obtaining an access token then fetching profile.

        Uses GrowwAPI.get_access_token(api_key, secret) — the same call as the
        official Groww sample.  If that succeeds, credentials are valid.
        """
        try:
            token = await self.authenticate()

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/user/profile",
                    headers=self._headers(token),
                    timeout=10,
                )

                if resp.status_code == 200:
                    profile = resp.json()
                    name = (
                        profile.get("name")
                        or profile.get("username")
                        or profile.get("clientName")
                        or "N/A"
                    )

                    balance: Optional[float] = None
                    margin_resp = await client.get(
                        f"{BASE_URL}/user/margins",
                        headers=self._headers(token),
                        timeout=10,
                    )
                    if margin_resp.status_code == 200:
                        data = margin_resp.json()
                        try:
                            balance = float(
                                data.get("availableCash")
                                or data.get("available_cash")
                                or 0
                            )
                        except (ValueError, TypeError):
                            pass

                    return TestConnectionResponse(
                        broker="groww",
                        connected=True,
                        message=f"Connected as {name}",
                        balance=balance,
                    )

                return TestConnectionResponse(
                    broker="groww",
                    connected=False,
                    message=f"Profile fetch failed (HTTP {resp.status_code}). "
                            "Please check your API credentials.",
                )

        except httpx.TimeoutException:
            return TestConnectionResponse(
                broker="groww",
                connected=False,
                message="Connection timed out. Check your internet connection.",
            )
        except Exception as exc:
            err = str(exc)
            err_lower = err.lower()
            if "unregistered ip" in err_lower or "ip address" in err_lower or "ip not" in err_lower:
                msg = (
                    "IP address not whitelisted. Log in to groww.in/trade-api → "
                    "API Keys → add your server's public IP to the allowed list, then retry."
                )
            elif "401" in err or "unauthorized" in err_lower or "invalid" in err_lower:
                msg = (
                    "Invalid API key or secret (401). "
                    "Use the key + secret from groww.in/trade-api."
                )
            elif "403" in err:
                msg = "Access forbidden (403). API trading may not be enabled on your account."
            else:
                msg = f"Authentication failed: {err}"
            return TestConnectionResponse(broker="groww", connected=False, message=msg)

    # ── Order management ──────────────────────────────────────────────────

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
        """Place a live order using the official growwapi package.

        Matches the official Groww sample:
            groww.place_order(
                trading_symbol=..., quantity=..., validity="DAY",
                exchange="NSE", segment="CASH", product="MIS",
                order_type="MARKET", transaction_type="BUY"
            )
        Returns response["groww_order_id"] as the order ID.
        """
        from growwapi import GrowwAPI

        token = await self.authenticate()
        groww_instance = GrowwAPI(token)

        order_kwargs: dict = dict(
            trading_symbol=symbol,
            quantity=quantity,
            validity="DAY",
            exchange=exchange.upper(),        # "NSE" or "BSE"
            segment="CASH",                   # equity cash segment
            product="MIS",                    # intraday; "CNC" for delivery
            order_type=order_type.upper(),    # "MARKET" or "LIMIT"
            transaction_type=side.upper(),    # "BUY" or "SELL"
        )
        if price is not None and order_type.upper() == "LIMIT":
            order_kwargs["price"] = price
        if trigger_price is not None:
            order_kwargs["trigger_price"] = trigger_price

        result: dict = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: groww_instance.place_order(**order_kwargs),
        )

        order_id = str(
            result.get("groww_order_id")
            or result.get("order_id")
            or ""
        )
        return TradeResponse(
            order_id=order_id,
            broker="groww",
            status="PLACED",
            message=f"{side.upper()} {quantity}\u00d7 {symbol} placed on Groww (ID: {order_id})",
            simulated=False,
        )

    async def order_status(self, order_id: str) -> OrderStatusResponse:
        """Fetch current order status from Groww."""
        from growwapi import GrowwAPI

        token = await self.authenticate()
        groww_instance = GrowwAPI(token)

        result: dict = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: groww_instance.get_order_details(order_id),
        )

        return OrderStatusResponse(
            order_id=order_id,
            broker="groww",
            status=result.get("status", "UNKNOWN"),
            filled_qty=int(result.get("filledQuantity") or result.get("filled_qty") or 0),
            avg_price=float(result.get("averagePrice") or result.get("avg_price") or 0.0),
            message=result.get("statusMessage") or result.get("message") or "",
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open Groww order."""
        from growwapi import GrowwAPI

        token = await self.authenticate()
        groww_instance = GrowwAPI(token)

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: groww_instance.cancel_order(order_id),
            )
            return True
        except Exception:
            return False

    # ── Market data ───────────────────────────────────────────────────────

    async def get_ltp(self, symbol: str, exchange: str = "BSE") -> Optional[float]:
        """Fetch last traded price via Groww market data endpoint."""
        try:
            token = self._access_token or self.api_key
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/market/quote",
                    params={"symbol": symbol, "exchange": exchange.upper()},
                    headers=self._headers(token),
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return float(data.get("ltp") or data.get("lastPrice") or 0)
        except Exception:
            pass
        return None
