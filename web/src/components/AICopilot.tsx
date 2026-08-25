"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, Send, TrendingUp, TrendingDown, AlertTriangle, Lightbulb, ChevronRight } from "lucide-react";
import { fetchResults } from "@/lib/api";
import { clsx } from "clsx";
import type { FinancialResult } from "@/lib/types";

interface Insight {
  icon: React.ElementType;
  color: string;
  text: string;
  filter?: string;
}

function buildInsights(results: FinancialResult[]): Insight[] {
  if (!results.length) return [];
  const insights: Insight[] = [];

  const buys  = results.filter((r) => r.ui_payload.signal === "BUY");
  const sells = results.filter((r) => r.ui_payload.signal === "SELL");

  // Best performer
  const sorted = [...results].sort(
    (a, b) => (b.ui_payload.growth?.net_profit?.yoy ?? -999) - (a.ui_payload.growth?.net_profit?.yoy ?? -999)
  );
  if (sorted[0]) {
    const top = sorted[0];
    const yoy = top.ui_payload.growth?.net_profit?.yoy;
    if (yoy && yoy > 0) {
      insights.push({
        icon: TrendingUp,
        color: "text-green-400",
        text: `${top.ui_payload.company_name} leads with ${yoy.toFixed(0)}% profit growth YoY`,
        filter: "BUY",
      });
    }
  }

  // Worst performer
  const worst = sorted[sorted.length - 1];
  if (worst && (worst.ui_payload.growth?.net_profit?.yoy ?? 0) < -10) {
    const yoy = worst.ui_payload.growth?.net_profit?.yoy!;
    insights.push({
      icon: TrendingDown,
      color: "text-red-400",
      text: `${worst.ui_payload.company_name} saw ${Math.abs(yoy).toFixed(0)}% profit decline YoY`,
      filter: "SELL",
    });
  }

  if (buys.length > 0) {
    insights.push({
      icon: Lightbulb,
      color: "text-blue-400",
      text: `${buys.length} stock${buys.length > 1 ? "s" : ""} showing strong BUY signals today`,
      filter: "BUY",
    });
  }

  if (sells.length > 0) {
    insights.push({
      icon: AlertTriangle,
      color: "text-amber-400",
      text: `${sells.length} stock${sells.length > 1 ? "s" : ""} triggered SELL signals — review now`,
      filter: "SELL",
    });
  }

  // Beat/miss estimates
  const beats = results.filter(
    (r) => r.estimate_comparison?.has_estimate &&
           r.estimate_comparison?.net_profit?.verdict === "BEAT"
  );
  if (beats.length > 0) {
    insights.push({
      icon: Sparkles,
      color: "text-emerald-400",
      text: `${beats.length} stock${beats.length > 1 ? "s" : ""} beat analyst net profit estimates`,
    });
  }

  return insights.slice(0, 5);
}

interface Props {
  onFilterSignal?: (signal: string) => void;
}

export function AICopilot({ onFilterSignal }: Props) {
  const [query, setQuery]     = useState("");
  const [answer, setAnswer]   = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);

  const { data } = useQuery({
    queryKey: ["results", "ALL", "", 1],
    queryFn: () => fetchResults({ page: 1, page_size: 50 }),
    staleTime: 60_000,
  });

  const results  = data?.items ?? [];
  const insights = useMemo(() => buildInsights(results), [results]);

  function handleQuery() {
    if (!query.trim()) return;
    setThinking(true);
    setAnswer(null);

    // Client-side "AI" — pattern match common queries
    const q = query.toLowerCase();
    setTimeout(() => {
      if (q.includes("beat") || q.includes("estimate")) {
        const n = results.filter(
          (r) => r.estimate_comparison?.net_profit?.verdict === "BEAT"
        ).length;
        setAnswer(`${n} stock${n !== 1 ? "s" : ""} beat analyst estimates. Filter by signal BUY to see the top performers.`);
      } else if (q.includes("buy") || q.includes("opportunity")) {
        const buys = results.filter((r) => r.ui_payload.signal === "BUY");
        const names = buys.slice(0, 3).map((r) => r.ui_payload.company_name).join(", ");
        setAnswer(`${buys.length} BUY signals found today${names ? `: ${names}` : ""}. Click the BUY filter button to see them.`);
      } else if (q.includes("sell") || q.includes("miss")) {
        const sells = results.filter((r) => r.ui_payload.signal === "SELL");
        setAnswer(`${sells.length} SELL signal${sells.length !== 1 ? "s" : ""} detected. Use the SELL filter to review these positions.`);
      } else if (q.includes("profit") || q.includes("grow")) {
        const sorted = [...results].sort(
          (a, b) => (b.ui_payload.growth?.net_profit?.yoy ?? 0) - (a.ui_payload.growth?.net_profit?.yoy ?? 0)
        );
        const top = sorted.slice(0, 3).map(
          (r) => `${r.ui_payload.company_name} (${(r.ui_payload.growth?.net_profit?.yoy ?? 0).toFixed(0)}%)`
        ).join(", ");
        setAnswer(`Top profit growers YoY: ${top || "No data yet"}.`);
      } else if (q.includes("high confidence") || q.includes("confident")) {
        const high = results.filter((r) => (r.ui_payload.confidence ?? 0) >= 75);
        setAnswer(`${high.length} result${high.length !== 1 ? "s" : ""} have confidence ≥75%. These are your highest-conviction signals.`);
      } else {
        setAnswer(`I found ${results.length} results today. Ask me about BUY signals, profit growth, estimate beats, or SELL alerts.`);
      }
      setThinking(false);
    }, 600);
  }

  return (
    <aside
      className="fixed inset-y-0 right-0 z-40 flex flex-col"
      style={{
        width: "280px",
        background: "var(--bg-panel)",
        borderLeft: "1px solid var(--border-subtle)",
      }}
    >
      {/* ── Header ───────────────────────────────────────────────────── */}
      <div
        className="flex h-[60px] shrink-0 items-center gap-2.5 px-4 border-b"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600/20">
          <Sparkles size={14} className="text-violet-400" />
        </div>
        <div>
          <div className="text-[13px] font-semibold text-white">AI Copilot</div>
          <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Powered by market data</div>
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* ── Insights ─────────────────────────────────────────────────── */}
        <div className="shrink-0 overflow-y-auto p-4 space-y-2">
          <div
            className="mb-3 text-[10px] font-semibold uppercase tracking-widest"
            style={{ color: "var(--text-muted)" }}
          >
            Key Insights
          </div>

          {insights.length === 0 ? (
            <div
              className="rounded-lg p-3 text-[12px] text-center"
              style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}
            >
              No results yet — waiting for market data
            </div>
          ) : (
            insights.map((ins, i) => (
              <button
                key={i}
                onClick={() => ins.filter && onFilterSignal?.(ins.filter)}
                className="group flex w-full items-start gap-2.5 rounded-lg p-3 text-left transition hover:bg-white/5"
                style={{ background: "var(--bg-elevated)" }}
              >
                <ins.icon size={14} className={clsx("mt-0.5 shrink-0", ins.color)} />
                <span className="text-[12px] leading-snug" style={{ color: "var(--text-secondary)" }}>
                  {ins.text}
                </span>
                {ins.filter && (
                  <ChevronRight size={12} className="ml-auto mt-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition" style={{ color: "var(--text-muted)" }} />
                )}
              </button>
            ))
          )}
        </div>

        {/* ── Top 3 opportunities ──────────────────────────────────────── */}
        {results.filter((r) => r.ui_payload.signal === "BUY").length > 0 && (
          <div className="shrink-0 border-t px-4 py-3" style={{ borderColor: "var(--border-subtle)" }}>
            <div
              className="mb-2 text-[10px] font-semibold uppercase tracking-widest"
              style={{ color: "var(--text-muted)" }}
            >
              Top Opportunities
            </div>
            {results
              .filter((r) => r.ui_payload.signal === "BUY")
              .sort((a, b) => (b.ui_payload.confidence ?? 0) - (a.ui_payload.confidence ?? 0))
              .slice(0, 3)
              .map((r) => (
                <div
                  key={r.scrip_code}
                  className="mb-1.5 flex items-center justify-between rounded-lg px-3 py-2"
                  style={{ background: "var(--bg-elevated)" }}
                >
                  <div>
                    <div className="text-[12px] font-medium text-white truncate max-w-[130px]">
                      {r.ui_payload.company_name}
                    </div>
                    <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                      {r.ui_payload.confidence}% confidence
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[12px] font-semibold text-green-400">
                      {r.ui_payload.growth?.net_profit?.yoy != null
                        ? `+${r.ui_payload.growth.net_profit.yoy.toFixed(0)}%`
                        : "BUY"}
                    </div>
                    <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>profit YoY</div>
                  </div>
                </div>
              ))}
          </div>
        )}

        {/* ── AI Query box ─────────────────────────────────────────────── */}
        <div className="mt-auto border-t p-4" style={{ borderColor: "var(--border-subtle)" }}>
          {answer && (
            <div
              className="mb-3 rounded-lg p-3 text-[12px] leading-relaxed"
              style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)" }}
            >
              <span className="mr-1 text-violet-400">✦</span>
              {answer}
            </div>
          )}
          {thinking && (
            <div className="mb-3 flex items-center gap-2 text-[12px]" style={{ color: "var(--text-muted)" }}>
              <span className="inline-block h-3 w-3 animate-spin rounded-full border border-violet-400 border-t-transparent" />
              Analysing…
            </div>
          )}
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQuery()}
              placeholder="Ask about results…"
              className="flex-1 bg-transparent text-[12px] outline-none placeholder:text-slate-600"
              style={{ color: "var(--text-primary)" }}
            />
            <button
              onClick={handleQuery}
              className="rounded p-1 transition hover:bg-violet-500/20"
              style={{ color: "var(--text-muted)" }}
            >
              <Send size={13} />
            </button>
          </div>
          <p className="mt-2 text-[10px] text-center" style={{ color: "var(--text-muted)" }}>
            Ask about BUY signals, estimates, profit growth…
          </p>
        </div>
      </div>
    </aside>
  );
}
