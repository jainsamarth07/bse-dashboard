"""
Market-cap seeder job.

Fetches ALL BSE-listed stocks and populates Postgres.
Run once before starting the monitor, then periodically (e.g., weekly).

Usage
-----
    python -m jobs.fetch_market_cap
or
    python jobs/fetch_market_cap.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

from app.bse import BSE
from app.config import Config
from app.db import close, ping
from app.db.models import FilteredStockStore, StockStore

# All BSE stock groups
_BSE_GROUPS = [
    "A", "B", "E", "F", "FC", "GC", "I", "IF", "IP",
    "M", "MS", "MT", "P", "R", "T", "TS", "W", "X",
    "XD", "XT", "Y", "Z", "ZP", "ZY",
]


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def fetch_all_stocks() -> list[dict]:
    """Fetch & normalise stocks across every BSE group.  Returns a deduplicated list."""
    stocks: list[dict] = []
    seen: set[str] = set()

    with BSE("./") as bse:
        for group in _BSE_GROUPS:
            try:
                print(f"[{_ts()}] 📡 Fetching group '{group}' …")
                raw = bse.listSecurities(group=group)
                count = 0
                for s in raw:
                    code = s.get("SCRIP_CD", "")
                    if code in seen:
                        continue
                    seen.add(code)

                    try:
                        market_cap = float(s.get("Mktcap") or 0)
                    except (ValueError, TypeError):
                        market_cap = 0.0

                    stocks.append(
                        {
                            "scrip_code": code,
                            "scrip_name": s.get("scrip_id", ""),
                            "company_name": s.get("Scrip_Name", ""),
                            "group": s.get("GROUP", group),
                            "industry": s.get("INDUSTRY", ""),
                            "market_cap": market_cap,
                            "face_value": s.get("FACE_VALUE", ""),
                            "isin": s.get("ISIN_NUMBER", ""),
                            "segment": s.get("Segment", ""),
                            "status": s.get("Status", ""),
                        }
                    )
                    count += 1

                print(f"  ✅ Group '{group}': {count} stocks")
                time.sleep(0.5)  # BSE rate-limit courtesy delay

            except Exception as exc:
                print(f"  ⚠️  Error fetching group '{group}': {exc}")

    return stocks


def run() -> None:
    print("=" * 60)
    print("🏛️  BSE Market Cap Fetcher")
    print("=" * 60)

    print(f"\n[{_ts()}] 🔌 Connecting to Postgres …")
    if not ping():
        print("❌ Cannot connect to Postgres!")
        print("   Local:  docker compose up -d")
        print("   Cloud:  check DATABASE_URL env var")
        sys.exit(1)
    print(f"[{_ts()}] ✅ Postgres connected\n")

    print("━" * 60)
    print("📡 STEP 1: Fetching all stocks from BSE API")
    print("━" * 60)
    stocks = fetch_all_stocks()
    print(f"\n📊 Unique stocks fetched: {len(stocks)}")

    print("\n" + "━" * 60)
    print("💾 STEP 2: Storing in 'stocks' table")
    print("━" * 60)
    affected = StockStore.bulk_upsert(stocks)
    total = StockStore.count()
    print(f"✅ Upserted {affected} | Total in DB: {total}")

    print("\n" + "━" * 60)
    min_cap = Config.MIN_MARKET_CAP
    FilteredStockStore.MIN_MARKET_CAP = min_cap
    print(f"🔍 STEP 3: Filtering stocks with market cap > ₹{min_cap:,.0f} Cr")
    print("━" * 60)
    filtered = FilteredStockStore.refresh_from_all_stocks()
    print(f"✅ {filtered} stocks qualify")

    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    print(f"  Total BSE stocks:      {total}")
    print(f"  Above ₹{min_cap:,.0f} Cr:    {filtered}")
    print(f"  Excluded:              {total - filtered}")

    top = FilteredStockStore.get_all()[:10]
    if top:
        print(f"\n🏆 Top 10 by Market Cap:")
        print(f"  {'Symbol':<15} {'Market Cap (₹ Cr)':>18}   Company")
        print(f"  {'─' * 15} {'─' * 18}   {'─' * 30}")
        for s in top:
            print(
                f"  {s['scrip_name']:<15} {s['market_cap']:>18,.2f}   {s['company_name'][:30]}"
            )

    print(f"\n✅ Done!  Start the monitor: python -m jobs.run_monitor")
    close()


if __name__ == "__main__":
    run()
