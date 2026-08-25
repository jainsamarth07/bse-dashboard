"use client";

import { clsx } from "clsx";
import type { UiPayload } from "@/lib/types";
import { fmtDateTime } from "@/lib/format";

/* ── Signal badge colours ─────────────────────────────────────────────────── */

const SIGNAL_STYLES: Record<string, string> = {
  BUY: "bg-green-500/20 text-green-400 border-green-500/30",
  SELL: "bg-red-500/20 text-red-400 border-red-500/30",
  HOLD: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  NEUTRAL: "bg-slate-500/20 text-slate-400 border-slate-500/30",
};

/* ── Helpers ──────────────────────────────────────────────────────────────── */

function fmt(v: number | null | undefined, suffix = "%"): string {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}${suffix}`;
}

function fmtAbs(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-IN");
}

function growthColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-slate-400";
  return v >= 0 ? "text-green-400" : "text-red-400";
}

/* ── Component ────────────────────────────────────────────────────────────── */

interface Props {
  payload: UiPayload;
  marketCap?: number;
  analyzedAt?: string | null;
  newsDate?: string;
  onTrade?: (side: "BUY" | "SELL") => void;
}

export function ResultCard({ payload, marketCap, analyzedAt, newsDate, onTrade }: Props) {
  const {
    company_name,
    quarter,
    unit,
    growth,
    absolute_numbers,
    margins,
    signal,
    confidence,
    scrip_code,
  } = payload;

  return (
    <div className="rounded-xl border border-slate-700 bg-[#1e293b] p-5 shadow-lg hover:border-slate-600 transition">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">{company_name}</h3>
          <p className="text-sm text-slate-400">
            {scrip_code} · {quarter} · {unit}
            {marketCap ? ` · ₹${marketCap.toLocaleString("en-IN")} Cr` : ""}
          </p>
          {analyzedAt && (
            <p className="mt-0.5 text-xs text-slate-500">
              🕐 {fmtDateTime(analyzedAt)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "rounded-full border px-3 py-1 text-xs font-bold uppercase",
              SIGNAL_STYLES[signal] || SIGNAL_STYLES.NEUTRAL
            )}
          >
            {signal}
          </span>
          <span className="text-xs text-slate-500">{confidence}%</span>
        </div>
      </div>

      {/* ── Growth summary ─────────────────────────────────────────────── */}
      <div className="mb-4 grid grid-cols-3 gap-3 text-center text-sm">
        {(["revenue", "ebitda", "net_profit"] as const).map((metric) => (
          <div key={metric} className="rounded-lg bg-slate-800/50 p-3">
            <div className="mb-1 text-xs font-medium uppercase text-slate-500">
              {metric === "net_profit" ? "Net Profit" : metric.toUpperCase()}
            </div>
            <div className={clsx("text-base font-bold", growthColor(growth[metric].yoy))}>
              {fmt(growth[metric].yoy)}
            </div>
            <div className="text-xs text-slate-500">
              YoY · QoQ {fmt(growth[metric].qoq)}
            </div>
          </div>
        ))}
      </div>

      {/* ── Absolute numbers ───────────────────────────────────────────── */}
      <div className="mb-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500">
              <th className="pb-1 text-left font-medium">Metric</th>
              <th className="pb-1 text-right font-medium">Latest</th>
              <th className="pb-1 text-right font-medium">Prev Q</th>
              <th className="pb-1 text-right font-medium">SQLY</th>
            </tr>
          </thead>
          <tbody className="text-slate-300">
            {(["revenue", "ebitda", "net_profit"] as const).map((m) => (
              <tr key={m} className="border-t border-slate-700/50">
                <td className="py-1 capitalize">
                  {m === "net_profit" ? "Net Profit" : m.toUpperCase()}
                </td>
                <td className="py-1 text-right font-mono">
                  {fmtAbs(absolute_numbers[m].latest)}
                </td>
                <td className="py-1 text-right font-mono">
                  {fmtAbs(absolute_numbers[m].previous)}
                </td>
                <td className="py-1 text-right font-mono">
                  {fmtAbs(absolute_numbers[m].sqly)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Margins ────────────────────────────────────────────────────── */}
      <div className="mb-4 flex gap-4 text-sm">
        <div className="flex-1 rounded-lg bg-slate-800/50 p-2 text-center">
          <div className="text-xs text-slate-500">EBITDA Margin</div>
          <div className="font-bold text-white">
            {fmt(margins.ebitda_margin)}
          </div>
        </div>
        <div className="flex-1 rounded-lg bg-slate-800/50 p-2 text-center">
          <div className="text-xs text-slate-500">Net Profit Margin</div>
          <div className="font-bold text-white">
            {fmt(margins.net_profit_margin)}
          </div>
        </div>
      </div>

      {/* ── Trade buttons ──────────────────────────────────────────────── */}
      {onTrade && (
        <div className="flex gap-2">
          <button
            onClick={() => onTrade("BUY")}
            className="flex-1 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-500 transition"
          >
            Buy
          </button>
          <button
            onClick={() => onTrade("SELL")}
            className="flex-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 transition"
          >
            Sell
          </button>
        </div>
      )}
    </div>
  );
}
