"""
Stocks routes — list, search, update, bulk operations.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.models import FilteredStockStore, StockStore
from api.deps import get_current_user, get_pg
from api.schemas import (
    BulkUpdateMcapRequest,
    PaginatedStocks,
    StockResponse,
    StockUpdateRequest,
)

router = APIRouter()


def _to_stock_response(s: dict) -> StockResponse:
    return StockResponse(
        scrip_code=s.get("scrip_code") or "",
        scrip_name=s.get("scrip_name") or "",
        company_name=s.get("company_name") or "",
        market_cap=s.get("market_cap") or 0.0,
        group=s.get("group") or "",
        industry=s.get("industry") or "",
        isin=s.get("isin") or "",
        tags=s.get("tags") or [],
    )


@router.get("", response_model=PaginatedStocks)
async def list_stocks(
    page_size: int = Query(50, ge=1, le=500, alias="page_size"),
    limit: int = Query(None, ge=1, le=500, include_in_schema=False),
    skip: int = Query(0, ge=0),
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    group: Optional[str] = None,
    eligible_only: bool = True,
):
    """
    List stocks sorted by market cap (descending).

    - eligible_only=true (default) returns only stocks with market cap > threshold.
    - search: case-insensitive partial match on scrip_name or company_name.
    """
    effective_limit = limit if limit is not None else page_size
    store = FilteredStockStore if eligible_only else StockStore
    stocks = store.get_all()

    if search:
        q = search.lower()
        stocks = [
            s for s in stocks
            if q in s.get("scrip_name", "").lower()
            or q in s.get("company_name", "").lower()
            or q in s.get("scrip_code", "").lower()
        ]

    if group:
        stocks = [s for s in stocks if s.get("group", "").upper() == group.upper()]

    total = len(stocks)
    # Support both skip-based and page-based pagination
    offset = skip if skip > 0 else (page - 1) * effective_limit
    paged = stocks[offset : offset + effective_limit]
    pages = max(1, (total + effective_limit - 1) // effective_limit)

    return PaginatedStocks(
        items=[_to_stock_response(s) for s in paged],
        total=total,
        page=page,
        page_size=effective_limit,
        pages=pages,
    )


@router.get("/{scrip_code}", response_model=StockResponse)
async def get_stock(scrip_code: str):
    stock = FilteredStockStore.get_by_scrip_code(scrip_code)
    if not stock:
        # Fallback to all_stocks
        all_stocks = StockStore.get_all()
        stock = next((s for s in all_stocks if s.get("scrip_code") == scrip_code), None)
    if not stock:
        raise HTTPException(404, f"Stock {scrip_code} not found")
    return _to_stock_response(stock)


@router.patch("/{scrip_code}", response_model=StockResponse)
async def update_stock(
    scrip_code: str,
    body: StockUpdateRequest,
    user=Depends(get_current_user),
):
    """Update market_cap, company_name, or tags for a stock."""
    update = body.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(400, "No fields to update")

    # Update in both collections
    doc = StockStore.update_stock(scrip_code, update)
    if not doc:
        raise HTTPException(404, f"Stock {scrip_code} not found")

    FilteredStockStore.update_stock(scrip_code, update)

    return _to_stock_response(doc)


@router.post("/bulk-update-mcap")
async def bulk_update_mcap(
    body: BulkUpdateMcapRequest,
    user=Depends(get_current_user),
):
    """Bulk update market cap: absolute value or percentage change."""
    if body.value is None and body.percent is None:
        raise HTTPException(400, "Provide either 'value' or 'percent'")

    count = StockStore.bulk_update_mcap(
        body.scrip_codes, value=body.value, percent=body.percent
    )
    # Also update filtered_stocks
    FilteredStockStore.refresh_from_all_stocks()

    return {"updated_count": count}
