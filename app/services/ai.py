"""
AI analysis service — Groq (primary) with Gemini as fallback.

Exports
-------
analyze_pdf(pdf_path) → tuple[str, str, str]
    Returns (analysis_text, model_name_used, extracted_via).
    analysis_text starts with "Error:" on failure.
"""

from __future__ import annotations

import re
import time
from threading import Lock
from datetime import datetime

import fitz  # PyMuPDF
import requests
from groq import Groq

from app.config import Config
from app.core.prompts import AI_SYSTEM_MESSAGE, FINANCIAL_ANALYSIS_PROMPT
from app.services.pdf import (
    detect_image_pages,
    extract_text,
    render_pages_as_images,
    _score_page,
)

# ── Lazy-initialised clients (created on first call) ─────────────────────────

_groq_clients: dict[str, Groq] = {}
_groq_key_index: int = 0
_groq_key_lock = Lock()
_gemini_model = None


def _groq_for_key(api_key: str) -> Groq:
    client = _groq_clients.get(api_key)
    if client is None:
        client = Groq(api_key=api_key)
        _groq_clients[api_key] = client
    return client


def _next_groq_key() -> tuple[str | None, int, int]:
    """Round-robin select next Groq key.

    Returns (api_key_or_none, selected_index_1_based, total_keys).
    """
    global _groq_key_index
    keys = Config.get_groq_api_keys()
    total = len(keys)
    if total == 0:
        return None, 0, 0

    with _groq_key_lock:
        idx = _groq_key_index % total
        _groq_key_index += 1

    return keys[idx], idx + 1, total


def _gemini():
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai

        genai.configure(api_key=Config.GEMINI_API_KEY)
        _gemini_model = genai.GenerativeModel(Config.GEMINI_MODEL)
    return _gemini_model


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _sanitize_model_output(text: str) -> str:
    """Normalize model output so downstream parser can consume it reliably.

    Gemma/Ollama occasionally wraps answers in markdown fences, emits hidden
    reasoning tags, or omits the UI_PAYLOAD_END sentinel.
    """
    cleaned = (text or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return ""

    # Remove common reasoning wrappers used by some open models.
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)

    # Remove leading/trailing markdown fences if the whole payload is fenced.
    cleaned = re.sub(r"^```(?:json|text|markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # If model produced START but forgot END, add it so JSON extractor can work.
    if "UI_PAYLOAD_START" in cleaned and "UI_PAYLOAD_END" not in cleaned:
        cleaned = f"{cleaned}\nUI_PAYLOAD_END"

    return cleaned.strip()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _call_groq(prompt_text: str) -> str | None:
    """Call Groq API; return text or None on error."""
    api_key, selected_idx, total_keys = _next_groq_key()
    if not api_key:
        print(f"[{_ts()}] ❌ Groq API key missing — trying Gemini …")
        return None

    try:
        print(
            f"[{_ts()}] 🤖 Sending to Groq ({Config.GROQ_MODEL}) "
            f"[key {selected_idx}/{total_keys}] …"
        )
        time.sleep(5)  # rate-limit buffer
        completion = _groq_for_key(api_key).chat.completions.create(
            messages=[
                {"role": "system", "content": AI_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt_text},
            ],
            model=Config.GROQ_MODEL,
            temperature=0.1,
            max_tokens=8_192,
        )
        choice = completion.choices[0]
        result = choice.message.content
        if result:
            print(f"[{_ts()}] ✅ Analysis complete (Groq)")
        else:
            print(
                f"[{_ts()}] ⚠️  Groq returned an empty response "
                f"(finish_reason={choice.finish_reason}) — trying Gemini …"
            )
        return result
    except Exception as exc:
        err = str(exc).lower()
        if "429" in str(exc) or "rate" in err or "limit" in err:
            print(f"[{_ts()}] ⚠️  Groq rate-limited — switching to Gemini …")
        else:
            print(f"[{_ts()}] ❌ Groq error: {exc} — trying Gemini …")
        return None


def _call_ollama_text(prompt_text: str) -> str | None:
    """Call local Ollama API; return text or None on error."""
    try:
        print(
            f"[{_ts()}] 🤖 Sending to Ollama "
            f"({Config.OLLAMA_MODEL} @ {Config.OLLAMA_BASE_URL}) …"
        )
        full_prompt = f"{AI_SYSTEM_MESSAGE}\n\n{prompt_text}"
        resp = requests.post(
            f"{Config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": Config.OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                },
            },
            timeout=Config.OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        result = _sanitize_model_output(data.get("response") or "")
        if result:
            print(f"[{_ts()}] ✅ Analysis complete (Ollama)")
            return result
        print(f"[{_ts()}] ❌ Ollama returned empty response")
        return None
    except Exception as exc:
        print(f"[{_ts()}] ❌ Ollama error: {exc}")
        return None


def _call_gemini_text(prompt_text: str) -> str | None:
    """Call Gemini text API; return text or None on error."""
    try:
        print(f"[{_ts()}] 🤖 Sending to Gemini text ({Config.GEMINI_MODEL}) …")
        full_prompt = f"{AI_SYSTEM_MESSAGE}\n\n{prompt_text}"
        resp = _gemini().generate_content(full_prompt)
        if resp and resp.text:
            print(f"[{_ts()}] ✅ Analysis complete (Gemini text)")
        return resp.text if resp else None
    except Exception as exc:
        print(f"[{_ts()}] ❌ Gemini text error: {exc}")
        return None


def _call_gemini_vision(
    pdf_path: str,
    pdf_text: str,
    page_numbers: list[int],
    dpi: int = 200,
) -> str | None:
    """Call Gemini Vision with rendered PDF images + any extractable text."""
    try:
        images = render_pages_as_images(pdf_path, page_numbers, dpi=dpi)
        if not images:
            return None

        print(
            f"[{_ts()}] 🤖 Sending {len(images)} image(s) + text "
            f"to Gemini Vision ({Config.GEMINI_MODEL}, {dpi} DPI) …"
        )
        parts = [FINANCIAL_ANALYSIS_PROMPT]
        if pdf_text:
            parts.append(f"\n--- EXTRACTABLE TEXT (may be partial) ---\n{pdf_text}")
        parts.extend(images)

        resp = _gemini().generate_content(parts)
        if resp and resp.text:
            print(f"[{_ts()}] ✅ Analysis complete (Gemini Vision)")
        return resp.text if resp else None
    except Exception as exc:
        print(f"[{_ts()}] ❌ Gemini Vision error: {exc}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_pdf(pdf_path: str) -> tuple[str, str, str]:
    """Analyse a BSE result PDF and return (analysis_text, model_name, extracted_via).

    Decision tree
    -------------
    1. Text-based PDF → Groq first (fast + cheap), then Gemini fallback.
    2. Ollama/Gemma fallback is disabled.

    Returns ("Error: …", "", "") on total failure.
    """
    pdf_text = extract_text(pdf_path, max_result_pages=Config.MAX_RESULT_PAGES)
    image_pages = detect_image_pages(pdf_path)

    if not pdf_text and not image_pages:
        # Gemini vision fallback is disabled for now.
        # If needed later, re-enable _call_gemini_vision here.
        return "Error: Could not extract any text from PDF", "", ""

    # ── Path A: scanned / image-based table → Gemini Vision ──────────────────
    # Skip Vision if the text extraction already yielded substantial content —
    # image_pages detection can produce false positives (e.g. auditor-report
    # pages that have low char count but aren't result tables).
    if image_pages and len(pdf_text) >= 500:
        print(
            f"[{_ts()}] ℹ️  Image page(s) detected but pdf_text is substantial "
            f"({len(pdf_text)} chars) — using text path instead."
        )
        image_pages = []

    if image_pages:
        # Gemini vision fallback is disabled for now.
        # If needed later, re-enable _call_gemini_vision for scanned PDFs.
        if not pdf_text:
            return "Error: Scan/image-based PDF requires Vision fallback (currently disabled)", "", ""

    # ── Path B: text-based PDF → Groq first, then Gemini text ────────────────
    prompt = f"{FINANCIAL_ANALYSIS_PROMPT}\n\n--- EXTRACTED PDF TEXT ---\n{pdf_text}"

    result = _call_groq(prompt)
    if result:
        return result, Config.GROQ_MODEL, "text"

    result = _call_gemini_text(prompt)
    if result:
        return result, Config.GEMINI_MODEL, "text_fallback"

    return "Error: All AI providers failed", "", ""
