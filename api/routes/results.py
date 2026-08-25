"""
Results routes — list, detail, search, delete, export, reprocess financial results.

Data is served from Postgres (financial_results table).
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse

from app.db.models import (
    FinancialResultStore,
    FilteredStockStore,
    NotificationStore,
)
from api.deps import get_current_user, get_pg
from api.schemas import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    FinancialResultResponse,
    PaginatedResults,
    UiPayload,
)

router = APIRouter()


def _utc(dt: datetime | None) -> datetime | None:
    """Tag a naive datetime as UTC so Pydantic emits '+00:00' (defensive; psycopg2 already returns aware datetimes)."""
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _as_float(value: object) -> float | None:
    """Normalize legacy and current numeric payload variants to a float."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    if isinstance(value, dict):
        for key in ("latest", "value", "current", "sqly", "previous"):
            if key in value:
                normalized = _as_float(value.get(key))
                if normalized is not None:
                    return normalized

    return None


def _to_ui_payload(doc: dict) -> UiPayload:
    """Convert a financial_results row to UiPayload."""
    growth = doc.get("growth", {})
    margins = doc.get("margins", {})
    absolute = doc.get("absolute_numbers", {})

    return UiPayload(
        scrip_code=doc.get("scrip_code", ""),
        company_name=doc.get("company_name_extracted") or doc.get("company_name", ""),
        unit=doc.get("unit", "NA"),
        quarter=doc.get("quarter", ""),
        raw_analysis=doc.get("raw_analysis", ""),
        growth={
            "revenue": growth.get("revenue", {}),
            "ebitda": growth.get("ebitda", {}),
            "net_profit": growth.get("net_profit", {}),
        },
        absolute_numbers={
            "revenue": absolute.get("revenue", {}),
            "ebitda": absolute.get("ebitda", {}),
            "net_profit": absolute.get("net_profit", {}),
        },
        margins={
            "ebitda_margin": _as_float(margins.get("ebitda_margin")),
            "net_profit_margin": _as_float(margins.get("net_profit_margin")),
        },
        signal=doc.get("signal", "NEUTRAL"),
        confidence=doc.get("confidence", 0),
    )


def _to_response(doc: dict) -> FinancialResultResponse:
    return FinancialResultResponse(
        id=doc.get("_id", ""),
        scrip_code=doc.get("scrip_code", ""),
        scrip_name=doc.get("scrip_name", ""),
        company_name=doc.get("company_name", ""),
        market_cap=doc.get("market_cap", 0.0),
        news_date=doc.get("news_date", ""),
        subject=doc.get("subject", ""),
        pdf_link=doc.get("pdf_link", ""),
        ai_model=doc.get("ai_model", ""),
        analyzed_at=_utc(doc.get("analyzed_at")),
        deleted_at=_utc(doc.get("deleted_at")),
        ui_payload=_to_ui_payload(doc),
    )


@router.get("", response_model=PaginatedResults)
async def list_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="page_size"),
    limit: int = Query(None, ge=1, le=200, include_in_schema=False),
    sort_by: str = Query("analyzed_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    signal: Optional[str] = None,
    min_mcap: Optional[float] = None,
    max_mcap: Optional[float] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    include_deleted: bool = False,
):
    """Paginated, filterable list of financial results."""
    # Support both 'page_size' and 'limit' param names
    effective_limit = limit if limit is not None else page_size
    fd = None
    td = None
    if from_date:
        try:
            fd = datetime.fromisoformat(from_date)
        except ValueError:
            pass
    if to_date:
        try:
            td = datetime.fromisoformat(to_date)
        except ValueError:
            pass

    docs, total = FinancialResultStore.get_paginated(
        page=page,
        limit=effective_limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        signal=signal,
        min_mcap=min_mcap,
        max_mcap=max_mcap,
        sector=sector,
        search=search,
        from_date=fd,
        to_date=td,
        include_deleted=include_deleted,
    )

    pages = max(1, (total + effective_limit - 1) // effective_limit)
    return PaginatedResults(
        items=[_to_response(d) for d in docs],
        total=total,
        page=page,
        page_size=effective_limit,
        pages=pages,
    )


@router.get("/export")
async def export_results_csv(
    signal: Optional[str] = None,
    min_mcap: Optional[float] = None,
    max_mcap: Optional[float] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """Export filtered results as CSV stream."""
    fd = None
    td = None
    if from_date:
        try:
            fd = datetime.fromisoformat(from_date)
        except ValueError:
            pass
    if to_date:
        try:
            td = datetime.fromisoformat(to_date)
        except ValueError:
            pass

    docs, _ = FinancialResultStore.get_paginated(
        page=1,
        limit=10000,
        signal=signal,
        min_mcap=min_mcap,
        max_mcap=max_mcap,
        sector=sector,
        search=search,
        from_date=fd,
        to_date=td,
    )

    columns = [
        "scrip_code", "scrip_name", "company_name", "market_cap",
        "quarter", "revenue_qoq", "revenue_yoy", "ebitda_qoq", "ebitda_yoy",
        "net_profit_qoq", "net_profit_yoy", "ebitda_margin", "net_profit_margin",
        "signal", "confidence", "ai_model", "analyzed_at",
    ]

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        for doc in docs:
            g = doc.get("growth", {})
            m = doc.get("margins", {})
            writer.writerow([
                doc.get("scrip_code", ""),
                doc.get("scrip_name", ""),
                doc.get("company_name", ""),
                doc.get("market_cap", 0),
                doc.get("quarter", ""),
                g.get("revenue", {}).get("qoq"),
                g.get("revenue", {}).get("yoy"),
                g.get("ebitda", {}).get("qoq"),
                g.get("ebitda", {}).get("yoy"),
                g.get("net_profit", {}).get("qoq"),
                g.get("net_profit", {}).get("yoy"),
                _as_float(m.get("ebitda_margin")),
                _as_float(m.get("net_profit_margin")),
                doc.get("signal", "NEUTRAL"),
                doc.get("confidence", 0),
                doc.get("ai_model", ""),
                doc.get("analyzed_at", ""),
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_results(
    body: BulkDeleteRequest,
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Bulk soft or hard delete. Hard delete requires admin role."""
    if body.hard:
        row = await pg.fetchrow("SELECT role FROM users WHERE id=$1", int(user["sub"]))
        if not row or row["role"] != "admin":
            raise HTTPException(403, "Hard delete requires admin role")
        count = FinancialResultStore.bulk_hard_delete(body.ids)
    else:
        count = FinancialResultStore.bulk_soft_delete(body.ids)

    for doc_id in body.ids:
        NotificationStore.push("deleted_result", {"id": doc_id})

    return BulkDeleteResponse(deleted_count=count)


@router.get("/{scrip_code}/latest", response_model=FinancialResultResponse)
async def latest_result(scrip_code: str):
    """Get the most recent analysis for a given scrip code."""
    results = FinancialResultStore.get_by_scrip(scrip_code)
    if not results:
        raise HTTPException(404, f"No results for scrip_code={scrip_code}")
    return _to_response(results[0])


@router.get("/{scrip_code}/history", response_model=list[FinancialResultResponse])
async def result_history(scrip_code: str, limit: int = Query(50, ge=1, le=200)):
    """Get historical analyses for a scrip code (most recent first)."""
    results = FinancialResultStore.get_by_scrip(scrip_code)[:limit]
    return [_to_response(d) for d in results]


@router.delete("/{doc_id}")
async def delete_result(
    doc_id: str,
    hard: bool = Query(False),
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Soft-delete a result. Query param ?hard=true requires admin role."""
    if hard:
        row = await pg.fetchrow("SELECT role FROM users WHERE id=$1", int(user["sub"]))
        if not row or row["role"] != "admin":
            raise HTTPException(403, "Hard delete requires admin role")
        ok = FinancialResultStore.hard_delete(doc_id)
    else:
        ok = FinancialResultStore.soft_delete(doc_id)

    if not ok:
        raise HTTPException(404, "Result not found")

    NotificationStore.push("deleted_result", {"id": doc_id})
    return {"ok": True}


@router.post("/{doc_id}/reprocess", response_model=FinancialResultResponse)
async def reprocess_result(doc_id: str, user=Depends(get_current_user)):
    """Re-download PDF, re-analyse, and store as a new result (keeping old)."""
    existing = FinancialResultStore.get_by_id(doc_id)
    if not existing:
        raise HTTPException(404, "Result not found")

    pdf_url = existing.get("pdf_link", "")
    if not pdf_url:
        raise HTTPException(400, "No PDF link available to reprocess")

    scrip_code = existing.get("scrip_code", "")
    company = existing.get("company_name", existing.get("scrip_name", ""))

    # Import processing dependencies lazily
    from app.services.pdf import download_pdf
    from app.services.ai import analyze_pdf
    from app.core.parser import parse_analysis

    safe_name = company.replace("/", "_").replace(" ", "_")[:20]
    pdf_path = download_pdf(pdf_url, f"{safe_name}_reprocess.pdf")
    if not pdf_path:
        raise HTTPException(502, "Failed to download PDF")

    try:
        analysis, model, extracted_via = analyze_pdf(
            pdf_path,
            announcement_subject=existing.get("subject", ""),
            announcement_date=existing.get("news_date", ""),
        )
        if analysis.startswith("Error:"):
            raise HTTPException(502, f"AI analysis failed: {analysis}")

        parsed = parse_analysis(analysis)

        new_id = FinancialResultStore.save_result({
            "scrip_code": scrip_code,
            "scrip_name": existing.get("scrip_name", ""),
            "company_name": existing.get("company_name", company),
            "market_cap": existing.get("market_cap", 0.0),
            "news_date": existing.get("news_date", ""),
            "subject": existing.get("subject", ""),
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
            raise HTTPException(500, "Failed to save reprocessed result")

        NotificationStore.push("new_result", {
            "id": new_id,
            "scrip_code": scrip_code,
            "company_name": company,
        })

        return _to_response(new_doc)
    finally:
        try:
            os.remove(pdf_path)
        except OSError:
            pass
