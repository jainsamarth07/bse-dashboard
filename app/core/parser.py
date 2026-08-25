"""
Parse structured text produced by the AI into a typed Python dict.

The AI is asked to produce a fixed plain-text format (see core/prompts.py)
followed by a machine-readable UI_PAYLOAD JSON block.
This module converts that text into the nested dict that gets stored in Postgres.
"""

from __future__ import annotations

import json
import re
from datetime import datetime


def _safe_float(val: str) -> float | None:
    """Convert a string to float; return None for 'NA', empty, or garbage."""
    val = val.strip().replace(",", "")
    if not val or val.upper() == "NA":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _extract_qoq_yoy(text: str, section_name: str) -> tuple[float | None, float | None]:
    """Extract Q/Q and Y/Y growth percentages for a named section.

    Handles bullet variants (•, -, *) and optional surrounding whitespace.

    Example input block:
        Revenue:
        • Q/Q: -35.8%
        • Y/Y: 9.9%
    """
    pattern = (
        rf"{re.escape(section_name)}:\s*\n"
        r"[•\-\*]\s*Q/Q:\s*([\d.,\-NA]+)%\s*\n"
        r"[•\-\*]\s*Y/Y:\s*([\d.,\-NA]+)%"
    )
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return _safe_float(m.group(1)), _safe_float(m.group(2))
    return None, None


def _extract_latest_margin(text: str, section_name: str) -> float | None:
    """Extract the 'Latest Quarter' margin for a named section."""
    pattern = (
        rf"{re.escape(section_name)}:\s*\n"
        r"[•\-\*]\s*Latest Quarter:\s*([\d.,\-NA]+)%"
    )
    m = re.search(pattern, text, re.IGNORECASE)
    return _safe_float(m.group(1)) if m else None


def _extract_absolute(text: str, section_name: str) -> dict:
    """Extract absolute numbers (Latest, Previous, SQLY) for a named section."""
    pattern = (
        rf"{re.escape(section_name)}:\s*\n"
        r"[•\-\*]\s*Latest Quarter:\s*([\d.,\-NA]+)\s*\n"
        r"[•\-\*]\s*Previous Quarter:\s*([\d.,\-NA]+)\s*\n"
        r"[•\-\*]\s*Same Quarter Last Year:\s*([\d.,\-NA]+)"
    )
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return {
            "latest": _safe_float(m.group(1)),
            "previous": _safe_float(m.group(2)),
            "sqly": _safe_float(m.group(3)),
        }
    return {"latest": None, "previous": None, "sqly": None}


def _extract_ui_payload(raw_text: str) -> dict | None:
    """Extract machine-readable JSON payload even when model format drifts."""
    m = re.search(
        r"UI_PAYLOAD_START\s*\n\s*(\{.*?\})\s*\n\s*UI_PAYLOAD_END",
        raw_text,
        re.DOTALL,
    )
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: fenced JSON block without UI_PAYLOAD_START/END markers.
    for fence in re.finditer(r"```json\s*(\{[\s\S]*?\})\s*```", raw_text, re.IGNORECASE):
        blob = fence.group(1)
        try:
            payload = json.loads(blob)
            if isinstance(payload, dict) and ("growth" in payload or "margins" in payload):
                return payload
        except json.JSONDecodeError:
            continue

    # Fallback: scan for balanced JSON objects and parse candidates.
    candidates: list[str] = []
    n = len(raw_text)
    i = 0
    while i < n:
        if raw_text[i] != "{":
            i += 1
            continue

        start = i
        depth = 0
        in_str = False
        esc = False
        j = i
        while j < n:
            ch = raw_text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(raw_text[start : j + 1])
                        i = j
                        break
            j += 1
        i += 1

    for blob in candidates:
        if '"growth"' not in blob or '"margins"' not in blob:
            continue
        cleaned = re.sub(r",\s*([}\]])", r"\1", blob)
        try:
            payload = json.loads(cleaned)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue

    return None


def parse_analysis(raw_text: str) -> dict:
    """Parse the AI's plain-text analysis into a structured dict.

    Returns a dict with the same shape as the ``financial_results`` Postgres
    document (minus top-level fields like scrip_code that come from the
    announcement context).
    """
    metrics: dict = {
        "company_name_extracted": "",
        "unit": "",
        "quarter": "",
        "growth": {
            "revenue": {"qoq": None, "yoy": None},
            "ebitda": {"qoq": None, "yoy": None},
            "net_profit": {"qoq": None, "yoy": None},
        },
        "absolute_numbers": {
            "revenue": {"latest": None, "previous": None, "sqly": None},
            "ebitda": {"latest": None, "previous": None, "sqly": None},
            "net_profit": {"latest": None, "previous": None, "sqly": None},
        },
        "margins": {
            "ebitda_margin": None,
            "net_profit_margin": None,
        },
        "signal": "NEUTRAL",
        "confidence": 0,
    }

    try:
        # Company name (strip optional ** markdown)
        m = re.search(
            r"COMPANY NAME:?\s*\**\s*(.+?)\s*\**\s*$", raw_text, re.MULTILINE
        )
        if m:
            metrics["company_name_extracted"] = m.group(1).strip()

        # Unit
        m = re.search(r"Unit:?\s*(.+?)\s*$", raw_text, re.MULTILINE)
        if m:
            metrics["unit"] = m.group(1).strip()

        # Quarter
        m = re.search(r"Quarter:?\s*(.+?)\s*$", raw_text, re.MULTILINE)
        if m:
            metrics["quarter"] = m.group(1).strip()

        # ── Growth section ────────────────────────────────────────────────
        # Narrow to the GROWTH block so "Revenue" in ABSOLUTE NUMBERS
        # doesn't accidentally match.
        growth_block = re.search(
            r"GROWTH:?\s*\n(.+?)(?:ABSOLUTE|MARGINS|$)",
            raw_text,
            re.DOTALL | re.IGNORECASE,
        )
        growth_text = growth_block.group(1) if growth_block else raw_text

        for key, label in [
            ("revenue", "Revenue"),
            ("ebitda", "EBITDA"),
            ("net_profit", "Net Profit"),
        ]:
            qoq, yoy = _extract_qoq_yoy(growth_text, label)
            metrics["growth"][key]["qoq"] = qoq
            metrics["growth"][key]["yoy"] = yoy

        # ── Margins ───────────────────────────────────────────────────────
        metrics["margins"]["ebitda_margin"] = _extract_latest_margin(
            raw_text, "EBITDA Margin"
        )
        metrics["margins"]["net_profit_margin"] = _extract_latest_margin(
            raw_text, "Net Profit Margin"
        )

        # ── Absolute numbers ──────────────────────────────────────────────
        abs_block = re.search(
            r"ABSOLUTE\s*NUMBERS:?\s*\n(.+?)(?:MARGINS|UI_PAYLOAD|$)",
            raw_text,
            re.DOTALL | re.IGNORECASE,
        )
        abs_text = abs_block.group(1) if abs_block else raw_text

        for key, label in [
            ("revenue", "Revenue"),
            ("ebitda", "EBITDA"),
            ("net_profit", "Net Profit"),
        ]:
            metrics["absolute_numbers"][key] = _extract_absolute(abs_text, label)

        # ── Machine-readable UI_PAYLOAD (if AI included it) ───────────────
        ui_payload = _extract_ui_payload(raw_text)
        if ui_payload:
            if not metrics["company_name_extracted"]:
                metrics["company_name_extracted"] = str(ui_payload.get("company_name", "")).strip()
            if not metrics["unit"]:
                metrics["unit"] = str(ui_payload.get("unit", "")).strip()
            if not metrics["quarter"]:
                metrics["quarter"] = str(ui_payload.get("quarter", "")).strip()

            # Prefer AI-generated structured data when available
            for field in ("signal", "confidence"):
                if field in ui_payload:
                    metrics[field] = ui_payload[field]
            # Merge growth/margins/absolute_numbers from JSON if present
            for block in ("growth", "absolute_numbers", "margins"):
                if block in ui_payload and isinstance(ui_payload[block], dict):
                    if isinstance(metrics[block], dict):
                        metrics[block].update(ui_payload[block])

    except Exception as exc:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] ⚠️  Metrics parsing error: {exc}")

    return metrics
