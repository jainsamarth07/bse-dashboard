"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import {
  ChevronDown, ChevronRight,
  TrendingUp, TrendingDown, Minus,
  ShoppingCart, ExternalLink,
} from "lucide-react";
import {
  AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmtDateTime, fmtPct, formatMcap, fmtAbs } from "@/lib/format";
import type { FinancialResult, UiPayload, EstimateComparison, Verdict } from "@/lib/types";

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const SIGNAL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  BUY:     { bg: "rgba(34,197,94,0.12)",  text: "#22c55e", border: "rgba(34,197,94,0.3)" },
  SELL:    { bg: "rgba(239,68,68,0.12)",  text: "#ef4444", border: "rgba(239,68,68,0.3)" },
  HOLD:    { bg: "rgba(245,158,11,0.12)", text: "#f59e0b", border: "rgba(245,158,11,0.3)" },
  NEUTRAL: { bg: "rgba(100,116,139,0.12)", text: "#94a3b8", border: "rgba(100,116,139,0.3)" },
};

const VERDICT_STYLES: Record<Verdict, { bg: string; text: string }> = {
  BEAT:    { bg: "rgba(16,185,129,0.12)", text: "#10b981" },
  MISS:    { bg: "rgba(239,68,68,0.12)",  text: "#ef4444" },
  IN_LINE: { bg: "rgba(100,116,139,0.12)", text: "#94a3b8" },
};

function growthIcon(v: number | null | undefined) {
  if (v == null) return <Minus size={11} className="text-slate-500" />;
  return v >= 0
    ? <TrendingUp size={11} className="text-green-400" />
    : <TrendingDown size={11} className="text-red-400" />;
}

function growthColor(v: number | null | undefined): string {
  if (v == null) return "var(--text-muted)";
  return v >= 0 ? "#22c55e" : "#ef4444";
}

function announcementDateTime(result: FinancialResult): string {
  const hasTimeInNewsDate = typeof result.news_date === "string" && /\d{1,2}:\d{2}/.test(result.news_date);
  return hasTimeInNewsDate ? result.news_date : (result.analyzed_at || result.news_date);
}

/* ── Sparkline bars (from absolute_numbers) ───────────────────────────────── */

function MetricBar({ label, values }: { label: string; values: number[] }) {
  const data = values.map((v, i) => ({ v, i }));
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>{label}</div>
      <ResponsiveContainer width="100%" height={50}>
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`g-${label}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}   />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="v" stroke="#3b82f6" strokeWidth={1.5}
            fill={`url(#g-${label})`} dot={false} />
          <Tooltip
            contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", fontSize: 10 }}
            labelFormatter={() => ""}
            formatter={(v) => [Number(v ?? 0).toLocaleString("en-IN"), label]}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Expanded detail panel ────────────────────────────────────────────────── */

function ExpandedDetail({
  result,
  onTrade,
}: {
  result: FinancialResult;
  onTrade: (payload: UiPayload, side: "BUY" | "SELL") => void;
}) {
  const { ui_payload: p, estimate_comparison: ec } = result;
  const [tab, setTab] = useState<"overview" | "ai">("overview");

  const metrics = ["revenue", "ebitda", "net_profit"] as const;
  const LABELS  = { revenue: "Revenue", ebitda: "EBITDA", net_profit: "Net Profit" };

  return (
    <tr>
      <td
        colSpan={9}
        style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-subtle)" }}
        className="px-0 py-0"
      >
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div className="p-5">
            {/* Tabs */}
            <div className="mb-4 flex gap-1 border-b" style={{ borderColor: "var(--border-subtle)" }}>
              {(["overview", "ai"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={clsx(
                    "rounded-t-lg px-4 py-2 text-[12px] font-medium transition",
                    tab === t ? "text-white border-b-2 border-blue-500" : "hover:text-white"
                  )}
                  style={{ color: tab === t ? "var(--text-primary)" : "var(--text-muted)" }}
                >
                  {t === "overview" ? "Overview" : "AI Analysis"}
                </button>
              ))}
            </div>

            {tab === "overview" && (
              <div className="grid gap-6 lg:grid-cols-3">
                {/* Charts */}
                <div className="col-span-2 grid gap-4 sm:grid-cols-3">
                  {metrics.map((m) => {
                    const vals = [
                      p.absolute_numbers[m].sqly,
                      p.absolute_numbers[m].previous,
                      p.absolute_numbers[m].latest,
                    ].filter((v): v is number => v != null);
                    return (
                      <div
                        key={m}
                        className="rounded-xl p-4"
                        style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
                      >
                        <MetricBar label={LABELS[m]} values={vals} />
                        <div className="mt-2 flex items-center justify-between">
                          <div>
                            <div className="text-[13px] font-semibold text-white">
                              {fmtAbs(p.absolute_numbers[m].latest)}
                            </div>
                            <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Latest</div>
                          </div>
                          <div className="text-right">
                            <div className="text-[12px] font-semibold tabular-nums" style={{ color: growthColor(p.growth[m].yoy) }}>
                              {fmtPct(p.growth[m].yoy)}
                            </div>
                            <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>YoY</div>
                          </div>
                        </div>
                        {/* Estimate vs actual */}
                        {ec?.has_estimate && ec[m]?.verdict && (
                          <div
                            className="mt-2 flex items-center justify-between rounded px-2 py-1"
                            style={{
                              background: VERDICT_STYLES[ec[m]!.verdict!].bg,
                            }}
                          >
                            <span className="text-[10px]" style={{ color: VERDICT_STYLES[ec[m]!.verdict!].text }}>
                              {ec[m]!.verdict} by {ec[m]!.pct_diff != null ? `${Math.abs(ec[m]!.pct_diff!).toFixed(1)}%` : "—"}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Right panel: full metrics table + margins */}
                <div className="space-y-4">
                  {/* Absolute numbers table */}
                  <div
                    className="rounded-xl overflow-hidden"
                    style={{ border: "1px solid var(--border-subtle)" }}
                  >
                    <table className="w-full text-[12px]">
                      <thead>
                        <tr style={{ background: "var(--bg-card)", borderBottom: "1px solid var(--border-subtle)" }}>
                          <th className="px-3 py-2 text-left font-medium" style={{ color: "var(--text-muted)" }}>Metric</th>
                          <th className="px-3 py-2 text-right font-medium" style={{ color: "var(--text-muted)" }}>Latest</th>
                          <th className="px-3 py-2 text-right font-medium" style={{ color: "var(--text-muted)" }}>SQLY</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.map((m) => (
                          <tr key={m} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                            <td className="px-3 py-2" style={{ color: "var(--text-secondary)" }}>{LABELS[m]}</td>
                            <td className="px-3 py-2 text-right font-mono text-white tabular-nums">
                              {fmtAbs(p.absolute_numbers[m].latest)}
                            </td>
                            <td className="px-3 py-2 text-right font-mono tabular-nums" style={{ color: "var(--text-muted)" }}>
                              {fmtAbs(p.absolute_numbers[m].sqly)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Margins */}
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: "EBITDA Margin", value: p.margins.ebitda_margin },
                      { label: "Net Margin",    value: p.margins.net_profit_margin },
                    ].map(({ label, value }) => (
                      <div
                        key={label}
                        className="rounded-xl p-3 text-center"
                        style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
                      >
                        <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{label}</div>
                        <div className="mt-1 text-[16px] font-bold text-white">{fmtPct(value)}</div>
                      </div>
                    ))}
                  </div>

                  {/* Trade buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => onTrade(p, "BUY")}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-green-600 py-2.5 text-[13px] font-semibold text-white transition hover:bg-green-500"
                    >
                      <ShoppingCart size={14} /> Buy
                    </button>
                    <button
                      onClick={() => onTrade(p, "SELL")}
                      className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-red-600 py-2.5 text-[13px] font-semibold text-white transition hover:bg-red-500"
                    >
                      Sell
                    </button>
                  </div>
                </div>
              </div>
            )}

            {tab === "ai" && (
              <div
                className="rounded-xl p-4 text-[13px] leading-relaxed whitespace-pre-wrap"
                style={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border-subtle)",
                  color: "var(--text-secondary)",
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: "12px",
                  maxHeight: "400px",
                  overflowY: "auto",
                }}
              >
                {p.raw_analysis || "No AI analysis available for this result."}
              </div>
            )}
          </div>
        </motion.div>
      </td>
    </tr>
  );
}

/* ── ResultRow ────────────────────────────────────────────────────────────── */

interface Props {
  result:   FinancialResult;
  expanded: boolean;
  onToggle: () => void;
  onTrade:  (payload: UiPayload, side: "BUY" | "SELL") => void;
}

export function ResultRow({ result, expanded, onToggle, onTrade }: Props) {
  const { ui_payload: p, estimate_comparison: ec } = result;
  const sig = SIGNAL_STYLES[p.signal] ?? SIGNAL_STYLES.NEUTRAL;
  const announcedAt = announcementDateTime(result);

  const verdict = ec?.has_estimate ? ec?.net_profit?.verdict ?? null : null;
  const vs = verdict ? VERDICT_STYLES[verdict] : null;

  return (
    <>
      <tr
        className="cursor-pointer transition-colors"
        style={{
          background: expanded ? "var(--bg-elevated)" : "var(--bg-card)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
        onMouseEnter={(e) => { if (!expanded) (e.currentTarget as HTMLElement).style.background = "var(--bg-hover)"; }}
        onMouseLeave={(e) => { if (!expanded) (e.currentTarget as HTMLElement).style.background = "var(--bg-card)"; }}
        onClick={onToggle}
      >
        {/* Signal badge */}
        <td className="px-4 py-3">
          <span
            className="inline-block rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase"
            style={{ background: sig.bg, color: sig.text, border: `1px solid ${sig.border}` }}
          >
            {p.signal}
          </span>
        </td>

        {/* Company */}
        <td className="px-4 py-3">
          <div className="font-medium text-white text-[13px]">{p.company_name}</div>
          <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
            {result.scrip_code} · {p.quarter} · {p.unit}
          </div>
        </td>

        {/* Net Profit YoY */}
        <td className="px-4 py-3 text-right">
          <div
            className="inline-flex items-center gap-1 font-semibold tabular-nums text-[13px]"
            style={{ color: growthColor(p.growth?.net_profit?.yoy) }}
          >
            {growthIcon(p.growth?.net_profit?.yoy)}
            {fmtPct(p.growth?.net_profit?.yoy)}
          </div>
          <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
            QoQ {fmtPct(p.growth?.net_profit?.qoq)}
          </div>
        </td>

        {/* Revenue YoY */}
        <td className="px-4 py-3 text-right">
          <div
            className="font-medium tabular-nums text-[13px]"
            style={{ color: growthColor(p.growth?.revenue?.yoy) }}
          >
            {fmtPct(p.growth?.revenue?.yoy)}
          </div>
        </td>

        {/* Confidence */}
        <td className="px-4 py-3 text-right">
          <div className="inline-flex flex-col items-end gap-1">
            <span className="text-[13px] font-semibold text-white">{p.confidence}%</span>
            <div className="h-1 w-16 rounded-full bg-slate-700">
              <div
                className="h-1 rounded-full bg-blue-500"
                style={{ width: `${p.confidence}%` }}
              />
            </div>
          </div>
        </td>

        {/* Market cap */}
        <td className="px-4 py-3 text-right">
          <span className="text-[13px] text-white tabular-nums">{formatMcap(result.market_cap)}</span>
        </td>

        {/* Announcement time */}
        <td className="px-4 py-3 text-right">
          <span className="text-[11px] tabular-nums" style={{ color: "var(--text-muted)" }}>
            {fmtDateTime(announcedAt)}
          </span>
        </td>

        {/* Verdict */}
        <td className="px-4 py-3">
          {vs && verdict ? (
            <span
              className="rounded px-2 py-0.5 text-[11px] font-semibold"
              style={{ background: vs.bg, color: vs.text }}
            >
              {verdict === "IN_LINE" ? "In-Line" : verdict}
            </span>
          ) : (
            <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>—</span>
          )}
        </td>

        {/* Expand arrow */}
        <td className="px-3 py-3 text-right">
          <span style={{ color: "var(--text-muted)" }}>
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
        </td>
      </tr>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <ExpandedDetail
            result={result}
            onTrade={onTrade}
          />
        )}
      </AnimatePresence>
    </>
  );
}
