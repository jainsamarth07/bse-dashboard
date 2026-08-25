"""
Upstox broker adapter.

API docs: https://upstox.com/developer/api-documentation/

Authentication flow:
  1. User visits Upstox login URL with your api_key
  2. Upstox redirects to redirect_uri with ?code=...
  3. Exchange code for access_token via POST /login/authorization/token
  4. Use access_token in Authorization header for all subsequent calls

This adapter assumes the access_token is obtained externally (e.g. via a
frontend OAuth popup) and stored.  The authenticate() method handles the
code-exchange step.
"""

from __future__ import annotations

from typing import Optional

import httpx

from api.broker_adapters.base import BrokerAdapter
from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse

BASE_URL = "https://api.upstox.com/v2"


class UpstoxAdapter(BrokerAdapter):
    """Concrete adapter for Upstox V2 API."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._access_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────

    async def authenticate(self) -> str:
        """Exchange authorization code for access token.

        In a real flow the `auth_code` would come from the OAuth redirect.
        For now this is a skeleton — fill in auth_code handling.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/login/authorization/token",
                data={
                    "code": "AUTH_CODE_FROM_REDIRECT",  # placeholder
                    "client_id": self.api_key,
                    "client_secret": self.api_secret,
                    "redirect_uri": self.redirect_uri or "",
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data.get("access_token", "")
            return self._access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token or self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── Connection test ───────────────────────────────────────────────────

    async def test_connection(self) -> TestConnectionResponse:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/user/profile",
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code == 200:
                    profile = resp.json().get("data", {})
                    # Attempt to fetch fund balance
                    fund_resp = await client.get(
                        f"{BASE_URL}/user/get-funds-and-margin",
                        headers=self._headers(),
                        timeout=10,
                    )
                    balance = None
                    if fund_resp.status_code == 200:
                        equity = fund_resp.json().get("data", {}).get("equity", {})
                        balance = equity.get("available_margin")

                    return TestConnectionResponse(
                        broker="upstox",
                        connected=True,
                        message=f"Connected as {profile.get('user_name', 'N/A')}",
                        balance=balance,
                    )
                else:
                    return TestConnectionResponse(
                        broker="upstox",
                        connected=False,
                        message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )
        except Exception as exc:
            return TestConnectionResponse(
                broker="upstox", connected=False, message=str(exc)
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
        """Place order via Upstox V2 /order/place endpoint."""
        # Map our generic params to Upstox-specific payload
        product = "D"  # Delivery; use "I" for intraday
        validity = "DAY"

        payload = {
            "quantity": quantity,
            "product": product,
            "validity": validity,
            "price": price or 0,
            "tag": "bse_analyser",
            "instrument_token": f"{exchange}_EQ|{symbol}",
            "order_type": order_type.upper(),
            "transaction_type": side.upper(),
            "disclosed_quantity": 0,
            "trigger_price": trigger_price or 0,
            "is_amo": False,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/order/place",
                json=payload,
                headers=self._headers(),
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("status") == "success":
                return TradeResponse(
                    order_id=data["data"].get("order_id", ""),
                    broker="upstox",
                    status="PLACED",
                    message="Order placed successfully",
                    simulated=False,
                )
            else:
                return TradeResponse(
                    order_id="",
                    broker="upstox",
                    status="REJECTED",
                    message=data.get("message", resp.text[:200]),
                    simulated=False,
                )

    async def order_status(self, order_id: str) -> OrderStatusResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/order/details",
                params={"order_id": order_id},
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json().get("data", {})
            return OrderStatusResponse(
                order_id=order_id,
                broker="upstox",
                status=data.get("status", "UNKNOWN").upper(),
                filled_qty=int(data.get("filled_quantity", 0)),
                avg_price=float(data.get("average_price", 0)),
                message=data.get("status_message", ""),
            )

    async def cancel_order(self, order_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{BASE_URL}/order/cancel",
                params={"order_id": order_id},
                headers=self._headers(),
                timeout=10,
            )
            return resp.status_code == 200

    async def get_ltp(self, symbol: str, exchange: str = "BSE") -> Optional[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/market-quote/ltp",
                params={"instrument_key": f"{exchange}_EQ|{symbol}"},
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                for key, val in data.items():
                    return val.get("last_price")
            return None
