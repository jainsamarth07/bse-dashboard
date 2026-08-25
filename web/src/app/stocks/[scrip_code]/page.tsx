"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { fetchStock, fetchResultHistory, fetchBseQuote } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { SignalBadge } from "@/components/SignalBadge";
import { formatMcap, fmtPct, fmtAbs, growthColor, fmtDateTime } from "@/lib/format";
import { ArrowLeft, ExternalLink, TrendingUp, TrendingDown } from "lucide-react";
import { clsx } from "clsx";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const scrip_code = params.scrip_code as string;

  const { data: stock, isLoading: stockLoading } = useQuery({
    queryKey: ["stock", scrip_code],
    queryFn: () => fetchStock(scrip_code),
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["result-history", scrip_code],
    queryFn: () => fetchResultHistory(scrip_code, 20),
  });

  const { data: quote } = useQuery({
    queryKey: ["bse-quote", scrip_code],
    queryFn: () => fetchBseQuote(scrip_code),
    retry: false,
  });

  const isLoading = stockLoading || historyLoading;

  // Chart data from result history
  const chartData = (history ?? [])
    .slice()
    .reverse()
    .map((r) => ({
      quarter: r.ui_payload?.quarter || r.news_date,
      revenue_yoy: r.ui_payload?.growth?.revenue?.yoy ?? 0,
      net_profit_yoy: r.ui_payload?.growth?.net_profit?.yoy ?? 0,
      ebitda_margin: r.ui_payload?.margins?.ebitda_margin ?? 0,
    }));

  return (
    <AppShell>
      {/* ── Back button ────────────────────────────────────────────────── */}
      <button
        onClick={() => router.push("/stocks")}
        className="mb-4 flex items-center gap-1 text-sm text-slate-400 hover:text-white transition"
      >
        <ArrowLeft size={16} />
        Back to Stocks
      </button>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : !stock ? (
        <div className="py-20 text-center text-slate-500">Stock not found.</div>
      ) : (
        <>
          {/* ── Header ─────────────────────────────────────────────────── */}
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold text-white">
                {stock.company_name}
              </h2>
              <p className="text-sm text-slate-400">
                {stock.scrip_name} · {stock.scrip_code} · Group {stock.group} ·{" "}
                {stock.industry || "N/A"}
              </p>
              <p className="mt-1 text-sm text-slate-500">ISIN: {stock.isin}</p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-white">
                {formatMcap(stock.market_cap)}
              </div>
              <div className="text-xs text-slate-500">Market Cap</div>
              {quote && (
                <div className="mt-2">
                  <span className="text-lg font-semibold text-white">
                    ₹{Number(quote.CurrRate || quote.last || 0).toLocaleString("en-IN")}
                  </span>
                  <span
                    className={clsx(
                      "ml-2 text-sm font-medium",
                      Number(quote.Change || 0) >= 0
                        ? "text-green-400"
                        : "text-red-400"
                    )}
                  >
                    {Number(quote.Change || 0) >= 0 ? "+" : ""}
                    {Number(quote.Change || 0).toFixed(2)} (
                    {Number(quote.PerChange || 0).toFixed(2)}%)
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ── Revenue & Profit Growth Chart ──────────────────────────── */}
          {chartData.length > 0 && (
            <div className="mb-8 rounded-xl border border-slate-700 bg-[#1e293b] p-5">
              <h3 className="mb-4 text-sm font-semibold text-white">
                Revenue & Net Profit Growth (YoY %)
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="quarter"
                    stroke="#64748b"
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                  />
                  <YAxis
                    stroke="#64748b"
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                    tickFormatter={(v: number) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#f1f5f9",
                      fontSize: 12,
                    }}
                    formatter={(value) => [`${Number(value).toFixed(1)}%`]}
                  />
                  <Bar
                    dataKey="revenue_yoy"
                    name="Revenue"
                    fill="#3b82f6"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="net_profit_yoy"
                    name="Net Profit"
                    fill="#22c55e"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* ── Result History ─────────────────────────────────────────── */}
          <h3 className="mb-4 text-sm font-semibold text-white">
            Financial Results History ({(history ?? []).length} results)
          </h3>

          {(history ?? []).length === 0 ? (
            <div className="rounded-xl border border-slate-700 bg-[#1e293b] px-6 py-12 text-center text-slate-500">
              No results analysed for this stock yet.
            </div>
          ) : (
            <div className="space-y-3">
              {(history ?? []).map((r, i) => {
                const p = r.ui_payload;
                return (
                  <div
                    key={r.analyzed_at + i}
                    className="rounded-xl border border-slate-700 bg-[#1e293b] p-5 transition hover:border-slate-600"
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <span className="font-medium text-white">
                          {p?.quarter || r.news_date}
                        </span>
                        <span className="ml-2 text-xs text-slate-500">
                          {fmtDateTime(r.analyzed_at)}
                        </span>
                        <span className="ml-2 text-xs text-slate-500">
                          · {r.ai_model}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {p?.signal && <SignalBadge signal={p.signal} />}
                        <a
                          href={r.pdf_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:text-blue-300"
                        >
                          <ExternalLink size={14} />
                        </a>
                      </div>
                    </div>

                    {/* Growth row */}
                    {p?.growth && (
                      <div className="grid grid-cols-3 gap-3 text-center text-sm">
                        {(["revenue", "ebitda", "net_profit"] as const).map(
                          (metric) => (
                            <div
                              key={metric}
                              className="rounded-lg bg-slate-800/50 p-3"
                            >
                              <div className="mb-1 text-xs font-medium uppercase text-slate-500">
                                {metric === "net_profit"
                                  ? "Net Profit"
                                  : metric.toUpperCase()}
                              </div>
                              <div
                                className={clsx(
                                  "text-base font-bold",
                                  growthColor(p.growth[metric]?.yoy)
                                )}
                              >
                                {fmtPct(p.growth[metric]?.yoy)}
                              </div>
                              <div className="text-xs text-slate-500">
                                YoY · QoQ {fmtPct(p.growth[metric]?.qoq)}
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}
