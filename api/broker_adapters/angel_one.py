"""
Angel One (AngelBroking) SmartAPI adapter.

API docs: https://smartapi.angelone.in/docs

Authentication flow:
  1. Generate session with client_id + password + TOTP
  2. Receive jwt_token for subsequent API calls
  3. Use jwt_token in Authorization header

Requires: pip install pyotp  (for TOTP generation)
"""

from __future__ import annotations

from typing import Optional

import httpx

from api.broker_adapters.base import BrokerAdapter
from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse

BASE_URL = "https://apiconnect.angelone.in"


class AngelOneAdapter(BrokerAdapter):
    """Concrete adapter for Angel One SmartAPI."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._jwt_token: str | None = None
        self._refresh_token: str | None = None
        self._feed_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────

    async def authenticate(self) -> str:
        """Login with client_id (api_key), password (api_secret), and TOTP."""
        import pyotp

        totp = pyotp.TOTP(self.totp_secret).now() if self.totp_secret else ""

        payload = {
            "clientcode": self.api_key,
            "password": self.api_secret,
            "totp": totp,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-UserType": "USER",
                    "X-SourceID": "WEB",
                    "X-ClientLocalIP": "0.0.0.0",
                    "X-ClientPublicIP": "0.0.0.0",
                    "X-MACAddress": "00:00:00:00:00:00",
                    "X-PrivateKey": self.api_key,
                },
                timeout=15,
            )
            data = resp.json()

            if data.get("status"):
                self._jwt_token = data["data"]["jwtToken"]
                self._refresh_token = data["data"]["refreshToken"]
                self._feed_token = data["data"].get("feedToken", "")
                return self._jwt_token
            else:
                raise Exception(f"Angel One login failed: {data.get('message')}")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._jwt_token or ''}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "0.0.0.0",
            "X-ClientPublicIP": "0.0.0.0",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
        }

    # ── Connection test ───────────────────────────────────────────────────

    async def test_connection(self) -> TestConnectionResponse:
        try:
            await self.authenticate()

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/rest/secure/angelbroking/user/v1/getRMS",
                    headers=self._headers(),
                    timeout=10,
                )
                data = resp.json()

                if data.get("status"):
                    rms = data.get("data", {})
                    balance = None
                    try:
                        balance = float(rms.get("net", 0))
                    except (ValueError, TypeError):
                        pass

                    return TestConnectionResponse(
                        broker="angel_one",
                        connected=True,
                        message=f"Connected. Net balance: ₹{balance:,.2f}" if balance else "Connected",
                        balance=balance,
                    )
                else:
                    return TestConnectionResponse(
                        broker="angel_one",
                        connected=False,
                        message=data.get("message", "Unknown error"),
                    )
        except Exception as exc:
            return TestConnectionResponse(
                broker="angel_one", connected=False, message=str(exc)
            )

    # ── Orders ────────────────────────────────────────────────────────────

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
        """Place order via Angel One SmartAPI."""
        if not self._jwt_token:
            await self.authenticate()

        # Angel One order type mapping
        angel_order_type = {
            "LIMIT": "LIMIT",
            "MARKET": "MARKET",
            "SL": "STOPLOSS_LIMIT",
        }.get(order_type.upper(), "LIMIT")

        angel_exchange = {
            "BSE": "BSE",
            "NSE": "NSE",
        }.get(exchange.upper(), "BSE")

        payload = {
            "variety": "NORMAL",
            "tradingsymbol": f"{symbol}-EQ",
            "symboltoken": "",  # Needs symbol token lookup — see note below
            "transactiontype": side.upper(),
            "exchange": angel_exchange,
            "ordertype": angel_order_type,
            "producttype": "DELIVERY",
            "duration": "DAY",
            "price": str(price or 0),
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity),
            "triggerprice": str(trigger_price or 0),
        }

        # NOTE: Angel One requires a `symboltoken` for each instrument.
        # In production, maintain a mapping file or use their search endpoint:
        #   POST /rest/secure/angelbroking/order/v1/searchScrip
        #   {"exchange": "BSE", "searchscrip": "RELIANCE"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/rest/secure/angelbroking/order/v1/placeOrder",
                json=payload,
                headers=self._headers(),
                timeout=15,
            )
            data = resp.json()

            if data.get("status"):
                return TradeResponse(
                    order_id=data["data"].get("orderid", ""),
                    broker="angel_one",
                    status="PLACED",
                    message="Order placed successfully",
                    simulated=False,
                )
            else:
                return TradeResponse(
                    order_id="",
                    broker="angel_one",
                    status="REJECTED",
                    message=data.get("message", "Order failed"),
                    simulated=False,
                )

    async def order_status(self, order_id: str) -> OrderStatusResponse:
        if not self._jwt_token:
            await self.authenticate()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/rest/secure/angelbroking/order/v1/details/{order_id}",
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json().get("data", {})
            return OrderStatusResponse(
                order_id=order_id,
                broker="angel_one",
                status=data.get("orderstatus", "UNKNOWN").upper(),
                filled_qty=int(data.get("filledshares", 0)),
                avg_price=float(data.get("averageprice", 0)),
                message=data.get("text", ""),
            )

    async def cancel_order(self, order_id: str) -> bool:
        if not self._jwt_token:
            await self.authenticate()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/rest/secure/angelbroking/order/v1/cancelOrder",
                json={"variety": "NORMAL", "orderid": order_id},
                headers=self._headers(),
                timeout=10,
            )
            return resp.json().get("status", False)

    async def get_ltp(self, symbol: str, exchange: str = "BSE") -> Optional[float]:
        if not self._jwt_token:
            await self.authenticate()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/rest/secure/angelbroking/market/v1/quote",
                json={
                    "mode": "LTP",
                    "exchangeTokens": {exchange.upper(): [symbol]},
                },
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json().get("data", {})
            fetched = data.get("fetched", [])
            if fetched:
                return float(fetched[0].get("ltp", 0))
            return None
