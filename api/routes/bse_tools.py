"""
BSE Tools routes — proxy endpoints for BSE API operations.

Rate limited: 10 req/min per user (enforced via simple in-memory counter).
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_current_user
from api.schemas import BseFetchResultRequest
from app.bse import BSE
from app.db.models import (
    FilteredStockStore,
    FinancialResultStore,
    NotificationStore,
    ResultCalendarStore,
    StockStore,
)

router = APIRouter()

# ── Simple rate limiter (in-memory) ──────────────────────────────────────────
_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60  # seconds
_RATE_MAX = 10     # requests per window


def _check_rate_limit(user_id: str):
    now = time.time()
    timestamps = _rate_limits[user_id]
    # Purge old entries
    _rate_limits[user_id] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_rate_limits[user_id]) >= _RATE_MAX:
        raise HTTPException(429, "Rate limit exceeded (10 req/min for BSE proxy)")
    _rate_limits[user_id].append(now)


def _bse_call(fn_name: str, **kwargs):
    """Execute a BSE API call safely."""
    with BSE("./") as bse:
        fn = getattr(bse, fn_name, None)
        if not fn:
            raise HTTPException(500, f"Unknown BSE method: {fn_name}")
        return fn(**kwargs)


@router.get("/securities")
async def bse_securities(
    group: str = Query("A"),
    user=Depends(get_current_user),
):
    """Proxy BSE listSecurities — returns stocks in a group."""
    _check_rate_limit(user["sub"])
    try:
        result = _bse_call("listSecurities", group=group)
        return {"group": group, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.get("/gainers")
async def bse_gainers(
    by: str = Query("group"),
    name: str = Query("A"),
    user=Depends(get_current_user),
):
    """Proxy BSE gainers."""
    _check_rate_limit(user["sub"])
    try:
        result = _bse_call("gainers", by=by, name=name)
        return {"by": by, "name": name, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.get("/losers")
async def bse_losers(
    by: str = Query("group"),
    name: str = Query("A"),
    user=Depends(get_current_user),
):
    """Proxy BSE losers."""
    _check_rate_limit(user["sub"])
    try:
        result = _bse_call("losers", by=by, name=name)
        return {"by": by, "name": name, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.get("/actions")
async def bse_actions(
    scrip_code: str = Query(...),
    user=Depends(get_current_user),
):
    """Proxy BSE corporate actions."""
    _check_rate_limit(user["sub"])
    try:
        result = _bse_call("actions", scripcode=scrip_code)
        return {"scrip_code": scrip_code, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.get("/calendar")
async def bse_calendar(
    refresh: bool = Query(False, description="Force refresh from BSE and update DB cache"),
    user=Depends(get_current_user),
):
    """Return result calendar from DB cache (with optional forced refresh)."""
    _check_rate_limit(user["sub"])
    try:
        ResultCalendarStore.ensure_indexes()

        if refresh or ResultCalendarStore.count() == 0:
            result = _bse_call("resultCalendar")
            if not isinstance(result, list):
                raise HTTPException(502, "Unexpected calendar payload from BSE")
            saved = ResultCalendarStore.upsert_rows(result)
            data = ResultCalendarStore.get_all()
            return {
                "data": data,
                "cached": True,
                "source": "bse_refreshed",
                "saved": saved,
            }

        data = ResultCalendarStore.get_all()
        return {
            "data": data,
            "cached": True,
            "source": "db",
            "saved": len(data),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.post("/calendar/refresh")
async def bse_calendar_refresh(user=Depends(get_current_user)):
    """Force-refresh calendar cache from BSE and persist to DB."""
    _check_rate_limit(user["sub"])
    try:
        ResultCalendarStore.ensure_indexes()
        result = _bse_call("resultCalendar")
        if not isinstance(result, list):
            raise HTTPException(502, "Unexpected calendar payload from BSE")
        saved = ResultCalendarStore.upsert_rows(result)
        data = ResultCalendarStore.get_all()
        return {
            "data": data,
            "cached": True,
            "source": "bse_refreshed",
            "saved": saved,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.get("/quote")
async def bse_quote(
    scrip_code: str = Query(...),
    user=Depends(get_current_user),
):
    """Proxy BSE quote."""
    _check_rate_limit(user["sub"])
    try:
        result = _bse_call("quote", scripcode=scrip_code)
        return {"scrip_code": scrip_code, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"BSE API error: {str(e)}")


@router.post("/fetch-result")
async def fetch_result(
    body: BseFetchResultRequest,
    user=Depends(get_current_user),
):
    """Trigger one-off PDF fetch + AI analysis for a specific scrip code.

    Fetches the latest Result announcement from BSE for the given scrip,
    downloads the PDF, runs AI analysis, and stores in Postgres.
    """
    _check_rate_limit(user["sub"])

    # Check stock exists
    stock = FilteredStockStore.get_by_scrip_code(body.scrip_code)
    if not stock:
        # Try all_stocks
        all_stocks = StockStore.get_all()
        stock = next(
            (s for s in all_stocks if s.get("scrip_code") == body.scrip_code),
            None,
        )
    if not stock:
        raise HTTPException(404, f"Stock {body.scrip_code} not found in database")

    # Fetch announcements filtering by scrip code
    try:
        with BSE("./") as bse:
            res = bse.announcements(page_no=1, category="Result")
            if not res or "Table" not in res:
                raise HTTPException(404, "No result announcements found")

            # Find matching announcement
            matching = [
                a for a in res["Table"]
                if str(a.get("SCRIP_CD", "")) == body.scrip_code
            ]
            if not matching:
                raise HTTPException(
                    404,
                    f"No result announcement found for scrip {body.scrip_code}",
                )

            announcement = matching[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch from BSE: {str(e)}")

    attach = announcement.get("ATTACHMENTNAME")
    if not attach:
        raise HTTPException(400, "No PDF attachment in announcement")

    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}"

    from app.services.pdf import download_pdf
    from app.services.ai import analyze_pdf
    from app.core.parser import parse_analysis

    company = stock.get("company_name", stock.get("scrip_name", ""))
    safe_name = company.replace("/", "_").replace(" ", "_")[:20]
    pdf_path = download_pdf(pdf_url, f"{safe_name}_fetch.pdf")
    if not pdf_path:
        raise HTTPException(502, "Failed to download PDF")

    try:
        analysis, model, extracted_via = analyze_pdf(pdf_path)
        if analysis.startswith("Error:"):
            raise HTTPException(502, f"AI analysis failed: {analysis}")

        parsed = parse_analysis(analysis)

        new_id = FinancialResultStore.save_result({
            "scrip_code": body.scrip_code,
            "scrip_name": stock.get("scrip_name", ""),
            "company_name": company,
            "market_cap": stock.get("market_cap", 0.0),
            "news_date": announcement.get("NEWS_DT", ""),
            "subject": announcement.get("NEWSSUB", ""),
            "pdf_link": pdf_url,
            "raw_analysis": analysis,
            "company_name_extracted": parsed.get("company_name_extracted", ""),
            "unit": parsed.get("unit", ""),
            "quarter": parsed.get("quarter", ""),
            "growth": parsed.get("growth", {}),
            "absolute_numbers": parsed.get("absolute_numbers", {}),
            "margins": parsed.get("margins", {}),
            "signal": parsed.get("signal", "NEUTRAL"),
            "confidence": parsed.get("confidence", 0),
            "ai_model": model,
            "extracted_via": extracted_via,
        })

        new_doc = FinancialResultStore.get_by_id(new_id)
        if not new_doc:
            raise HTTPException(500, "Failed to save result")

        NotificationStore.push("new_result", {
            "id": new_id,
            "scrip_code": body.scrip_code,
            "company_name": company,
        })

        return new_doc

    finally:
        try:
            os.remove(pdf_path)
        except OSError:
            pass
