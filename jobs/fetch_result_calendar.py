"""
Result calendar seeder job.

Fetches BSE result calendar and stores it in Postgres so API/UI can read from DB
without repeatedly calling BSE.

Usage
-----
    python -m jobs.fetch_result_calendar
or
    python jobs/fetch_result_calendar.py
"""

from __future__ import annotations

import sys
from datetime import datetime

from app.bse import BSE
from app.db import close, ping
from app.db.models import ResultCalendarStore


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def run() -> None:
    print("=" * 60)
    print("🏛️  BSE Result Calendar Fetcher")
    print("=" * 60)

    print(f"\n[{_ts()}] 🔌 Connecting to Postgres …")
    if not ping():
        print("❌ Cannot connect to Postgres!")
        print("   Local:  docker compose up -d")
        print("   Cloud:  check DATABASE_URL env var")
        sys.exit(1)
    print(f"[{_ts()}] ✅ Postgres connected\n")

    ResultCalendarStore.ensure_indexes()

    print("━" * 60)
    print("📡 STEP 1: Fetching result calendar from BSE API")
    print("━" * 60)
    with BSE("./") as bse:
        rows = bse.resultCalendar()

    if not isinstance(rows, list):
        print(f"❌ Unexpected BSE payload type: {type(rows).__name__}")
        sys.exit(1)

    print(f"✅ Fetched {len(rows)} calendar row(s)")

    print("\n" + "━" * 60)
    print("💾 STEP 2: Upserting into 'result_calendar' table")
    print("━" * 60)
    saved = ResultCalendarStore.upsert_rows(rows)
    total = ResultCalendarStore.count()
    print(f"✅ Upserted/updated {saved} row(s) | Total in DB: {total}")

    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    print(f"  Result calendar rows in DB: {total}")

    sample = ResultCalendarStore.get_all(limit=3)
    if sample:
        print("\n🔎 Sample rows:")
        for row in sample:
            print(
                f"  {row.get('meeting_date', ''):<12} "
                f"{row.get('short_name', ''):<12} "
                f"{row.get('Long_Name', '')[:35]}"
            )

    print("\n✅ Done! Calendar API now serves from Postgres cache.")
    close()


if __name__ == "__main__":
    run()
