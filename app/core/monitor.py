"""
Main BSE Result Monitor.

Orchestrates the full pipeline:
  BSE API poll → filter by market cap → download PDF → AI analysis
  → Postgres store → Telegram notify → deduplication

Entry point: run()
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timezone, timedelta

from app.bse import BSE
from app.config import Config
from app.core.parser import parse_analysis
from app.db import close, ping
from app.db.models import (
    FilteredStockStore,
    FinancialResultStore,
    MonitorRuleStore,
    MonitorStatusStore,
    NotificationStore,
    ResultCalendarStore,
    SeenAnnouncementStore,
)
from app.services.ai import analyze_pdf
from app.services.pdf import download_pdf
from app.services.telegram import send_analysis, send_message


# Indian Standard Time = UTC+5:30
_IST = timezone(timedelta(hours=5, minutes=30))


def _ts() -> str:
    """Current time as HH:MM:SS IST."""
    return datetime.now(_IST).strftime("%H:%M:%S IST")


# ── BSE announcement fetcher ──────────────────────────────────────────────────

def _load_rules() -> list[dict]:
    """Load enabled monitor rules from Postgres."""
    try:
        return MonitorRuleStore.get_enabled()
    except Exception as exc:
        print(f"[{_ts()}] ⚠️  Failed to load monitor rules: {exc}")
        return []


def _check_rules(rules: list[dict], stock_info: dict) -> bool:
    """Return True if the stock passes ALL enabled rules.

    If there are no rules, everything passes.
    Supported fields: market_cap, group, industry, scrip_name.
    Operators: gt, lt, equals, contains, in, not_in (match API-stored values).
    """
    if not rules:
        return True

    for rule in rules:
        field = rule.get("field", "")
        op = rule.get("operator", "")
        value = rule.get("value")

        actual = stock_info.get(field)
        if actual is None:
            continue  # field missing — skip rule

        try:
            if op in ("gt", "lt"):
                actual_n = float(actual)
                value_n = float(value)
                if op == "gt" and not (actual_n > value_n):
                    return False
                if op == "lt" and not (actual_n < value_n):
                    return False
            elif op == "equals":
                if str(actual).lower() != str(value).lower():
                    return False
            elif op == "contains":
                if str(value).lower() not in str(actual).lower():
                    return False
            elif op == "in":
                vals = [v.strip().lower() for v in str(value).split(",")]
                if str(actual).lower() not in vals:
                    return False
            elif op == "not_in":
                vals = [v.strip().lower() for v in str(value).split(",")]
                if str(actual).lower() in vals:
                    return False
        except (ValueError, TypeError):
            continue  # bad data — skip rule

    return True


def _is_board_outcome(item: dict) -> bool:
    """True when announcement is a Board Meeting Outcome (not intimation)."""
    newssub = str(item.get("NEWSSUB", "")).lower()
    return "outcome" in newssub and "intimation" not in newssub


def _has_result_keywords(item: dict) -> bool:
    """Keyword fallback when calendar cache is stale/unavailable."""
    text = " ".join([str(item.get("NEWSSUB", "")), str(item.get("HEADLINE", ""))]).lower()
    keywords = (
        "result",
        "financial result",
        "financial results",
        "quarter",
        "q1",
        "q2",
        "q3",
        "q4",
        "audited",
        "unaudited",
    )
    return any(k in text for k in keywords)


def _refresh_result_calendar_cache() -> int:
    """Refresh result calendar cache from BSE and return changed-row count."""
    with BSE("./") as bse:
        rows = bse.resultCalendar()
    if not isinstance(rows, list):
        raise RuntimeError(f"Unexpected resultCalendar payload type: {type(rows).__name__}")
    return ResultCalendarStore.upsert_rows(rows)


def _fetch_result_announcements(calendar_codes_for_today: set[str]) -> list[dict]:
    """Fetch all pages of Result + Board Meeting announcements for today."""
    categories = ("Result", "Board Meeting", "Board Meet")
    announcements: list[dict] = []
    seen_keys: set[tuple[str, str, str]] = set()
    max_attempts = 3

    with BSE("./") as bse:
        for category in categories:
            page = 1
            total = 1

            while True:
                res = None
                last_exc: Exception | None = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        res = bse.announcements(page_no=page, category=category)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        print(
                            f"[{_ts()}] ❌ BSE fetch error ({category}, page {page}, attempt {attempt}/{max_attempts}): {exc}"
                        )
                        # Small backoff to ride out transient DNS/network blips
                        time.sleep(1.0 * attempt)

                if last_exc is not None:
                    # Page-1 failure means we don't know ROWCNT; bail out for this category
                    # and continue with remaining categories.
                    if page == 1:
                        print(
                            f"[{_ts()}] ⚠️  Skipping category {category} for this poll cycle (page 1 unavailable)"
                        )
                        break
                    # For deeper pages, continue pagination instead of dropping the entire
                    # category so a single timeout doesn't hide all later announcements.
                    print(
                        f"[{_ts()}] ⚠️  Skipping failed page {page} in {category}; continuing pagination"
                    )
                    page += 1
                    if page > total:
                        break
                    continue

                if not res or "Table" not in res:
                    break

                if page == 1 and "Table1" in res:
                    total = res["Table1"][0].get("ROWCNT", len(res["Table"]))

                for item in res["Table"]:
                    if category != "Result":
                        if not _is_board_outcome(item):
                            continue

                        scrip_cd = str(item.get("SCRIP_CD", ""))
                        # Primary path: board outcome is accepted when the stock appears in
                        # today's result calendar. Fallback path: keyword match.
                        if scrip_cd not in calendar_codes_for_today and not _has_result_keywords(item):
                            continue

                    key = (
                        str(item.get("SCRIP_CD", "")),
                        str(item.get("NEWS_DT", "")),
                        str(item.get("NEWSSUB", "")),
                    )
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    announcements.append(item)

                page += 1
                if page > total:
                    break

    return announcements


def _fetch_announcements_for_scrip(
    bse: BSE,
    scrip_code: str,
    calendar_codes_for_today: set[str],
) -> list[dict]:
    """Fetch today's Result/Board announcements for a specific scrip code."""
    categories = ("Result", "Board Meeting", "Board Meet")
    announcements: list[dict] = []
    seen_keys: set[tuple[str, str, str]] = set()
    max_attempts = 3
    today = datetime.now()

    for category in categories:
        page = 1
        total = 1

        while True:
            res = None
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    res = bse.announcements(
                        page_no=page,
                        from_date=today,
                        to_date=today,
                        scripcode=scrip_code,
                        category=category,
                    )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    print(
                        f"[{_ts()}] ❌ Backfill fetch error ({scrip_code}, {category}, page {page}, attempt {attempt}/{max_attempts}): {exc}"
                    )
                    time.sleep(0.7 * attempt)

            if last_exc is not None:
                if page == 1:
                    break
                page += 1
                if page > total:
                    break
                continue

            if not res or "Table" not in res:
                break

            if page == 1 and "Table1" in res:
                total = res["Table1"][0].get("ROWCNT", len(res["Table"]))

            for item in res["Table"]:
                if category != "Result":
                    if not _is_board_outcome(item):
                        continue
                    if scrip_code not in calendar_codes_for_today and not _has_result_keywords(item):
                        continue

                key = (
                    str(item.get("SCRIP_CD", "")),
                    str(item.get("NEWS_DT", "")),
                    str(item.get("NEWSSUB", "")),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                announcements.append(item)

            page += 1
            if page > total:
                break

    return announcements


def _run_calendar_backfill(
    calendar_codes_for_today: set[str],
    eligible_codes: set[str],
    stocks_by_code: dict[str, dict],
    rules: list[dict],
    max_scrips: int = 3,
    max_announcements: int = 2,
    max_seconds: float = 20.0,
) -> int:
    """Backfill missed announcements by querying BSE directly per missing scrip."""
    if not calendar_codes_for_today:
        return 0

    today = date.today()
    candidates = [
        code
        for code in sorted(calendar_codes_for_today)
        if code in eligible_codes and not FinancialResultStore.has_scrip_on_date(code, today)
    ]

    if not candidates:
        return 0

    if len(candidates) > max_scrips:
        print(
            f"[{_ts()}] 🔁 Backfill candidates: {len(candidates)} (processing up to {max_scrips} scrips this cycle; remaining deferred)"
        )

    processed = 0
    cycle_start = time.monotonic()

    def _budget_exhausted() -> bool:
        return processed >= max_announcements or (time.monotonic() - cycle_start) >= max_seconds

    with BSE("./") as bse:
        for scrip_code in candidates[:max_scrips]:
            if _budget_exhausted():
                break

            stock_info = stocks_by_code.get(scrip_code, {})

            if not _check_rules(rules, stock_info):
                continue

            announcements = _fetch_announcements_for_scrip(
                bse,
                scrip_code,
                calendar_codes_for_today,
            )
            if not announcements:
                continue

            print(
                f"[{_ts()}] 🔎 Backfill found {len(announcements)} announcement(s) for {stock_info.get('scrip_name', scrip_code)}"
            )

            for ann in announcements:
                if _budget_exhausted():
                    break

                scrip_cd = str(ann.get("SCRIP_CD", ""))
                news_dt = str(ann.get("NEWS_DT", ""))
                news_sub = str(ann.get("NEWSSUB", ""))

                if SeenAnnouncementStore.is_seen(scrip_cd, news_dt, news_sub):
                    continue

                done = _process_announcement(ann, stock_info)
                if done:
                    SeenAnnouncementStore.mark_seen(scrip_cd, news_dt, news_sub)
                    processed += 1

    if candidates and processed < len(candidates):
        remaining = max(0, len(candidates) - max_scrips)
        if remaining > 0:
            print(f"[{_ts()}] ⏭️  Deferred {remaining} backfill candidate(s) to later cycles")

    return processed


# ── Single-announcement processor ────────────────────────────────────────────

def _process_announcement(
    announcement: dict,
    stock_info: dict,
) -> bool:
    """Download PDF, run AI, save to DB, send Telegram message."""
    scrip = (
        announcement.get("SLONGNAME")
        or announcement.get("SCRIPNAME")
        or stock_info.get("scrip_name")
        or stock_info.get("company_name")
        or "N/A"
    )
    scrip_code = str(announcement.get("SCRIP_CD") or "")
    subject = announcement.get("NEWSSUB") or "No Subject"
    date = announcement.get("NEWS_DT") or datetime.now().strftime("%d/%m/%Y")
    attach = announcement.get("ATTACHMENTNAME")
    market_cap = stock_info.get("market_cap", 0.0)

    print(f"  ✅ {scrip} | ₹{market_cap:,.0f} Cr | {subject}")

    if not attach:
        # No PDF — send a basic notification and return
        send_message(
            f"📢 <b>New BSE Result</b>\n"
            f"<b>Company:</b> {scrip} (₹{market_cap:,.0f} Cr)\n"
            f"<b>Subject:</b> {subject}\n"
            f"<b>Date:</b> {date}\n"
            f"<i>No attachment</i>"
        )
        return True

    pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}"
    safe_scrip = scrip.replace("/", "_").replace(" ", "_")[:20]
    safe_date = date.replace("/", "-")
    pdf_path = download_pdf(pdf_url, f"{safe_scrip}_{safe_date}.pdf")

    if not pdf_path:
        # Download failures are often transient; allow retries in future polls.
        return False

    try:
        analysis, model, extracted_via = analyze_pdf(pdf_path)

        if analysis.startswith("Error:"):
            lower = analysis.lower()
            retryable = any(
                token in lower
                for token in ("429", "quota", "rate", "timeout", "temporar", "retry")
            )
            if retryable:
                print(f"[{_ts()}] ⏳ Deferring announcement — retryable AI failure: {analysis}")
                return False
            print(f"[{_ts()}] ⚠️  Skipping save/send — non-retryable AI error: {analysis}")
            return True

        # Parse metrics
        parsed = parse_analysis(analysis)

        # Persist to Postgres
        result_id = FinancialResultStore.save_result(
            {
                "scrip_code": scrip_code,
                "scrip_name": scrip,
                "company_name": stock_info.get("company_name", scrip),
                "market_cap": market_cap,
                "news_date": date,
                "subject": subject,
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
            }
        )
        print(f"[{_ts()}] 💾 Saved to Postgres (model: {model})")

        # Push real-time notification for WebSocket clients
        try:
            NotificationStore.push(
                "new_result",
                {
                    "id": result_id,
                    "scrip_code": scrip_code,
                    "scrip_name": scrip,
                    "market_cap": market_cap,
                    "signal": parsed.get("signal", "NEUTRAL"),
                    "quarter": parsed.get("quarter", ""),
                },
            )
        except Exception:
            pass  # non-critical

        # Update monitor status counters
        try:
            MonitorStatusStore.increment_results()
        except Exception:
            pass

        # Send to Telegram
        send_analysis(scrip, pdf_url, analysis, scrip_code, market_cap)
        return True

    finally:
        # Always clean up temp PDF
        try:
            os.remove(pdf_path)
        except OSError:
            pass


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(interval: int = Config.POLL_INTERVAL) -> None:
    """Start the BSE Result Monitor.  Runs until interrupted (Ctrl-C)."""

    print("=" * 60)
    print("🏛️  BSE Result Monitor (Groq + Ollama + Postgres)")
    print("=" * 60)

    # ── Guard: Postgres must be reachable ─────────────────────────────────────
    print(f"[{_ts()}] 🔌 Connecting to Postgres …")
    if not ping():
        print("❌ Cannot connect to Postgres!")
        print("   Local:  docker compose up -d")
        print("   Cloud:  check DATABASE_URL env var")
        sys.exit(1)
    print(f"[{_ts()}] ✅ Postgres connected")

    # ── Load eligible scrip codes into memory for O(1) lookup ────────────────
    # Rebuild filtered snapshot at startup so MIN_MARKET_CAP env changes
    # are applied immediately without needing a separate fetch job run.
    FilteredStockStore.MIN_MARKET_CAP = Config.MIN_MARKET_CAP
    try:
        rebuilt = FilteredStockStore.refresh_from_all_stocks()
        print(f"[{_ts()}] 🔄 Rebuilt filtered stocks snapshot ({rebuilt} rows)")
    except Exception as exc:
        print(f"[{_ts()}] ⚠️  Could not rebuild filtered stocks snapshot: {exc}")

    eligible_codes = FilteredStockStore.get_scrip_codes()
    stocks_by_code = {s["scrip_code"]: s for s in FilteredStockStore.get_all()}

    print(
        f"[{_ts()}] ✅ Loaded {len(eligible_codes)} stocks "
        f"(market cap > ₹{Config.MIN_MARKET_CAP:,.0f} Cr)"
    )

    if not eligible_codes:
        print("⚠️  No eligible stocks — run the market-cap fetcher first:")
        print("   python -m jobs.fetch_market_cap")
        print(f"[{_ts()}] ⏳ Waiting for stock data — will retry every 60s …")
        while not eligible_codes:
            time.sleep(60)
            eligible_codes = FilteredStockStore.get_scrip_codes()
            stocks_by_code = {s["scrip_code"]: s for s in FilteredStockStore.get_all()}
            if eligible_codes:
                print(f"[{_ts()}] ✅ Stock data loaded ({len(eligible_codes)} stocks), resuming …")

    # ── Load monitor rules ────────────────────────────────────────────────────
    rules = _load_rules()
    if rules:
        print(f"[{_ts()}] 📋 Loaded {len(rules)} monitor rule(s)")
    else:
        print(f"[{_ts()}] 📋 No monitor rules — processing all eligible stocks")

    # ── Ensure notification indexes ───────────────────────────────────────────
    try:
        NotificationStore.ensure_indexes()
    except Exception:
        pass

    # ── Initialize monitor status ─────────────────────────────────────────────
    try:
        MonitorStatusStore.reset_daily()
    except Exception:
        pass

    # ── First-run seeding ─────────────────────────────────────────────────────
    ResultCalendarStore.ensure_indexes()
    calendar_codes_for_today: set[str] = set()
    last_calendar_refresh = datetime.min
    last_backfill = datetime.min

    try:
        changed = _refresh_result_calendar_cache()
        calendar_codes_for_today = ResultCalendarStore.get_scrip_codes_for_date(date.today())
        last_calendar_refresh = datetime.now()
        print(
            f"[{_ts()}] 📅 Result calendar refreshed "
            f"({changed} changed rows, {len(calendar_codes_for_today)} companies today)"
        )
    except Exception as exc:
        calendar_codes_for_today = ResultCalendarStore.get_scrip_codes_for_date(date.today())
        print(
            f"[{_ts()}] ⚠️  Calendar refresh failed ({exc}) — "
            f"using cached DB entries ({len(calendar_codes_for_today)} companies today)"
        )

    # On a fresh DB, mark ALL current announcements as "seen" so we only
    # analyse genuinely NEW ones from this point forward.
    if SeenAnnouncementStore.count() == 0:
        print(f"[{_ts()}] 🌱 First run — seeding existing announcements …")
        seed = _fetch_result_announcements(calendar_codes_for_today)
        for a in seed:
            SeenAnnouncementStore.mark_seen(
                str(a.get("SCRIP_CD", "")),
                str(a.get("NEWS_DT", "")),
                str(a.get("NEWSSUB", "")),
            )
        print(
            f"[{_ts()}] ✅ Seeded {len(seed)} announcements as 'seen'.\n"
            f"           Only NEW announcements will be analysed from now on."
        )

    send_message(
        "🤖 <b>BSE Result Monitor Started</b>\n"
        f"Primary: Llama 3.3 70B • Fallback: Gemini ({Config.GEMINI_MODEL})\n"
        f"Tracking {len(eligible_codes)} stocks (>₹{Config.MIN_MARKET_CAP:,.0f} Cr)\n"
        f"Polling every {interval}s …"
    )

    print(f"\n🔍 Polling every {interval}s — press Ctrl-C to stop.\n")

    # ── Main polling loop ─────────────────────────────────────────────────────
    while True:
        try:
            if (datetime.now() - last_calendar_refresh).total_seconds() >= 900:
                try:
                    changed = _refresh_result_calendar_cache()
                    calendar_codes_for_today = ResultCalendarStore.get_scrip_codes_for_date(date.today())
                    last_calendar_refresh = datetime.now()
                    print(
                        f"[{_ts()}] 📅 Calendar refresh complete "
                        f"({changed} changed rows, {len(calendar_codes_for_today)} companies today)"
                    )
                except Exception as exc:
                    print(f"[{_ts()}] ⚠️  Calendar refresh skipped: {exc}")

            # Check if rules need reloading (triggered by API)
            try:
                status = MonitorStatusStore.get_status()
                if status and status.get("reload_rules"):
                    rules = _load_rules()
                    MonitorStatusStore.clear_reload_flag()
                    print(f"[{_ts()}] 🔄 Reloaded {len(rules)} monitor rule(s)")
            except Exception:
                pass

            all_ann = _fetch_result_announcements(calendar_codes_for_today)

            # Update poll timestamp
            try:
                MonitorStatusStore.update_poll(len(all_ann))
            except Exception:
                pass

            new_items: list[tuple[dict, dict]] = []

            for a in all_ann:
                scrip_cd = str(a.get("SCRIP_CD", ""))
                news_dt = str(a.get("NEWS_DT", ""))
                news_sub = str(a.get("NEWSSUB", ""))

                if SeenAnnouncementStore.is_seen(scrip_cd, news_dt, news_sub):
                    continue

                if scrip_cd not in eligible_codes:
                    SeenAnnouncementStore.mark_seen(scrip_cd, news_dt, news_sub)
                    continue  # below market-cap threshold — skip silently

                stock_info = stocks_by_code.get(scrip_cd, {})

                # Apply monitor rules
                if not _check_rules(rules, stock_info):
                    print(
                        f"[{_ts()}] ⏭️  Skipped {stock_info.get('scrip_name', scrip_cd)}"
                        f" — filtered by monitor rules"
                    )
                    SeenAnnouncementStore.mark_seen(scrip_cd, news_dt, news_sub)
                    continue

                new_items.append((a, stock_info))

            if new_items:
                print(f"\n[{_ts()}] 🆕 {len(new_items)} new announcement(s):")
                for announcement, stock_info in new_items:
                    done = _process_announcement(announcement, stock_info)
                    if done:
                        SeenAnnouncementStore.mark_seen(
                            str(announcement.get("SCRIP_CD", "")),
                            str(announcement.get("NEWS_DT", "")),
                            str(announcement.get("NEWSSUB", "")),
                        )

            backfilled = 0
            # Keep backfill low-priority so live announcements are never delayed.
            if not new_items and (datetime.now() - last_backfill).total_seconds() >= 600:
                try:
                    backfilled = _run_calendar_backfill(
                        calendar_codes_for_today,
                        eligible_codes,
                        stocks_by_code,
                        rules,
                    )
                    last_backfill = datetime.now()
                    if backfilled:
                        print(f"[{_ts()}] ✅ Backfill processed {backfilled} missed announcement(s)")
                except Exception as exc:
                    print(f"[{_ts()}] ⚠️  Backfill skipped: {exc}")

            if not new_items and backfilled == 0:
                print(
                    f"[{_ts()}] ℹ️  No new Result/Board Meeting announcements "
                    f"({len(calendar_codes_for_today)} companies in today's calendar)."
                )

        except KeyboardInterrupt:
            print(f"\n[{_ts()}] 🛑 Shutting down …")
            close()
            sys.exit(0)
        except Exception as exc:
            print(f"[{_ts()}] ❌ Monitor error: {exc}")

        time.sleep(interval)
