"""
Centralized configuration — all values loaded from environment variables.

Copy .env.example → .env and fill in the values before running.

Usage:
    from app.config import Config
    print(Config.BOT_TOKEN)
"""

from __future__ import annotations

import os
import sys

# Load .env automatically when running locally — no-op when env vars are
# already set (e.g. injected by Railway / Render / Docker).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed (acceptable in minimal envs)


def _require(key: str) -> str:
    """Return env var value or exit with a helpful message."""
    val = os.getenv(key, "").strip()
    if not val:
        print(f"❌  Missing required environment variable: {key}")
        print(f"   Add it to your .env file or export it before running.")
        sys.exit(1)
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


class Config:
    """All application settings, sourced from environment variables."""

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    # Read directly via os.getenv in app.db / api.deps (same DATABASE_URL for
    # both the sync and async connection pools) — not duplicated here.

    # ── Telegram ─────────────────────────────────────────────────────────────
    BOT_TOKEN: str = _optional("BOT_TOKEN")
    CHAT_ID: str = _optional("CHAT_ID")

    # ── AI providers ─────────────────────────────────────────────────────────
    GROQ_API_KEY: str = _optional("GROQ_API_KEY")
    # Optional comma-separated list of keys for round-robin rotation.
    # Example: GROQ_API_KEYS=key1,key2,key3
    GROQ_API_KEYS_RAW: str = _optional("GROQ_API_KEYS")
    GROQ_MODEL: str = _optional("GROQ_MODEL", "llama-3.3-70b-versatile")

    GEMINI_API_KEY: str = _optional("GEMINI_API_KEY")
    GEMINI_MODEL: str = _optional("GEMINI_MODEL", "gemini-2.5-flash")

    OLLAMA_BASE_URL: str = _optional("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = _optional("OLLAMA_MODEL", "gemma4:e4b")
    OLLAMA_TIMEOUT: int = int(_optional("OLLAMA_TIMEOUT", "120"))

    # ── Tunable parameters ───────────────────────────────────────────────────
    # How often to poll BSE for new announcements (seconds)
    POLL_INTERVAL: int = int(_optional("POLL_INTERVAL", "15"))

    # Minimum market cap (₹ Crores) to include in analysis
    MIN_MARKET_CAP: float = float(_optional("MIN_MARKET_CAP", "500"))

    # Max PDF pages to send to AI (saves tokens)
    MAX_RESULT_PAGES: int = int(_optional("MAX_RESULT_PAGES", "3"))

    @classmethod
    def get_groq_api_keys(cls) -> list[str]:
        """Return all Groq keys, preferring GROQ_API_KEYS when provided."""
        keys: list[str] = []

        if cls.GROQ_API_KEYS_RAW:
            keys.extend([k.strip() for k in cls.GROQ_API_KEYS_RAW.split(",") if k.strip()])

        if cls.GROQ_API_KEY:
            keys.append(cls.GROQ_API_KEY)

        # De-duplicate while preserving order.
        deduped: list[str] = []
        seen: set[str] = set()
        for key in keys:
            if key not in seen:
                deduped.append(key)
                seen.add(key)

        return deduped
