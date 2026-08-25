"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchResults } from "@/lib/api";
import { TradeModal } from "@/components/TradeModal";
import { Pagination } from "@/components/Pagination";
import { ResultRow } from "@/components/ResultRow";
import {
  TrendingUp, TrendingDown, Activity, Zap, ChevronUp, ChevronDown, ChevronsUpDown,
  AlertCircle, Target, BarChart3,
} from "lucide-react";
import { clsx } from "clsx";
import { fmtPct, toEpochMs } from "@/lib/format";
import type { FinancialResult, Signal, UiPayload } from "@/lib/types";

/* ── Types ────────────────────────────────────────────────────────────────── */

type SortKey = "announced_at" | "company_name" | "net_profit_yoy" | "revenue_yoy" | "confidence" | "market_cap";
type SortDir = "asc" | "desc";

const SIGNAL_OPTIONS: ("ALL" | Signal)[] = ["ALL", "BUY", "SELL", "HOLD", "NEUTRAL"];

/* ── Market Summary Strip ─────────────────────────────────────────────────── */

function SummaryStrip({ results }: { results: FinancialResult[] }) {
  const buys    = results.filter((r) => r.ui_payload.signal === "BUY").length;
  const sells   = results.filter((r) => r.ui_payload.signal === "SELL").length;
  const holds   = results.filter((r) => r.ui_payload.signal === "HOLD").length;

  const sorted = [...results].sort(
    (a, b) =>
      (b.ui_payload.growth?.net_profit?.yoy ?? -999) -
      (a.ui_payload.growth?.net_profit?.yoy ?? -999)
  );
  const biggestBeat = sorted[0];
  const biggestMiss = sorted[sorted.length - 1];

  const sentiment = results.length === 0 ? 50 : Math.round((buys / results.length) * 100);

  const stats = [
    {
      label: "Results Today",
      value: results.length,
      icon: Activity,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "BUY Signals",
      value: buys,
      icon: TrendingUp,
      color: "text-green-400",
      bg: "bg-green-500/10",
    },
    {
      label: "SELL Signals",
      value: sells,
      icon: TrendingDown,
      color: "text-red-400",
      bg: "bg-red-500/10",
    },
    {
      label: "HOLD / Watch",
      value: holds,
      icon: Target,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-6">
      {stats.map(({ label, value, icon: Icon, color, bg }) => (
        <div
          key={label}
          className="flex items-center gap-3 rounded-xl p-4"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
        >
          <div className={clsx("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", bg)}>
            <Icon size={18} className={color} />
          </div>
          <div>
            <div className="text-2xl font-bold tabular-nums text-white">{value}</div>
            <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>{label}</div>
          </div>
        </div>
      ))}

      {/* Biggest beat */}
      {biggestBeat && (
        <div
          className="flex items-center gap-3 rounded-xl p-4"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10">
            <Zap size={18} className="text-emerald-400" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold text-white">
              {biggestBeat.ui_payload.company_name}
            </div>
            <div className="text-[11px] text-emerald-400">
              Best: {fmtPct(biggestBeat.ui_payload.growth?.net_profit?.yoy)} profit YoY
            </div>
          </div>
        </div>
      )}

      {/* Sentiment gauge */}
      <div
        className="flex flex-col justify-center rounded-xl p-4"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
      >
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>Sentiment</span>
          <span
            className={clsx(
              "text-[11px] font-semibold",
              sentiment >= 55 ? "text-green-400" : sentiment <= 35 ? "text-red-400" : "text-amber-400"
            )}
          >
            {sentiment >= 55 ? "Bullish" : sentiment <= 35 ? "Bearish" : "Neutral"}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-slate-700">
          <div
            className={clsx(
              "h-1.5 rounded-full transition-all duration-700",
              sentiment >= 55 ? "bg-green-500" : sentiment <= 35 ? "bg-red-500" : "bg-amber-500"
            )}
            style={{ width: `${sentiment}%` }}
          />
        </div>
        <div className="mt-1.5 text-[10px]" style={{ color: "var(--text-muted)" }}>
          {sentiment}% bullish signals
        </div>
      </div>
    </div>
  );
}

/* ── Critical Alerts ─────────────────────────────────────────────────────── */

function CriticalAlerts({ results, onFilterSignal }: { results: FinancialResult[]; onFilterSignal: (s: string) => void }) {
  const alerts = useMemo(() => {
    const out: Array<{
      level: "red" | "yellow" | "green";
      headline: string;
      sub: string;
      signal: string;
    }> = [];

    const highConfBuys = results
      .filter((r) => r.ui_payload.signal === "BUY" && (r.ui_payload.confidence ?? 0) >= 75)
      .sort((a, b) => (b.ui_payload.confidence ?? 0) - (a.ui_payload.confidence ?? 0));

    if (highConfBuys.length > 0) {
      const top = highConfBuys[0];
      out.push({
        level: "green",
        headline: `Strong BUY: ${top.ui_payload.company_name}`,
        sub: `${top.ui_payload.confidence}% confidence · Net Profit ${fmtPct(top.ui_payload.growth?.net_profit?.yoy)} YoY`,
        signal: "BUY",
      });
    }

    const sells = results.filter((r) => r.ui_payload.signal === "SELL");
    if (sells.length > 0) {
      out.push({
        level: "red",
        headline: `${sells.length} SELL signal${sells.length > 1 ? "s" : ""} detected`,
        sub: sells
          .slice(0, 2)
          .map((r) => r.ui_payload.company_name)
          .join(", "),
        signal: "SELL",
      });
    }

    const misses = results.filter(
      (r) => r.estimate_comparison?.has_estimate && r.estimate_comparison?.net_profit?.verdict === "MISS"
    );
    if (misses.length > 0) {
      out.push({
        level: "yellow",
        headline: `${misses.length} stock${misses.length > 1 ? "s" : ""} missed profit estimates`,
        sub: misses.slice(0, 2).map((r) => r.ui_payload.company_name).join(", "),
        signal: "SELL",
      });
    }

    return out.slice(0, 4);
  }, [results]);

  if (alerts.length === 0) return null;

  const COLOR = {
    red:    { border: "border-red-500/30",    bg: "bg-red-500/5",    dot: "bg-red-400",    text: "text-red-400" },
    yellow: { border: "border-amber-500/30",  bg: "bg-amber-500/5",  dot: "bg-amber-400",  text: "text-amber-400" },
    green:  { border: "border-green-500/30",  bg: "bg-green-500/5",  dot: "bg-green-400",  text: "text-green-400" },
  };

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <AlertCircle size={14} className="text-red-400" />
        <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
          Critical Alerts
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {alerts.map((a, i) => {
          const c = COLOR[a.level];
          return (
            <button
              key={i}
              onClick={() => onFilterSignal(a.signal)}
              className={clsx("flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 text-left transition hover:brightness-110", c.border, c.bg)}
            >
              <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", c.dot)} />
              <div>
                <div className={clsx("text-[12px] font-semibold leading-tight", c.text)}>{a.headline}</div>
                <div className="mt-0.5 text-[11px] leading-snug" style={{ color: "var(--text-muted)" }}>{a.sub}</div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── Top Opportunities (horizontal scroll) ────────────────────────────────── */

function TopOpportunities({ results, onTrade }: {
  results: FinancialResult[];
  onTrade: (payload: UiPayload, side: "BUY" | "SELL") => void;
}) {
  const opps = useMemo(() =>
    results
      .filter((r) => r.ui_payload.signal === "BUY")
      .sort((a, b) => (b.ui_payload.confidence ?? 0) - (a.ui_payload.confidence ?? 0))
      .slice(0, 8),
    [results]
  );

  if (opps.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <BarChart3 size={14} className="text-blue-400" />
        <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
          Top Opportunities
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {opps.map((r) => (
          <motion.div
            key={r.scrip_code}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="shrink-0 w-48 rounded-xl p-4 flex flex-col gap-3"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
          >
            <div>
              <div className="truncate text-[13px] font-semibold text-white">{r.ui_payload.company_name}</div>
              <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{r.scrip_code} · {r.ui_payload.quarter}</div>
            </div>
            <div className="flex items-end justify-between">
              <div>
                <div className="text-xl font-bold text-green-400 tabular-nums">
                  {fmtPct(r.ui_payload.growth?.net_profit?.yoy)}
                </div>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Profit YoY</div>
              </div>
              <div
                className="rounded-full px-2 py-0.5 text-[10px] font-bold text-green-400"
                style={{ background: "rgba(34,197,94,0.12)" }}
              >
                {r.ui_payload.confidence}%
              </div>
            </div>
            <div className="flex gap-1.5">
              <button
                onClick={() => onTrade(r.ui_payload, "BUY")}
                className="flex-1 rounded-lg bg-green-600 py-1.5 text-[11px] font-semibold text-white transition hover:bg-green-500"
              >
                Trade
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

/* ── Sort icon ────────────────────────────────────────────────────────────── */

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (col !== sortKey) return <ChevronsUpDown size={12} className="opacity-30" />;
  return sortDir === "asc"
    ? <ChevronUp size={12} className="text-blue-400" />
    : <ChevronDown size={12} className="text-blue-400" />;
}

/* ── Results Feed Table ───────────────────────────────────────────────────── */

function ResultsFeed({
  results,
  isLoading,
  page,
  pages,
  total,
  onPageChange,
  onTrade,
}: {
  results: FinancialResult[];
  isLoading: boolean;
  page: number;
  pages: number;
  total: number;
  onPageChange: (p: number) => void;
  onTrade: (payload: UiPayload, side: "BUY" | "SELL") => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("announced_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  function handleSort(col: SortKey) {
    if (col === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col);
      setSortDir("desc");
    }
  }

  const sorted = useMemo(() => {
    return [...results].sort((a, b) => {
      let av: number | string = 0;
      let bv: number | string = 0;
      if (sortKey === "company_name") {
        av = a.ui_payload.company_name ?? "";
        bv = b.ui_payload.company_name ?? "";
      } else if (sortKey === "announced_at") {
        av = toEpochMs(a.news_date) || toEpochMs(a.analyzed_at);
        bv = toEpochMs(b.news_date) || toEpochMs(b.analyzed_at);
      } else if (sortKey === "net_profit_yoy") {
        av = a.ui_payload.growth?.net_profit?.yoy ?? -9999;
        bv = b.ui_payload.growth?.net_profit?.yoy ?? -9999;
      } else if (sortKey === "revenue_yoy") {
        av = a.ui_payload.growth?.revenue?.yoy ?? -9999;
        bv = b.ui_payload.growth?.revenue?.yoy ?? -9999;
      } else if (sortKey === "confidence") {
        av = a.ui_payload.confidence ?? 0;
        bv = b.ui_payload.confidence ?? 0;
      } else if (sortKey === "market_cap") {
        av = a.market_cap ?? 0;
        bv = b.market_cap ?? 0;
      }
      if (typeof av === "string") {
        return sortDir === "asc" ? av.localeCompare(bv as string) : (bv as string).localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [results, sortKey, sortDir]);

  const COLS: Array<{ key: SortKey; label: string; align?: string }> = [
    { key: "company_name",   label: "Company" },
    { key: "net_profit_yoy", label: "Profit YoY",  align: "right" },
    { key: "revenue_yoy",    label: "Revenue YoY", align: "right" },
    { key: "confidence",     label: "Confidence",  align: "right" },
    { key: "market_cap",     label: "Mkt Cap",     align: "right" },
    { key: "announced_at",   label: "Announced",   align: "right" },
  ];

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-blue-400" />
          <span className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
            Results Feed
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setSortKey("announced_at");
              setSortDir((d) => (sortKey === "announced_at" && d === "desc" ? "asc" : "desc"));
            }}
            className="rounded-md px-2.5 py-1 text-[11px] font-medium transition hover:brightness-110"
            style={{
              background: sortKey === "announced_at" ? "var(--bg-elevated)" : "transparent",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-muted)",
            }}
            title="Toggle announcement order"
          >
            {sortKey === "announced_at" && sortDir === "asc"
              ? "Announcements: Oldest first"
              : "Announcements: Latest first"}
          </button>
          <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>{total} result{total !== 1 ? "s" : ""}</span>
        </div>
      </div>

      <div
        className="overflow-hidden rounded-xl"
        style={{ border: "1px solid var(--border-subtle)" }}
      >
        {/* Table header */}
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-subtle)" }}>
              {/* Signal col */}
              <th className="px-4 py-3 text-left">
                <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                  Signal
                </span>
              </th>
              {COLS.map((col) => (
                <th
                  key={col.key}
                  className={clsx("cursor-pointer px-4 py-3 select-none", col.align === "right" ? "text-right" : "text-left")}
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                    {col.label}
                    <SortIcon col={col.key} sortKey={sortKey} sortDir={sortDir} />
                  </span>
                </th>
              ))}
              {/* Verdict col */}
              <th className="px-4 py-3 text-left">
                <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                  Verdict
                </span>
              </th>
              {/* Expand col */}
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={9} className="py-16 text-center">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                </td>
              </tr>
            ) : sorted.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-16 text-center text-[13px]" style={{ color: "var(--text-muted)" }}>
                  No earnings processed yet today — the monitor is watching BSE…
                </td>
              </tr>
            ) : (
              sorted.map((r) => (
                <ResultRow
                  key={`${r.scrip_code}-${r.analyzed_at}`}
                  result={r}
                  expanded={expandedId === `${r.scrip_code}-${r.analyzed_at}`}
                  onToggle={() =>
                    setExpandedId((id) =>
                      id === `${r.scrip_code}-${r.analyzed_at}`
                        ? null
                        : `${r.scrip_code}-${r.analyzed_at}`
                    )
                  }
                  onTrade={onTrade}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <Pagination page={page} pages={pages} total={total} onPageChange={onPageChange} />
      )}
    </div>
  );
}

/* ── Main Dashboard ───────────────────────────────────────────────────────── */

export function Dashboard() {
  const [signalFilter, setSignalFilter] = useState<string>("ALL");
  const [search, setSearch]             = useState("");
  const [page, setPage]                 = useState(1);
  const [tradeTarget, setTradeTarget]   = useState<{ payload: UiPayload; side: "BUY" | "SELL" } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["results", signalFilter, search, page],
    queryFn: () =>
      fetchResults({
        page,
        page_size: 30,
        signal: signalFilter === "ALL" ? undefined : signalFilter,
        search: search || undefined,
      }),
    staleTime: 15_000,
    refetchInterval: 15_000,  // safety-net: refresh every 15 s if WebSocket misses an event
  });

  const results = data?.items ?? [];
  const total   = data?.total ?? 0;
  const pages   = data?.pages ?? 1;

  function handleTrade(payload: UiPayload, side: "BUY" | "SELL") {
    setTradeTarget({ payload, side });
  }

  return (
    <div className="space-y-6">
      {/* ── Market Summary Strip ─────────────────────────────────────── */}
      <SummaryStrip results={results} />

      {/* ── Critical Alerts ──────────────────────────────────────────── */}
      <CriticalAlerts results={results} onFilterSignal={(s) => setSignalFilter(s)} />

      {/* ── Top Opportunities ────────────────────────────────────────── */}
      <TopOpportunities results={results} onTrade={handleTrade} />

      {/* ── Filter bar ───────────────────────────────────────────────── */}
      <div
        className="flex flex-wrap items-center gap-3 rounded-xl p-4"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
      >
        <input
          type="text"
          placeholder="Filter by company or scrip…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="flex-1 min-w-[200px] rounded-lg px-3 py-2 text-[13px] outline-none focus:ring-1 focus:ring-blue-500/50"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            color: "var(--text-primary)",
          }}
        />
        <div className="flex gap-1">
          {SIGNAL_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => { setSignalFilter(s); setPage(1); }}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-[12px] font-medium transition",
                signalFilter === s
                  ? s === "BUY"  ? "bg-green-600 text-white"
                  : s === "SELL" ? "bg-red-600 text-white"
                  : s === "HOLD" ? "bg-amber-600 text-white"
                  : "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-white"
              )}
              style={signalFilter !== s ? { background: "var(--bg-elevated)" } : undefined}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* ── Results Feed ─────────────────────────────────────────────── */}
      <ResultsFeed
        results={results}
        isLoading={isLoading}
        page={page}
        pages={pages}
        total={total}
        onPageChange={setPage}
        onTrade={handleTrade}
      />

      {/* ── Trade modal ──────────────────────────────────────────────── */}
      {tradeTarget && (
        <TradeModal
          scrip_code={tradeTarget.payload.scrip_code}
          company_name={tradeTarget.payload.company_name}
          side={tradeTarget.side}
          onClose={() => setTradeTarget(null)}
        />
      )}
    </div>
  );
}