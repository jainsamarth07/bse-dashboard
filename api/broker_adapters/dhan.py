"""
Dhan (DhanHQ) broker adapter.

API docs: https://dhanhq.co/docs/v2/

Authentication:
  Dhan does NOT use a traditional API key/secret pair for order placement.
  Instead it uses:
    - access-token  : A JWT obtained from web.dhan.co (valid 24 h).
                      Passed in the `api_key` field when configuring the broker.
    - dhanClientId  : Your Dhan client ID (e.g. "1000000001").
                      Passed in the `api_secret` field.

  Optionally, if `totp_secret` is set together with a Dhan PIN stored as
  `redirect_uri` (used as a PIN field), the adapter can auto-refresh the
  access token via:
    POST https://auth.dhan.co/app/generateAccessToken
         ?dhanClientId=...&pin=...&totp=...

Security ID note:
  Dhan identifies instruments by a numeric `securityId` from their instruments
  list (https://dhanhq.co/docs/v2/instruments/), NOT by the trading symbol.
  Pass the Dhan security ID as the `symbol` field when placing orders, or use
  the BSE scrip code — for BSE_EQ orders the scrip code maps 1-to-1 with the
  Dhan security ID for most stocks.
"""

from __future__ import annotations

from typing import Optional

import httpx
import pyotp

from api.broker_adapters.base import BrokerAdapter
from api.schemas import TestConnectionResponse, TradeResponse, OrderStatusResponse

BASE_URL = "https://api.dhan.co/v2"
AUTH_URL = "https://auth.dhan.co/app/generateAccessToken"

# Map our generic exchange names to Dhan's exchangeSegment values
_EXCHANGE_MAP = {
    "BSE": "BSE_EQ",
    "NSE": "NSE_EQ",
    "BSE_EQ": "BSE_EQ",
    "NSE_EQ": "NSE_EQ",
}

# Map our generic order types to Dhan's orderType values
_ORDER_TYPE_MAP = {
    "LIMIT": "LIMIT",
    "MARKET": "MARKET",
    "SL": "STOP_LOSS",
    "STOP_LOSS": "STOP_LOSS",
    "SL-M": "STOP_LOSS_MARKET",
    "STOP_LOSS_MARKET": "STOP_LOSS_MARKET",
}


class DhanAdapter(BrokerAdapter):
    """Concrete adapter for the Dhan (DhanHQ) V2 API.

    Field mapping (to fit the standard BrokerAdapter interface):
      api_key      → Dhan access-token (JWT from web.dhan.co)
      api_secret   → dhanClientId
      totp_secret  → TOTP secret (optional, for auto-token refresh)
      redirect_uri → Dhan PIN (6-digit, optional, needed with totp_secret)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._access_token: str = self._normalize_token(self.api_key)
        self._client_id: str = (self.api_secret or "").strip()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "access-token": self._access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _normalize_token(token: str | None) -> str:
        raw = (token or "").strip().strip('"').strip("'")
        if raw.lower().startswith("bearer "):
            return raw.split(" ", 1)[1].strip()
        return raw

    @staticmethod
    def _is_invalid_token(status_code: int, text: str) -> bool:
        body = (text or "").lower()
        return (
            status_code in (400, 401)
            and (
                "invalid token" in body
                or "dh-906" in body
                or '"errorcode":"dh-906"' in body
            )
        )

    def _exchange_segment(self, exchange: str) -> str:
        return _EXCHANGE_MAP.get(exchange.upper(), "BSE_EQ")

    def _order_type(self, order_type: str) -> str:
        return _ORDER_TYPE_MAP.get(order_type.upper(), "LIMIT")

    # ── Authentication ────────────────────────────────────────────────────

    async def authenticate(self) -> str:
        """Return/refresh the Dhan access token.

        If both `totp_secret` and `redirect_uri` (used as PIN) are provided,
        a fresh access token is generated from Dhan's TOTP endpoint.
        Otherwise the pre-configured `api_key` is returned as-is (the standard
        individual-trader flow where the token is copied from web.dhan.co).
        """
        if self.totp_secret and self.redirect_uri:
            # redirect_uri doubles as the Dhan PIN in this adapter
            pin = self.redirect_uri.strip()
            totp = pyotp.TOTP(self.totp_secret).now()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    AUTH_URL,
                    params={
                        "dhanClientId": self._client_id,
                        "pin": pin,
                        "totp": totp,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                self._access_token = self._normalize_token(data.get("accessToken", self.api_key))
        return self._access_token

    # ── Connection test ───────────────────────────────────────────────────

    async def test_connection(self) -> TestConnectionResponse:
        """Verify the access token by calling GET /v2/profile."""
        try:
            # Keep token normalized even for manually pasted values.
            self._access_token = self._normalize_token(self._access_token)

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{BASE_URL}/profile",
                    headers=self._headers(),
                    timeout=10,
                )

                # Some Dhan invalid-token cases return HTTP 400 with DH-906.
                # If auto-refresh inputs are available, refresh and retry once.
                if self._is_invalid_token(resp.status_code, resp.text) and self.totp_secret and self.redirect_uri:
                    await self.authenticate()
                    resp = await client.get(
                        f"{BASE_URL}/profile",
                        headers=self._headers(),
                        timeout=10,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    client_id = data.get("dhanClientId", self._client_id)
                    segments = data.get("activeSegment", "")

                    # Fetch fund balance
                    balance: Optional[float] = None
                    fund_resp = await client.get(
                        f"{BASE_URL}/fundlimit",
                        headers=self._headers(),
                        timeout=10,
                    )
                    if fund_resp.status_code == 200:
                        fund_data = fund_resp.json()
                        try:
                            balance = float(
                                fund_data.get("availabelBalance")
                                or fund_data.get("availableBalance")
                                or fund_data.get("net")
                                or 0
                            )
                        except (ValueError, TypeError):
                            pass

                    return TestConnectionResponse(
                        broker="dhan",
                        connected=True,
                        message=f"Connected | Client: {client_id} | Segments: {segments}",
                        balance=balance,
                        account_name=client_id,
                        masked_account_id=f"****{self._client_id[-4:]}",
                    )

                if self._is_invalid_token(resp.status_code, resp.text):
                    return TestConnectionResponse(
                        broker="dhan",
                        connected=False,
                        message=(
                            "Invalid or expired Dhan access token. "
                            "Generate a fresh token from web.dhan.co → "
                            "My Profile → Access DhanHQ APIs."
                        ),
                    )

                return TestConnectionResponse(
                    broker="dhan",
                    connected=False,
                    message=f"Profile fetch failed (HTTP {resp.status_code}): {resp.text[:200]}",
                )

        except httpx.TimeoutException:
            return TestConnectionResponse(
                broker="dhan",
                connected=False,
                message="Connection timed out. Check your internet connection.",
            )
        except Exception as exc:
            return TestConnectionResponse(
                broker="dhan", connected=False, message=f"Connection error: {exc}"
            )

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
        """Place a BUY or SELL order via Dhan V2 /orders endpoint.

        The `symbol` field should be Dhan's numeric securityId for the instrument.
        For BSE equity the BSE scrip code (e.g. "500325") can be used directly
        as Dhan's securityId.  See https://dhanhq.co/docs/v2/instruments/ for
        the full mapping CSV.
        """
        dhan_order_type = self._order_type(order_type)
        exchange_segment = self._exchange_segment(exchange)

        payload: dict = {
            "dhanClientId": self._client_id,
            "transactionType": side.upper(),
            "exchangeSegment": exchange_segment,
            "productType": "CNC",        # delivery; callers can override via subclass
            "orderType": dhan_order_type,
            "validity": "DAY",
            "securityId": str(symbol),
            "quantity": quantity,
            "disclosedQuantity": 0,
            "price": price if price is not None else 0,
            "triggerPrice": trigger_price if trigger_price is not None else 0,
            "afterMarketOrder": False,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BASE_URL}/orders",
                    json=payload,
                    headers=self._headers(),
                    timeout=15,
                )
                data = resp.json()

                if resp.status_code in (200, 201):
                    order_id = str(data.get("orderId", ""))
                    status = data.get("orderStatus", "PENDING")
                    return TradeResponse(
                        order_id=order_id,
                        broker="dhan",
                        status=status,
                        message=f"Order placed: {side.upper()} {quantity}x {symbol} ({exchange_segment})",
                        simulated=False,
                    )

                # Dhan error response: {"errorType": ..., "errorCode": ..., "errorMessage": ...}
                err_msg = (
                    data.get("errorMessage")
                    or data.get("message")
                    or resp.text[:300]
                )
                return TradeResponse(
                    order_id="",
                    broker="dhan",
                    status="REJECTED",
                    message=f"Order rejected ({resp.status_code}): {err_msg}",
                    simulated=False,
                )

        except Exception as exc:
            return TradeResponse(
                order_id="",
                broker="dhan",
                status="REJECTED",
                message=f"Order placement error: {exc}",
                simulated=False,
            )

    async def order_status(self, order_id: str) -> OrderStatusResponse:
        """Fetch current status of an order by its orderId."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/orders/{order_id}",
                headers=self._headers(),
                timeout=10,
            )
            data = resp.json() if resp.status_code == 200 else {}

            return OrderStatusResponse(
                order_id=order_id,
                broker="dhan",
                status=data.get("orderStatus", "UNKNOWN").upper(),
                filled_qty=int(data.get("filledQty", 0)),
                avg_price=float(data.get("averageTradedPrice", 0)),
                message=(
                    data.get("omsErrorDescription")
                    or data.get("orderStatus", "")
                ),
            )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True on success (202 Accepted)."""
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{BASE_URL}/orders/{order_id}",
                headers=self._headers(),
                timeout=10,
            )
            return resp.status_code in (200, 202)

    # ── Market data ───────────────────────────────────────────────────────

    async def get_ltp(self, symbol: str, exchange: str = "BSE") -> Optional[float]:
        """Last traded price via Dhan's market quote endpoint."""
        exchange_segment = self._exchange_segment(exchange)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BASE_URL}/marketfeed/ltp",
                    json={exchange_segment: [str(symbol)]},
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Response: {"data": {"BSE_EQ": {"<securityId>": {"last_price": ...}}}}
                    segment_data = data.get("data", {}).get(exchange_segment, {})
                    instrument_data = segment_data.get(str(symbol), {})
                    ltp = instrument_data.get("last_price")
                    return float(ltp) if ltp is not None else None
        except Exception:
            pass
        return None
