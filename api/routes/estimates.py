"""
Estimates routes — import analyst estimates from Excel and expose CRUD endpoints.

POST /api/estimates/import   — Upload an Excel file (.xlsx) to populate estimates
GET  /api/estimates           — List all estimates
GET  /api/estimates/{scrip_code} — Get estimate for a specific scrip
DELETE /api/estimates         — Clear all estimates
"""

from __future__ import annotations

import io
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.db.models import EstimateStore, FilteredStockStore
from api.deps import get_current_user
from api.schemas import EstimateResponse, ImportEstimatesResponse

router = APIRouter()

# ── Excel column indices (0-based) for "Est vs Actuals" sheet ─────────────────
# Row layout (header is row 7 in the sheet, data from row 8):
#   C(2)  = BSE scrip / cap code
#   D(3)  = Script (company name)
#   G(6)  = Sector
#   H(7)  = Cap size (Large Cap / Mid Cap / Small Cap)
#   J(9)  = Est Revenue
#   S(18) = Est EBITDA
#   AD(29)= Est Reported PAT (net profit)

_COL_SCRIP_CODE = 2
_COL_SCRIP_NAME = 3
_COL_BLOOM = 5
_COL_SECTOR = 6
_COL_CAP_SIZE = 7
_COL_REV_EST = 9
_COL_EBITDA_EST = 18
_COL_PAT_EST = 29

_HEADER_ROW_INDEX = 7  # 0-based row index where actual header labels appear
_DATA_START_INDEX = 8  # 0-based row index where data begins

# Cache populated once per import call: scrip_name (upper) → scrip_code
_stocks_cache: dict[str, str] = {}


def _load_stocks_cache() -> dict[str, str]:
    """Build a lookup from normalised name/ticker → real BSE scrip_code."""
    cache: dict[str, str] = {}
    for doc in FilteredStockStore.get_all():
        sc = doc.get("scrip_code", "")
        if not sc:
            continue
        # Index by ticker (e.g. "TCS", "NUVOCO") and first word(s) of company name
        ticker = (doc.get("scrip_name") or "").strip().upper()
        if ticker:
            cache[ticker] = sc
        cname = (doc.get("company_name") or "").strip().upper()
        if cname:
            cache[cname] = sc
    return cache


def _resolve_bse_code(internal_code: str, scrip_name: str, bloom_code: str, cache: dict[str, str]) -> str:
    """Map an internal estimate code to a real BSE scrip_code via name lookup.

    Strategy (in order):
    1. Exact ticker match (e.g. "TCS" → "532540")
    2. Exact full company name match
    3. Partial prefix match (first 6 chars) against company names
    Fallback: keep the internal code (comparison won't fire but import won't break).
    """
    if bloom_code:
        bloom_ticker = bloom_code.strip().upper().split()[0]
        if bloom_ticker in cache:
            return cache[bloom_ticker]

    if not scrip_name:
        return internal_code

    key = scrip_name.strip().upper()

    # 1. Exact match
    if key in cache:
        return cache[key]

    # 2. Partial prefix match — handles "Nuvoco Vistas" → "NUVOCO VISTAS CORPORATION LTD"
    for cached_key, sc in cache.items():
        if cached_key.startswith(key) or key.startswith(cached_key[:max(6, len(key) - 4)]):
            return sc

    # 3. Token overlap — at least 2 words match
    key_tokens = set(re.split(r"[\s\-&]+", key))
    key_tokens.discard("")
    best_sc, best_overlap = internal_code, 0
    for cached_key, sc in cache.items():
        tokens = set(re.split(r"[\s\-&]+", cached_key))
        overlap = len(key_tokens & tokens)
        if overlap >= 2 and overlap > best_overlap:
            best_overlap, best_sc = overlap, sc
    return best_sc


def _safe_float(val) -> Optional[float]:
    """Convert a cell value to float, ignoring formulas / blanks / strings."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            f = float(val)
            return f if f == f else None  # NaN guard
        except (ValueError, TypeError):
            return None
    if isinstance(val, str):
        # Skip formula strings or empty strings
        if val.startswith("=") or val.strip() == "":
            return None
        try:
            return float(val.replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_excel(content: bytes) -> list[dict]:
    """Parse the estimates Excel file and return a list of estimate dicts."""
    try:
        import openpyxl
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="openpyxl is not installed. Run: pip install openpyxl",
        ) from e

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    # Use the first sheet (or "Est vs Actuals" if present)
    sheet_name = "Est vs Actuals" if "Est vs Actuals" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[sheet_name]

    # Build name → BSE scrip_code cache once for this import
    stocks_cache = _load_stocks_cache()

    estimates: list[dict] = []
    for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
        if row_idx < _DATA_START_INDEX:
            continue

        scrip_raw = row[_COL_SCRIP_CODE] if len(row) > _COL_SCRIP_CODE else None
        if scrip_raw is None:
            continue

        # Convert scrip code to string (BSE codes are integers in the sheet)
        internal_code = str(int(scrip_raw)) if isinstance(scrip_raw, float) else str(scrip_raw).strip()
        if not internal_code or internal_code == "0":
            continue

        scrip_name = str(row[_COL_SCRIP_NAME]).strip() if len(row) > _COL_SCRIP_NAME and row[_COL_SCRIP_NAME] else ""
        bloom_code = str(row[_COL_BLOOM]).strip() if len(row) > _COL_BLOOM and row[_COL_BLOOM] else ""
        sector = str(row[_COL_SECTOR]).strip() if len(row) > _COL_SECTOR and row[_COL_SECTOR] else ""
        cap_size = str(row[_COL_CAP_SIZE]).strip() if len(row) > _COL_CAP_SIZE and row[_COL_CAP_SIZE] else ""

        rev_est = _safe_float(row[_COL_REV_EST]) if len(row) > _COL_REV_EST else None
        ebitda_est = _safe_float(row[_COL_EBITDA_EST]) if len(row) > _COL_EBITDA_EST else None
        pat_est = _safe_float(row[_COL_PAT_EST]) if len(row) > _COL_PAT_EST else None

        # Skip rows that have no estimates at all
        if rev_est is None and ebitda_est is None and pat_est is None:
            continue

        # Resolve real BSE scrip_code — column C uses broker-internal IDs, not BSE codes
        scrip_code = _resolve_bse_code(internal_code, scrip_name, bloom_code, stocks_cache)

        estimates.append({
            "scrip_code": scrip_code,
            "scrip_name": scrip_name,
            "sector": sector,
            "cap_size": cap_size,
            "revenue_estimate": rev_est,
            "ebitda_estimate": ebitda_est,
            "net_profit_estimate": pat_est,
        })

    return estimates


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/import", response_model=ImportEstimatesResponse)
async def import_estimates(
    file: UploadFile = File(...),
    replace: bool = True,
    _user=Depends(get_current_user),
):
    """
    Upload an Excel (.xlsx) file containing analyst estimates.

    The sheet must follow the "Est vs Actuals" column layout:
    - Column C: BSE scrip code
    - Column D: Company name
    - Column G: Sector
    - Column H: Cap size
    - Column J: Estimated Revenue (Rs Cr)
    - Column S: Estimated EBITDA (Rs Cr)
    - Column AD: Estimated Reported PAT / Net Profit (Rs Cr)
    """
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported.")

    content = await file.read()
    estimates = _parse_excel(content)

    if not estimates:
        raise HTTPException(status_code=422, detail="No valid estimate rows found in the file.")

    if replace:
        EstimateStore.delete_all()

    imported = EstimateStore.bulk_upsert(estimates)
    return ImportEstimatesResponse(
        imported=imported,
        message=f"Successfully imported {imported} estimates (total rows parsed: {len(estimates)}).",
    )


@router.get("", response_model=list[EstimateResponse])
async def list_estimates(_user=Depends(get_current_user)):
    """Return all stored estimates."""
    docs = EstimateStore.get_all()
    return [EstimateResponse(**d) for d in docs]


@router.get("/count")
async def count_estimates(_user=Depends(get_current_user)):
    return {"count": EstimateStore.count()}


@router.get("/{scrip_code}", response_model=EstimateResponse)
async def get_estimate(scrip_code: str, _user=Depends(get_current_user)):
    """Return the estimate for a single scrip code."""
    doc = EstimateStore.get_by_scrip_code(scrip_code)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No estimate found for scrip_code={scrip_code}")
    return EstimateResponse(**doc)


@router.delete("")
async def clear_estimates(_user=Depends(get_current_user)):
    """Delete all estimates from the database."""
    deleted = EstimateStore.delete_all()
    return {"deleted": deleted, "message": f"Cleared {deleted} estimates."}
