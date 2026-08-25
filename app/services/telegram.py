"""
Telegram notification service.

Exports
-------
send_message(text)
send_analysis(company, pdf_link, analysis, scrip_code, market_cap)
broker_links(symbol, scrip_code) → str
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import requests

from app.config import Config


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Low-level sender ──────────────────────────────────────────────────────────

def send_message(text: str) -> None:
    """Send a plain HTML message to the configured Telegram chat."""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        requests.post(
            url,
            json={"chat_id": Config.CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as exc:
        print(f"[{_ts()}] ⚠️  Telegram send error: {exc}")


# ── Broker deep-link builder ──────────────────────────────────────────────────

def broker_links(symbol: str, scrip_code: str = "") -> str:  # noqa: ARG001
    """Return a formatted HTML block with Groww / Kite / Dhan buy-sell links."""
    sym = symbol.strip().replace(" ", "").upper()

    kite_buy = (
        f"https://kite.zerodha.com/connect/basket"
        f"?tradingsymbol={quote(sym)}&exchange=BSE&transaction_type=BUY"
        f"&quantity=1&order_type=LIMIT"
    )
    kite_sell = kite_buy.replace("transaction_type=BUY", "transaction_type=SELL")
    dhan_buy = (
        f"https://web.dhan.co/orders"
        f"?symbol={quote(sym)}&exchange=BSE&action=BUY&qty=1&ordertype=LIMIT"
    )
    dhan_sell = dhan_buy.replace("action=BUY", "action=SELL")
    groww = f"https://groww.in/stocks/search?query={quote(sym)}"

    return (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Quick Trade ({sym})</b>\n\n"
        f"<b>Groww:</b>\n"
        f"  🟢 <a href='{groww}'>Open in Groww</a>\n\n"
        f"<b>Kite (Zerodha):</b>\n"
        f"  📈 <a href='{kite_buy}'>Buy on Kite</a>\n"
        f"  📉 <a href='{kite_sell}'>Sell on Kite</a>\n\n"
        f"<b>Dhan:</b>\n"
        f"  📈 <a href='{dhan_buy}'>Buy on Dhan</a>\n"
        f"  📉 <a href='{dhan_sell}'>Sell on Dhan</a>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )


# ── High-level sender ─────────────────────────────────────────────────────────

def send_analysis(
    company: str,
    pdf_link: str,
    analysis: str,
    scrip_code: str = "",
    market_cap: float = 0.0,
) -> None:
    """Send a full analysis report to Telegram, chunking if necessary."""
    try:
        trade_links = broker_links(company, scrip_code) if scrip_code else ""
        MAX_LEN = 4_000

        mcap_str = f"\n<b>Market Cap:</b> ₹{market_cap:,.0f} Cr" if market_cap else ""
        header = (
            f"📊 <b>Financial Analysis Report</b>\n"
            f"<b>Company:</b> {company}{mcap_str}\n"
            f"<b>PDF:</b> {pdf_link}\n\n"
        )

        if len(header) + len(analysis) + len(trade_links) <= MAX_LEN:
            send_message(header + analysis + trade_links)
        else:
            send_message(header)
            chunks = [analysis[i : i + MAX_LEN] for i in range(0, len(analysis), MAX_LEN)]
            for idx, chunk in enumerate(chunks, 1):
                if idx > 1:
                    chunk = f"<b>... (Part {idx})</b>\n" + chunk
                send_message(chunk)
            if trade_links:
                send_message(trade_links)
    except Exception as exc:
        print(f"[{_ts()}] ❌ Telegram send error: {exc}")
