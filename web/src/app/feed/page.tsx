"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { fetchResults } from "@/lib/api";
import { fmtDateTime, fmtPct, formatMcap, toEpochMs } from "@/lib/format";
import { Rss, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { clsx } from "clsx";
import type { FinancialResult } from "@/lib/types";

const SIGNAL_COLORS: Record<string, string> = {
  BUY:     "#22c55e",
  SELL:    "#ef4444",
  HOLD:    "#f59e0b",
  NEUTRAL: "#94a3b8",
};

function growthColor(v: number | null | undefined) {
  if (v == null) return "var(--text-muted)";
  return v >= 0 ? "#22c55e" : "#ef4444";
}

export default function FeedPage() {
  const [signal, setSignal] = useState("ALL");
  const [announcementOrder, setAnnouncementOrder] = useState<"latest" | "oldest">("latest");
  const [page]              = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["results", signal === "ALL" ? "ALL" : signal, "", page],
    queryFn: () => fetchResults({ signal: signal === "ALL" ? undefined : signal, page, page_size: 50 }),
  });

  const results: FinancialResult[] = data?.items ?? [];
  const orderedResults = useMemo(() => {
    const dir = announcementOrder === "latest" ? -1 : 1;
    return [...results].sort((a, b) => {
      const aTs = toEpochMs(a.news_date || a.analyzed_at);
      const bTs = toEpochMs(b.news_date || b.analyzed_at);
      return (aTs - bTs) * dir;
    });
  }, [results, announcementOrder]);

  return (
    <AppShell>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2.5 text-xl font-bold text-white">
            <Rss size={20} className="text-blue-400" />
            Earnings Feed
          </h1>
          <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
            Chronological stream of analysed result announcements
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-5 flex flex-wrap gap-2">
        <select
          value={announcementOrder}
          onChange={(e) => setAnnouncementOrder(e.target.value as "latest" | "oldest")}
          className="rounded-lg px-3 py-1.5 text-[12px] font-semibold"
          style={{
            background: "var(--bg-card)",
            color: "var(--text-muted)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <option value="latest">Latest Announcements First</option>
          <option value="oldest">Oldest Announcements First</option>
        </select>

        {["ALL", "BUY", "SELL", "HOLD", "NEUTRAL"].map((s) => (
          <button
            key={s}
            onClick={() => setSignal(s)}
            className={clsx("rounded-lg px-3 py-1.5 text-[12px] font-semibold transition")}
            style={{
              background: signal === s
                ? (s === "ALL" ? "#3b82f6" : SIGNAL_COLORS[s] + "33")
                : "var(--bg-card)",
              color: signal === s
                ? (s === "ALL" ? "#fff" : SIGNAL_COLORS[s])
                : "var(--text-muted)",
              border: `1px solid ${signal === s
                ? (s === "ALL" ? "#3b82f6" : SIGNAL_COLORS[s] + "66")
                : "var(--border-subtle)"}`,
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : orderedResults.length === 0 ? (
        <div
          className="rounded-xl py-16 text-center text-[13px]"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}
        >
          No results in the feed yet. Start the monitor to see live analysis here.
        </div>
      ) : (
        <div className="space-y-3">
          {orderedResults.map((r) => {
            const p = r.ui_payload;
            const sigColor = SIGNAL_COLORS[p.signal] ?? SIGNAL_COLORS.NEUTRAL;
            return (
              <div
                key={r.scrip_code + r.news_date + (r.analyzed_at ?? "")}
                className="flex items-center gap-4 rounded-xl p-4"
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                  borderLeft: `3px solid ${sigColor}`,
                }}
              >
                {/* Signal */}
                <span
                  className="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase"
                  style={{ background: sigColor + "20", color: sigColor, border: `1px solid ${sigColor}44` }}
                >
                  {p.signal}
                </span>

                {/* Company info */}
                <div className="flex-1 min-w-0">
                  <div className="truncate font-semibold text-white text-[13px]">{p.company_name}</div>
                  <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                    {r.scrip_code} · {p.quarter} · {formatMcap(r.market_cap)}
                  </div>
                </div>

                {/* Metrics */}
                <div className="hidden sm:flex items-center gap-6">
                  {[
                    { label: "Rev YoY",    val: p.growth?.revenue?.yoy },
                    { label: "EBITDA YoY", val: p.growth?.ebitda?.yoy },
                    { label: "PAT YoY",    val: p.growth?.net_profit?.yoy },
                  ].map(({ label, val }) => (
                    <div key={label} className="text-right">
                      <div className="font-semibold text-[13px] tabular-nums" style={{ color: growthColor(val) }}>
                        {val != null ? (
                          <span className="inline-flex items-center gap-0.5">
                            {val >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                            {fmtPct(val)}
                          </span>
                        ) : <Minus size={12} />}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--text-muted)" }}>{label}</div>
                    </div>
                  ))}
                </div>

                {/* Time */}
                <div className="shrink-0 text-[10px] text-right" style={{ color: "var(--text-muted)" }}>
                  {fmtDateTime(r.analyzed_at)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
