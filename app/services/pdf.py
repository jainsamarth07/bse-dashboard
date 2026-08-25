"""
PDF download and smart text extraction service.

Exports
-------
download_pdf(url, filename) → str | None
extract_text(pdf_path, max_pages) → str
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import fitz  # PyMuPDF
import requests
from PIL import Image

# ── Keywords that strongly indicate a financial-results page ─────────────────

_RESULT_KEYWORDS: list[str] = [
    # Revenue / Income
    "revenue from operations", "total income", "total revenue",
    # Profit line items
    "profit before tax", "profit after tax", "profit for the period",
    "net profit", "profit/(loss)",
    # Typical expense lines
    "depreciation and amortisation", "depreciation and amortization",
    "finance cost", "finance costs",
    # Period column headers
    "quarter ended", "period ended", "half year ended",
    # Consolidated / Standalone
    "consolidated", "standalone",
    # EPS row
    "earnings per share", "basic eps", "diluted eps",
    # Document-type identifiers
    "statement of financial results", "unaudited financial results",
    "audited financial results",
]


def _score_page(text: str) -> int:
    lower = text.lower()
    return sum(1 for kw in _RESULT_KEYWORDS if kw in lower)


# ── Public API ────────────────────────────────────────────────────────────────

def download_pdf(url: str, filename: str | None = None) -> str | None:
    """Download a PDF from *url* into the system temp directory.

    Returns the local file path on success, None on failure.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bseindia.com/",
            "Accept": "application/pdf",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        fname = filename or url.split("/")[-1] or "document.pdf"
        filepath = os.path.join(tempfile.gettempdir(), fname)
        with open(filepath, "wb") as fh:
            fh.write(resp.content)

        _ts()
        print(f"✅ PDF downloaded: {filepath}")
        return filepath
    except Exception as exc:
        _ts()
        print(f"❌ PDF download failed: {exc}")
        return None


def extract_text(pdf_path: str, max_result_pages: int = 3) -> str:
    """Extract text from *only* the pages most likely to contain the results table.

    Strategy
    --------
    1. Score every page by counting financial-result keywords.
    2. Select the top ``max_result_pages`` scoring pages (min score 4).
    3. Return their combined text.
    4. Falls back to the first 3 pages if nothing scores highly.

    This cuts token usage by 80-90 % vs sending the whole PDF.
    """
    try:
        doc = fitz.open(pdf_path)
        total = len(doc)
        _ts()
        print(f"📄 Scanning {total} page(s) for results table …")

        page_scores: list[tuple[int, int, str]] = []
        for i in range(total):
            text = doc.load_page(i).get_text()
            page_scores.append((i, _score_page(text), text))
        doc.close()

        MIN_SCORE = 4
        good = [(pn, sc, txt) for pn, sc, txt in page_scores if sc >= MIN_SCORE]
        good.sort(key=lambda x: x[1], reverse=True)
        selected = good[:max_result_pages]

        if not selected:
            selected = page_scores[: min(3, total)]
            _ts()
            print(f"⚠️  No high-score pages — falling back to first {len(selected)} page(s)")
        else:
            selected.sort(key=lambda x: x[0])
            nums = [p[0] + 1 for p in selected]
            scores = [p[1] for p in selected]
            _ts()
            print(f"✅ Results found on page(s) {nums} (scores: {scores})")

        full_text = "".join(
            f"\n--- Page {pn + 1} (score {sc}) ---\n{txt}"
            for pn, sc, txt in selected
        )

        total_chars = sum(len(txt) for _, _, txt in selected)
        if total_chars < 200:
            _ts()
            print(f"⚠️  PDF appears scanned/image-based ({total_chars} chars) — cannot extract text.")
            return ""

        _ts()
        print(
            f"✅ Sending {len(selected)}/{total} page(s) to AI "
            f"(~{total - len(selected)} page(s) saved)"
        )
        return full_text
    except Exception as exc:
        _ts()
        print(f"❌ PDF extraction error: {exc}")
        return ""


def detect_image_pages(pdf_path: str) -> list[int]:
    """Return 0-indexed page numbers where financial tables appear as images.

    A page is flagged when it has a 'financial results' header but fewer than
    800 extractable characters (indicating an image-based table).
    """
    doc = fitz.open(pdf_path)
    image_pages: list[int] = []
    low_text_with_image: list[int] = []

    for i in range(len(doc)):
        page = doc.load_page(i)
        text = page.get_text()
        lower = text.lower()
        text_len = len(text.strip())
        has_images = len(page.get_images(full=True)) > 0

        has_header = any(
            kw in lower
            for kw in ["financial results", "statement of", "unaudited", "audited"]
        )

        # Compute keyword score to distinguish actual result pages from
        # auditor-report pages that also contain 'financial results' / 'audited'.
        kw_score = _score_page(text)

        # Strong signal: result-table header + some financial keywords + sparse text.
        # Score ≥ 2 avoids false-positives on auditor's report pages.
        if has_header and kw_score >= 2 and text_len < 800:
            image_pages.append(i)
            continue

        # Fallback signal: page is nearly textless but has embedded images.
        if has_images and text_len < 120:
            low_text_with_image.append(i)

    # If nothing matched header-based detection, use low-text image pages.
    if not image_pages and low_text_with_image:
        image_pages = low_text_with_image

    doc.close()
    return image_pages


def render_pages_as_images(
    pdf_path: str,
    page_numbers: list[int],
    dpi: int = 200,
) -> list[Image.Image]:
    """Render PDF pages as PIL images for Gemini Vision."""
    images: list[Image.Image] = []
    doc = fitz.open(pdf_path)
    for pg in page_numbers:
        if pg < len(doc):
            pix = doc.load_page(pg).get_pixmap(dpi=dpi)
            images.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
    doc.close()
    return images


def _ts() -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ", end="")
