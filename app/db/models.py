"""
PostgreSQL CRUD models for BSE India data.

Each class wraps one table and exposes class-methods only (stateless — no
need to instantiate). Method names/signatures/return shapes mirror the old
Mongo-backed version exactly so callers (app.core.monitor, jobs/*,
api/routes/*) did not need to change.

Tables
------
StockStore              -> stocks            (was all_stocks + filtered_stocks)
FilteredStockStore       -> stocks WHERE market_cap > threshold (no longer a
                            separate table — always a derived view of stocks)
ResultCalendarStore     -> result_calendar
SeenAnnouncementStore   -> seen_announcements
FinancialResultStore    -> financial_results
MonitorRuleStore        -> monitor_rules
NotificationStore       -> notifications
MonitorStatusStore      -> monitor_status
EstimateStore           -> estimates
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from psycopg2.extras import Json

from app.db import get_conn, get_cursor

_SORT_WHITELIST = {
    "analyzed_at", "market_cap", "scrip_code", "scrip_name",
    "company_name", "signal", "confidence",
}


def _set_clause(fields: dict, start_index: int = 1) -> tuple[str, list]:
    """Build a parameterized `col = %s, col2 = %s` clause from a dict."""
    cols = list(fields.keys())
    clause = ", ".join(f"{c} = %s" for c in cols)
    return clause, [fields[c] for c in cols]


def _txt(d: dict, key: str, default: str = "") -> str:
    """Like dict.get, but also coalesces an explicit None value to default.

    BSE's API sometimes returns a field as null rather than omitting it —
    plain .get(key, default) only substitutes default when the key is
    absent, not when its value is None, which trips NOT NULL columns.
    """
    v = d.get(key)
    return default if v is None else v


def _num(d: dict, key: str, default: float = 0) -> float:
    v = d.get(key)
    return default if v is None else v


# ─────────────────────────────────────────────────────────────────────────────
# stocks  (was all_stocks)
# ─────────────────────────────────────────────────────────────────────────────

def _stock_row_to_dict(row: dict) -> dict:
    row = dict(row)
    row["group"] = row.pop("grp", "")
    return row


class StockStore:
    """All BSE-listed stocks with market-cap metadata."""

    @classmethod
    def upsert(cls, stock: dict) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO stocks
                    (scrip_code, scrip_name, company_name, grp, industry,
                     market_cap, face_value, isin, segment, status, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (scrip_code) DO UPDATE SET
                    scrip_name = EXCLUDED.scrip_name,
                    company_name = EXCLUDED.company_name,
                    grp = EXCLUDED.grp,
                    industry = EXCLUDED.industry,
                    market_cap = EXCLUDED.market_cap,
                    face_value = EXCLUDED.face_value,
                    isin = EXCLUDED.isin,
                    segment = EXCLUDED.segment,
                    status = EXCLUDED.status,
                    updated_at = NOW()
                """,
                (
                    stock["scrip_code"], _txt(stock, "scrip_name"),
                    _txt(stock, "company_name"), _txt(stock, "group"),
                    _txt(stock, "industry"), _num(stock, "market_cap"),
                    _txt(stock, "face_value"), _txt(stock, "isin"),
                    _txt(stock, "segment"), _txt(stock, "status"),
                ),
            )

    @classmethod
    def bulk_upsert(cls, stocks: list[dict]) -> int:
        """Bulk upsert; returns number of affected rows."""
        if not stocks:
            return 0
        with get_conn() as conn:
            with conn.cursor() as cur:
                for s in stocks:
                    cur.execute(
                        """
                        INSERT INTO stocks
                            (scrip_code, scrip_name, company_name, grp, industry,
                             market_cap, face_value, isin, segment, status, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (scrip_code) DO UPDATE SET
                            scrip_name = EXCLUDED.scrip_name,
                            company_name = EXCLUDED.company_name,
                            grp = EXCLUDED.grp,
                            industry = EXCLUDED.industry,
                            market_cap = EXCLUDED.market_cap,
                            face_value = EXCLUDED.face_value,
                            isin = EXCLUDED.isin,
                            segment = EXCLUDED.segment,
                            status = EXCLUDED.status,
                            updated_at = NOW()
                        """,
                        (
                            s["scrip_code"], _txt(s, "scrip_name"),
                            _txt(s, "company_name"), _txt(s, "group"),
                            _txt(s, "industry"), _num(s, "market_cap"),
                            _txt(s, "face_value"), _txt(s, "isin"),
                            _txt(s, "segment"), _txt(s, "status"),
                        ),
                    )
            return len(stocks)

    @classmethod
    def get_all(cls) -> list[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM stocks ORDER BY market_cap DESC")
            return [_stock_row_to_dict(r) for r in cur.fetchall()]

    @classmethod
    def count(cls) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM stocks")
            return cur.fetchone()["n"]

    @classmethod
    def update_stock(cls, scrip_code: str, update: dict) -> Optional[dict]:
        """Update specific fields for a stock. Returns the updated row."""
        fields = dict(update)
        if "group" in fields:
            fields["grp"] = fields.pop("group")
        fields["updated_at"] = datetime.now(timezone.utc)
        clause, params = _set_clause(fields)
        with get_cursor() as cur:
            cur.execute(
                f"UPDATE stocks SET {clause} WHERE scrip_code = %s RETURNING *",
                params + [scrip_code],
            )
            row = cur.fetchone()
            return _stock_row_to_dict(row) if row else None

    @classmethod
    def bulk_update_mcap(
        cls, scrip_codes: list[str], *, value: float | None = None, percent: float | None = None
    ) -> int:
        """Update market_cap for multiple stocks. Returns count of updated rows."""
        if not scrip_codes:
            return 0
        with get_cursor() as cur:
            if value is not None:
                cur.execute(
                    "UPDATE stocks SET market_cap = %s, updated_at = NOW() "
                    "WHERE scrip_code = ANY(%s)",
                    (value, scrip_codes),
                )
                return cur.rowcount
            elif percent is not None:
                cur.execute(
                    "UPDATE stocks SET market_cap = market_cap * (1 + %s / 100.0), "
                    "updated_at = NOW() WHERE scrip_code = ANY(%s)",
                    (percent, scrip_codes),
                )
                return cur.rowcount
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# filtered_stocks  (market_cap > MIN_MARKET_CAP) — a derived view of `stocks`,
# no longer a separate table.
# ─────────────────────────────────────────────────────────────────────────────

class FilteredStockStore:
    """Stocks with market_cap above the configured threshold (default ₹500 Cr)."""

    MIN_MARKET_CAP: float = 500.0  # overridden at startup from Config

    @classmethod
    def refresh_from_all_stocks(cls) -> int:
        """No-op — filtered set is now a live query, not a materialized copy.
        Returns the current count of qualifying stocks for compatibility."""
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM stocks WHERE market_cap > %s",
                (cls.MIN_MARKET_CAP,),
            )
            return cur.fetchone()["n"]

    @classmethod
    def is_eligible(cls, scrip_code: str) -> bool:
        with get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM stocks WHERE scrip_code = %s AND market_cap > %s",
                (scrip_code, cls.MIN_MARKET_CAP),
            )
            return cur.fetchone() is not None

    @classmethod
    def get_scrip_codes(cls) -> set[str]:
        with get_cursor() as cur:
            cur.execute(
                "SELECT scrip_code FROM stocks WHERE market_cap > %s", (cls.MIN_MARKET_CAP,)
            )
            return {r["scrip_code"] for r in cur.fetchall()}

    @classmethod
    def get_all(cls) -> list[dict]:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM stocks WHERE market_cap > %s ORDER BY market_cap DESC",
                (cls.MIN_MARKET_CAP,),
            )
            return [_stock_row_to_dict(r) for r in cur.fetchall()]

    @classmethod
    def get_by_scrip_code(cls, code: str) -> Optional[dict]:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM stocks WHERE scrip_code = %s AND market_cap > %s",
                (code, cls.MIN_MARKET_CAP),
            )
            row = cur.fetchone()
            return _stock_row_to_dict(row) if row else None

    @classmethod
    def count(cls) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM stocks WHERE market_cap > %s", (cls.MIN_MARKET_CAP,))
            return cur.fetchone()["n"]

    @classmethod
    def update_stock(cls, scrip_code: str, update: dict) -> Optional[dict]:
        """Same underlying table as StockStore — delegates directly."""
        return StockStore.update_stock(scrip_code, dict(update))


# ─────────────────────────────────────────────────────────────────────────────
# result_calendar
# ─────────────────────────────────────────────────────────────────────────────

def _calendar_row_to_dict(row: dict) -> dict:
    """Preserve the original mixed-case keys the frontend expects."""
    return {
        "scrip_Code": row["scrip_code"],
        "short_name": row["short_name"],
        "Long_Name": row["long_name"],
        "meeting_date": row["meeting_date"],
        "URL": row["url"],
        "updated_at": row.get("updated_at"),
    }


class ResultCalendarStore:
    """Stores BSE result calendar rows for DB-backed calendar API responses."""

    @classmethod
    def ensure_indexes(cls) -> None:
        """No-op — indexes are created by the SQL migration."""
        pass

    @classmethod
    def replace_all(cls, rows: list[dict]) -> int:
        """Replace table contents with fresh calendar rows."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE result_calendar")
                if not rows:
                    return 0
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO result_calendar
                            (scrip_code, short_name, long_name, meeting_date, url, updated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            str(row.get("scrip_Code", "")), str(row.get("short_name", "")),
                            str(row.get("Long_Name", "")), str(row.get("meeting_date", "")),
                            str(row.get("URL", "")),
                        ),
                    )
            return len(rows)

    @staticmethod
    def _parse_meeting_date(value: str) -> date | None:
        raw = str(value or "").strip()
        if not raw:
            return None

        for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def upsert_rows(cls, rows: list[dict]) -> int:
        """Upsert calendar rows; returns number of changed rows."""
        if not rows:
            return 0

        changed = 0
        with get_conn() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    scrip_code = str(row.get("scrip_Code", "")).strip()
                    meeting_date = str(row.get("meeting_date", "")).strip()
                    short_name = str(row.get("short_name", "")).strip()
                    if not scrip_code or not meeting_date:
                        continue

                    cur.execute(
                        """
                        INSERT INTO result_calendar
                            (scrip_code, short_name, long_name, meeting_date, url, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (scrip_code, meeting_date, short_name) DO UPDATE SET
                            long_name = EXCLUDED.long_name,
                            url = EXCLUDED.url,
                            updated_at = NOW()
                        """,
                        (
                            scrip_code, short_name, str(row.get("Long_Name", "")),
                            meeting_date, str(row.get("URL", "")),
                        ),
                    )
                    changed += 1
        return changed

    @classmethod
    def get_all(cls, limit: int = 1000) -> list[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM result_calendar LIMIT %s", (limit,))
            docs = [_calendar_row_to_dict(r) for r in cur.fetchall()]

        def _date_key(doc: dict):
            val = str(doc.get("meeting_date", "")).strip()
            try:
                return datetime.strptime(val, "%d %b %Y")
            except Exception:
                return datetime.max

        return sorted(docs, key=_date_key)

    @classmethod
    def count(cls) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM result_calendar")
            return cur.fetchone()["n"]

    @classmethod
    def get_scrip_codes_for_date(cls, on_date: date) -> set[str]:
        """Return scrip codes that have result calendar entries on a given date."""
        codes: set[str] = set()
        with get_cursor() as cur:
            cur.execute("SELECT scrip_code, meeting_date FROM result_calendar")
            for row in cur.fetchall():
                parsed = cls._parse_meeting_date(row.get("meeting_date", ""))
                if parsed == on_date:
                    code = str(row.get("scrip_code", "")).strip()
                    if code:
                        codes.add(code)
        return codes


# ─────────────────────────────────────────────────────────────────────────────
# seen_announcements  (deduplication)
# ─────────────────────────────────────────────────────────────────────────────

class SeenAnnouncementStore:
    """Tracks processed announcements to prevent re-analysis across restarts."""

    @classmethod
    def is_seen(cls, scrip_code: str, news_date: str, subject: str) -> bool:
        with get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM seen_announcements WHERE scrip_code = %s "
                "AND news_date = %s AND subject = %s",
                (scrip_code, news_date, subject),
            )
            return cur.fetchone() is not None

    @classmethod
    def mark_seen(cls, scrip_code: str, news_date: str, subject: str) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO seen_announcements (scrip_code, news_date, subject, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (scrip_code, news_date, subject) DO NOTHING
                """,
                (scrip_code, news_date, subject),
            )

    @classmethod
    def count(cls) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM seen_announcements")
            return cur.fetchone()["n"]

    @classmethod
    def count_today(cls) -> int:
        """Count announcements seen today (UTC)."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM seen_announcements WHERE created_at >= %s", (today,)
            )
            return cur.fetchone()["n"]


# ─────────────────────────────────────────────────────────────────────────────
# financial_results
# ─────────────────────────────────────────────────────────────────────────────

def _result_row_to_dict(row: dict) -> dict:
    row = dict(row)
    row["_id"] = str(row.pop("id"))
    return row


class FinancialResultStore:
    """Parsed financial analysis data extracted from BSE result PDFs."""

    @classmethod
    def save_result(cls, data: dict) -> str:
        """Save result and return inserted id as string."""
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO financial_results
                    (scrip_code, scrip_name, company_name, market_cap, news_date, subject,
                     pdf_link, raw_analysis, company_name_extracted, unit, quarter,
                     growth, absolute_numbers, margins, signal, confidence, ai_model,
                     extracted_via, analyzed_at, deleted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NULL)
                RETURNING id
                """,
                (
                    _txt(data, "scrip_code"), _txt(data, "scrip_name"),
                    _txt(data, "company_name"), _num(data, "market_cap"),
                    _txt(data, "news_date"), _txt(data, "subject"),
                    _txt(data, "pdf_link"), _txt(data, "raw_analysis"),
                    _txt(data, "company_name_extracted"), _txt(data, "unit"),
                    _txt(data, "quarter"), Json(data.get("growth") or {}),
                    Json(data.get("absolute_numbers") or {}), Json(data.get("margins") or {}),
                    _txt(data, "signal", "NEUTRAL"), _num(data, "confidence"),
                    _txt(data, "ai_model"), _txt(data, "extracted_via"),
                ),
            )
            return str(cur.fetchone()["id"])

    @classmethod
    def get_by_scrip(cls, scrip_code: str, include_deleted: bool = False) -> list[dict]:
        sql = "SELECT * FROM financial_results WHERE scrip_code = %s"
        params: list = [scrip_code]
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        sql += " ORDER BY analyzed_at DESC"
        with get_cursor() as cur:
            cur.execute(sql, params)
            return [_result_row_to_dict(r) for r in cur.fetchall()]

    @classmethod
    def get_latest(cls, limit: int = 50, include_deleted: bool = False) -> list[dict]:
        sql = "SELECT * FROM financial_results"
        if not include_deleted:
            sql += " WHERE deleted_at IS NULL"
        sql += " ORDER BY analyzed_at DESC LIMIT %s"
        with get_cursor() as cur:
            cur.execute(sql, (limit,))
            return [_result_row_to_dict(r) for r in cur.fetchall()]

    @classmethod
    def get_paginated(
        cls,
        *,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "analyzed_at",
        sort_dir: str = "desc",
        signal: str | None = None,
        min_mcap: float | None = None,
        max_mcap: float | None = None,
        sector: str | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[dict], int]:
        """Return (items, total_count) with full pagination and filtering."""
        where = []
        params: list = []

        if not include_deleted:
            where.append("deleted_at IS NULL")
        if signal:
            where.append("signal = %s")
            params.append(signal.upper())
        if min_mcap is not None:
            where.append("market_cap >= %s")
            params.append(min_mcap)
        if max_mcap is not None:
            where.append("market_cap <= %s")
            params.append(max_mcap)
        if sector:
            # Resolve via the stock's actual industry/group rather than
            # financial_results (which has no such columns of its own).
            where.append(
                "scrip_code IN (SELECT scrip_code FROM stocks WHERE industry ILIKE %s OR grp ILIKE %s)"
            )
            params.extend([f"%{sector}%", f"%{sector}%"])
        if search:
            like = f"%{search}%"
            where.append(
                "(scrip_name ILIKE %s OR company_name ILIKE %s OR scrip_code ILIKE %s "
                "OR company_name_extracted ILIKE %s)"
            )
            params.extend([like, like, like, like])
        if from_date:
            where.append("analyzed_at >= %s")
            params.append(from_date)
        if to_date:
            where.append("analyzed_at <= %s")
            params.append(to_date)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        sort_col = sort_by if sort_by in _SORT_WHITELIST else "analyzed_at"
        direction = "ASC" if sort_dir == "asc" else "DESC"
        skip = (page - 1) * limit

        with get_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM financial_results {where_sql}", params)
            total = cur.fetchone()["n"]

            cur.execute(
                f"SELECT * FROM financial_results {where_sql} "
                f"ORDER BY {sort_col} {direction} OFFSET %s LIMIT %s",
                params + [skip, limit],
            )
            docs = [_result_row_to_dict(r) for r in cur.fetchall()]

        return docs, total

    @classmethod
    def get_by_id(cls, doc_id: str) -> Optional[dict]:
        try:
            int_id = int(doc_id)
        except (TypeError, ValueError):
            return None
        with get_cursor() as cur:
            cur.execute("SELECT * FROM financial_results WHERE id = %s", (int_id,))
            row = cur.fetchone()
            return _result_row_to_dict(row) if row else None

    @classmethod
    def soft_delete(cls, doc_id: str) -> bool:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE financial_results SET deleted_at = NOW() WHERE id = %s", (int(doc_id),)
            )
            return cur.rowcount > 0

    @classmethod
    def hard_delete(cls, doc_id: str) -> bool:
        with get_cursor() as cur:
            cur.execute("DELETE FROM financial_results WHERE id = %s", (int(doc_id),))
            return cur.rowcount > 0

    @classmethod
    def bulk_soft_delete(cls, doc_ids: list[str]) -> int:
        ids = [int(i) for i in doc_ids]
        with get_cursor() as cur:
            cur.execute(
                "UPDATE financial_results SET deleted_at = NOW() WHERE id = ANY(%s)", (ids,)
            )
            return cur.rowcount

    @classmethod
    def bulk_hard_delete(cls, doc_ids: list[str]) -> int:
        ids = [int(i) for i in doc_ids]
        with get_cursor() as cur:
            cur.execute("DELETE FROM financial_results WHERE id = ANY(%s)", (ids,))
            return cur.rowcount

    @classmethod
    def exists(cls, scrip_code: str, news_date: str) -> bool:
        with get_cursor() as cur:
            cur.execute(
                "SELECT 1 FROM financial_results WHERE scrip_code = %s AND news_date = %s",
                (scrip_code, news_date),
            )
            return cur.fetchone() is not None

    @classmethod
    def count(cls, include_deleted: bool = False) -> int:
        sql = "SELECT COUNT(*) AS n FROM financial_results"
        if not include_deleted:
            sql += " WHERE deleted_at IS NULL"
        with get_cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()["n"]

    @classmethod
    def has_scrip_on_date(
        cls, scrip_code: str, on_date: date, include_deleted: bool = False
    ) -> bool:
        """Return True if a scrip has at least one analyzed result on a UTC date."""
        start = datetime(on_date.year, on_date.month, on_date.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)

        sql = "SELECT 1 FROM financial_results WHERE scrip_code = %s AND analyzed_at >= %s AND analyzed_at < %s"
        params = [scrip_code, start, end]
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        with get_cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() is not None

    @classmethod
    def count_today(cls) -> int:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with get_cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM financial_results "
                "WHERE analyzed_at >= %s AND deleted_at IS NULL",
                (today,),
            )
            return cur.fetchone()["n"]


# ─────────────────────────────────────────────────────────────────────────────
# monitor_rules
# ─────────────────────────────────────────────────────────────────────────────

def _rule_row_to_dict(row: dict) -> dict:
    row = dict(row)
    row["_id"] = str(row.pop("id"))
    return row


class MonitorRuleStore:
    """Rules that control which announcements the monitor should analyse."""

    @classmethod
    def create(cls, rule: dict) -> dict:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitor_rules (name, field, operator, value, enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, created_at, updated_at
                """,
                (
                    rule.get("name", ""), rule.get("field", ""), rule.get("operator", ""),
                    Json(rule.get("value")), rule.get("enabled", True),
                ),
            )
            row = cur.fetchone()
            rule["_id"] = str(row["id"])
            rule["created_at"] = row["created_at"]
            rule["updated_at"] = row["updated_at"]
            return rule

    @classmethod
    def get_all(cls) -> list[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM monitor_rules ORDER BY created_at DESC")
            return [_rule_row_to_dict(r) for r in cur.fetchall()]

    @classmethod
    def get_enabled(cls) -> list[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM monitor_rules WHERE enabled = TRUE")
            return [_rule_row_to_dict(r) for r in cur.fetchall()]

    @classmethod
    def get_by_id(cls, rule_id: str) -> Optional[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM monitor_rules WHERE id = %s", (int(rule_id),))
            row = cur.fetchone()
            return _rule_row_to_dict(row) if row else None

    @classmethod
    def update(cls, rule_id: str, update: dict) -> Optional[dict]:
        fields = dict(update)
        if "value" in fields:
            fields["value"] = Json(fields["value"])
        fields["updated_at"] = datetime.now(timezone.utc)
        clause, params = _set_clause(fields)
        with get_cursor() as cur:
            cur.execute(
                f"UPDATE monitor_rules SET {clause} WHERE id = %s RETURNING *",
                params + [int(rule_id)],
            )
            row = cur.fetchone()
            return _rule_row_to_dict(row) if row else None

    @classmethod
    def delete(cls, rule_id: str) -> bool:
        with get_cursor() as cur:
            cur.execute("DELETE FROM monitor_rules WHERE id = %s", (int(rule_id),))
            return cur.rowcount > 0

    @classmethod
    def count_enabled(cls) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM monitor_rules WHERE enabled = TRUE")
            return cur.fetchone()["n"]


# ─────────────────────────────────────────────────────────────────────────────
# notifications  (for WebSocket change feed)
# ─────────────────────────────────────────────────────────────────────────────

class NotificationStore:
    """Feed table for real-time WebSocket notifications.

    No TTL index in Postgres — old rows are opportunistically pruned
    (older than 1 hour) each time a new notification is pushed.
    """

    @classmethod
    def ensure_indexes(cls) -> None:
        """No-op — indexes are created by the SQL migration."""
        pass

    @classmethod
    def push(cls, event: str, data: dict) -> None:
        """Insert a notification that the WebSocket endpoint can stream."""
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO notifications (event, data, created_at) VALUES (%s, %s, NOW())",
                (event, Json(data)),
            )
            cur.execute("DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '1 hour'")

    @classmethod
    def get_recent(cls, minutes: int = 5) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM notifications WHERE created_at >= %s ORDER BY created_at DESC",
                (cutoff,),
            )
            docs = []
            for r in cur.fetchall():
                d = dict(r)
                d["_id"] = str(d.pop("id"))
                docs.append(d)
            return docs


# ─────────────────────────────────────────────────────────────────────────────
# monitor_status  (single-row table tracking monitor health)
# ─────────────────────────────────────────────────────────────────────────────

class MonitorStatusStore:
    """Tracks monitor runtime counters in a single row (id=1)."""

    @classmethod
    def update_poll(cls, announcements_count: int = 0) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitor_status (id, last_poll, announcements_count, polls_today)
                VALUES (1, NOW(), %s, 1)
                ON CONFLICT (id) DO UPDATE SET
                    last_poll = NOW(),
                    announcements_count = EXCLUDED.announcements_count,
                    polls_today = monitor_status.polls_today + 1
                """,
                (announcements_count,),
            )

    @classmethod
    def increment_results(cls) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitor_status (id, results_today)
                VALUES (1, 1)
                ON CONFLICT (id) DO UPDATE SET results_today = monitor_status.results_today + 1
                """
            )

    @classmethod
    def set_reload_flag(cls) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitor_status (id, reload_rules) VALUES (1, TRUE)
                ON CONFLICT (id) DO UPDATE SET reload_rules = TRUE
                """
            )

    @classmethod
    def clear_reload_flag(cls) -> bool:
        with get_cursor() as cur:
            cur.execute(
                "UPDATE monitor_status SET reload_rules = FALSE "
                "WHERE id = 1 AND reload_rules = TRUE RETURNING id"
            )
            return cur.fetchone() is not None

    @classmethod
    def get_status(cls) -> dict:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM monitor_status WHERE id = 1")
            row = cur.fetchone()
        if not row:
            return {
                "last_poll": None,
                "announcements_today": 0,
                "results_today": 0,
                "rules_active": MonitorRuleStore.count_enabled(),
            }
        return {
            "last_poll": row.get("last_poll"),
            "announcements_today": SeenAnnouncementStore.count_today(),
            "results_today": row.get("results_today", 0),
            "rules_active": MonitorRuleStore.count_enabled(),
            "reload_rules": row.get("reload_rules", False),
        }

    @classmethod
    def reset_daily(cls) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO monitor_status (id, polls_today, results_today) VALUES (1, 0, 0)
                ON CONFLICT (id) DO UPDATE SET polls_today = 0, results_today = 0
                """
            )


# ─────────────────────────────────────────────────────────────────────────────
# estimates  (analyst estimates for revenue / EBITDA / net profit)
# ─────────────────────────────────────────────────────────────────────────────

class EstimateStore:
    """Analyst estimates imported from the estimates Excel sheet."""

    @classmethod
    def upsert(cls, estimate: dict) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO estimates
                    (scrip_code, scrip_name, sector, cap_size, revenue_estimate,
                     ebitda_estimate, net_profit_estimate, imported_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (scrip_code) DO UPDATE SET
                    scrip_name = EXCLUDED.scrip_name,
                    sector = EXCLUDED.sector,
                    cap_size = EXCLUDED.cap_size,
                    revenue_estimate = EXCLUDED.revenue_estimate,
                    ebitda_estimate = EXCLUDED.ebitda_estimate,
                    net_profit_estimate = EXCLUDED.net_profit_estimate,
                    imported_at = NOW()
                """,
                (
                    estimate["scrip_code"], estimate.get("scrip_name", ""),
                    estimate.get("sector", ""), estimate.get("cap_size", ""),
                    estimate.get("revenue_estimate"), estimate.get("ebitda_estimate"),
                    estimate.get("net_profit_estimate"),
                ),
            )

    @classmethod
    def bulk_upsert(cls, estimates: list[dict]) -> int:
        if not estimates:
            return 0
        for e in estimates:
            cls.upsert(e)
        return len(estimates)

    @classmethod
    def get_by_scrip_code(cls, scrip_code: str) -> Optional[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM estimates WHERE scrip_code = %s", (scrip_code,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def _norm_tokens(name: str | None) -> set[str]:
        if not name:
            return set()
        tokens = set(re.split(r"[^A-Z0-9]+", name.upper()))
        tokens.discard("")
        for stop in ("LTD", "LIMITED", "CORPORATION", "COMPANY", "CO", "INDIA"):
            tokens.discard(stop)
        return tokens

    @classmethod
    def get_by_scrip_or_name(cls, scrip_code: str, names: list[str | None]) -> Optional[dict]:
        """Resolve an estimate by scrip_code first, then best-effort name matching."""
        exact = cls.get_by_scrip_code(scrip_code)
        if exact:
            return exact

        candidates = [n.strip() for n in names if n and n.strip()]
        if not candidates:
            return None

        docs = cls.get_all()

        candidate_upper = {c.upper() for c in candidates}
        for d in docs:
            sname = (d.get("scrip_name") or "").upper()
            if sname and sname in candidate_upper:
                return d

        cand_tokens = set()
        for c in candidates:
            cand_tokens |= cls._norm_tokens(c)
        if not cand_tokens:
            return None

        best_doc: Optional[dict] = None
        best_score = 0
        for d in docs:
            tokens = cls._norm_tokens(d.get("scrip_name"))
            if not tokens:
                continue
            score = len(tokens & cand_tokens)
            if score > best_score:
                best_score = score
                best_doc = d

        return best_doc if best_score >= 2 else None

    @classmethod
    def get_all(cls) -> list[dict]:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM estimates ORDER BY scrip_name")
            return [dict(r) for r in cur.fetchall()]

    @classmethod
    def delete_all(cls) -> int:
        with get_cursor() as cur:
            cur.execute("DELETE FROM estimates")
            return cur.rowcount

    @classmethod
    def count(cls) -> int:
        with get_cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM estimates")
            return cur.fetchone()["n"]
