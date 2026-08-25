"""
Pydantic schemas for API request/response bodies.

Shared across all route modules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


# ── Growth / Margin sub-schemas ───────────────────────────────────────────────

class QoqYoy(BaseModel):
    qoq: Optional[float] = None
    yoy: Optional[float] = None


class AbsoluteValues(BaseModel):
    latest: Optional[float] = None
    previous: Optional[float] = None
    sqly: Optional[float] = None


class GrowthBlock(BaseModel):
    revenue: QoqYoy = QoqYoy()
    ebitda: QoqYoy = QoqYoy()
    net_profit: QoqYoy = QoqYoy()


class AbsoluteBlock(BaseModel):
    revenue: AbsoluteValues = AbsoluteValues()
    ebitda: AbsoluteValues = AbsoluteValues()
    net_profit: AbsoluteValues = AbsoluteValues()


class MarginsBlock(BaseModel):
    ebitda_margin: Optional[float] = None
    net_profit_margin: Optional[float] = None


# ── ui_payload ────────────────────────────────────────────────────────────────

class UiPayload(BaseModel):
    """The machine-readable analysis payload rendered by the frontend."""
    scrip_code: str
    company_name: str
    unit: str = "NA"
    quarter: str = ""
    raw_analysis: str = ""
    growth: GrowthBlock = GrowthBlock()
    absolute_numbers: AbsoluteBlock = AbsoluteBlock()
    margins: MarginsBlock = MarginsBlock()
    signal: str = "NEUTRAL"          # BUY | SELL | HOLD | NEUTRAL
    confidence: int = Field(0, ge=0, le=100)


class FinancialResultResponse(BaseModel):
    """Full financial result document returned by the API."""
    id: str = ""
    scrip_code: str
    scrip_name: str = ""
    company_name: str = ""
    market_cap: float = 0.0
    news_date: str = ""
    subject: str = ""
    pdf_link: str = ""
    ai_model: str = ""
    analyzed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    ui_payload: UiPayload
    estimate_comparison: Optional[EstimateComparison] = None


class PaginatedResults(BaseModel):
    """Paginated results response."""
    items: list[FinancialResultResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Broker ────────────────────────────────────────────────────────────────────

class BrokerKeyCreate(BaseModel):
    broker: str = Field(..., description="upstox | angel_one | kite | dhan | groww")
    api_key: str
    api_secret: str
    totp_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    mode: str = Field("paper", description="paper | live")


class BrokerKeyResponse(BaseModel):
    id: int
    broker: str
    api_key_masked: str    # e.g. "sk-****abc"
    mode: str
    is_connected: bool
    created_at: datetime


class TestConnectionResponse(BaseModel):
    broker: str
    connected: bool
    message: str
    balance: Optional[float] = None
    account_name: Optional[str] = None
    masked_account_id: Optional[str] = None


class ModeToggleRequest(BaseModel):
    mode: str = Field(..., description="paper | live")
    confirm: Optional[bool] = None
    password: Optional[str] = None


# ── Trade ─────────────────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    broker: str
    scrip_code: str
    symbol: str
    exchange: str = "BSE"
    side: str = Field(..., description="BUY | SELL")
    quantity: int = Field(gt=0)
    order_type: str = Field("LIMIT", description="LIMIT | MARKET | SL")
    price: Optional[float] = None
    trigger_price: Optional[float] = None


class TradeResponse(BaseModel):
    order_id: str
    broker: str
    status: str   # PLACED | FILLED | REJECTED | SIMULATED
    message: str
    simulated: bool = False


class OrderStatusResponse(BaseModel):
    order_id: str
    broker: str
    status: str
    filled_qty: int = 0
    avg_price: float = 0.0
    message: str = ""


class OrderListItem(BaseModel):
    """Full order record for the orders list endpoint."""
    id: int
    order_id: str
    broker: str
    scrip_code: str = ""
    symbol: str = ""
    exchange: str = "BSE"
    side: str = ""
    quantity: int = 0
    order_type: str = ""
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    status: str = ""
    filled_qty: int = 0
    avg_price: float = 0.0
    simulated: bool = False
    broker_order_id: Optional[str] = None
    created_at: Optional[datetime] = None


class LtpResponse(BaseModel):
    scrip_code: str
    ltp: Optional[float] = None
    exchange: str = "BSE"
    timestamp: Optional[datetime] = None


# ── Stocks ────────────────────────────────────────────────────────────────────

class StockResponse(BaseModel):
    scrip_code: str
    scrip_name: str = ""
    company_name: str = ""
    market_cap: float = 0.0
    group: str = ""
    industry: str = ""
    isin: str = ""
    tags: list[str] = []


class StockUpdateRequest(BaseModel):
    market_cap: Optional[float] = None
    company_name: Optional[str] = None
    tags: Optional[list[str]] = None


class BulkUpdateMcapRequest(BaseModel):
    scrip_codes: list[str]
    value: Optional[float] = None
    percent: Optional[float] = None


class PaginatedStocks(BaseModel):
    items: list[StockResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Bulk operations ───────────────────────────────────────────────────────────

class BulkDeleteRequest(BaseModel):
    ids: list[str]
    hard: bool = False


class BulkDeleteResponse(BaseModel):
    deleted_count: int


# ── Monitor Rules ─────────────────────────────────────────────────────────────

class MonitorRuleCreate(BaseModel):
    name: str
    field: str = Field(..., description="group | subject | market_cap | scrip_code")
    operator: str = Field(..., description="equals | contains | gt | lt | in | not_in")
    value: Any
    enabled: bool = True


class MonitorRuleResponse(BaseModel):
    id: str
    name: str
    field: str
    operator: str
    value: Any
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MonitorRuleUpdate(BaseModel):
    name: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Optional[Any] = None
    enabled: Optional[bool] = None


class MonitorStatusResponse(BaseModel):
    last_poll: Optional[datetime] = None
    announcements_today: int = 0
    results_today: int = 0
    rules_active: int = 0


# ── BSE Tools ─────────────────────────────────────────────────────────────────

class BseFetchResultRequest(BaseModel):
    scrip_code: str


# ── Estimates ─────────────────────────────────────────────────────────────────

class EstimateResponse(BaseModel):
    scrip_code: str
    scrip_name: str = ""
    sector: str = ""
    cap_size: str = ""
    revenue_estimate: Optional[float] = None
    ebitda_estimate: Optional[float] = None
    net_profit_estimate: Optional[float] = None
    imported_at: Optional[datetime] = None


class MetricComparison(BaseModel):
    estimate: Optional[float] = None
    actual: Optional[float] = None
    pct_diff: Optional[float] = None   # (actual - estimate) / |estimate| * 100
    verdict: Optional[str] = None       # BEAT | MISS | IN_LINE


class EstimateComparison(BaseModel):
    has_estimate: bool = False
    revenue: Optional[MetricComparison] = None
    ebitda: Optional[MetricComparison] = None
    net_profit: Optional[MetricComparison] = None


class ImportEstimatesResponse(BaseModel):
    imported: int
    message: str


# ── User Settings ─────────────────────────────────────────────────────────────

class UserSettings(BaseModel):
    default_broker: Optional[str] = None
    default_broker_id: Optional[int] = None
    default_quantity: int = 1
    default_order_size: int = 1
    table_view: str = "dense"
    theme: str = "dark"
    signal_filter: Optional[list[str]] = None
    keyboard_shortcuts_enabled: bool = True
    notifications_enabled: bool = True
    notifications: dict = {"new_results": True, "trade_fills": True}
    dashboard_layout: str = "grid"
