"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { fetchResults } from "@/lib/api";
import {
  BarChart2, TrendingUp, TrendingDown, PieChart,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart as RechartsPie, Pie, Cell, Legend,
} from "recharts";
import type { FinancialResult } from "@/lib/types";

const SIGNAL_COLORS: Record<string, string> = {
  BUY:     "#22c55e",
  SELL:    "#ef4444",
  HOLD:    "#f59e0b",
  NEUTRAL: "#94a3b8",
};

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["results", "ALL", "", 1],
    queryFn: () => fetchResults({ page: 1, page_size: 200 }),
  });

  const results: FinancialResult[] = data?.items ?? [];

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  /* ── Signal distribution ─── */
  const signalCounts = results.reduce<Record<string, number>>((acc, r) => {
    const s = r.ui_payload.signal;
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});

  const pieData = Object.entries(signalCounts).map(([name, value]) => ({ name, value }));

  /* ── Avg YoY growth by signal ─── */
  const growthBySignal: Record<string, number[]> = {};
  results.forEach((r) => {
    const s = r.ui_payload.signal;
    const g = r.ui_payload.growth?.net_profit?.yoy;
    if (g != null) {
      if (!growthBySignal[s]) growthBySignal[s] = [];
      growthBySignal[s].push(g);
    }
  });
  const avgGrowth = Object.entries(growthBySignal).map(([signal, vals]) => ({
    signal,
    avg: Math.round(vals.reduce((a, b) => a + b, 0) / vals.length),
  }));

  /* ── Top 10 by confidence ─── */
  const top10 = [...results]
    .sort((a, b) => b.ui_payload.confidence - a.ui_payload.confidence)
    .slice(0, 10);

  const barData = top10.map((r) => ({
    name: r.ui_payload.company_name.split(" ").slice(0, 2).join(" "),
    confidence: r.ui_payload.confidence,
    signal: r.ui_payload.signal,
  }));

  const tooltipStyle = {
    contentStyle: {
      background: "var(--bg-elevated)",
      border: "1px solid var(--border-default)",
      fontSize: 12,
      color: "var(--text-primary)",
    },
  };

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="flex items-center gap-2.5 text-xl font-bold text-white">
          <BarChart2 size={20} className="text-blue-400" />
          Analytics
        </h1>
        <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
          Aggregate insights from {results.length} analysed results
        </p>
      </div>

      {results.length === 0 ? (
        <div
          className="rounded-xl py-20 text-center text-[13px]"
          style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}
        >
          No results to analyse yet. Run the monitor to generate data.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Signal distribution pie */}
          <div
            className="rounded-xl p-6"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
          >
            <div className="mb-4 flex items-center gap-2">
              <PieChart size={16} className="text-blue-400" />
              <span className="text-[13px] font-semibold text-white">Signal Distribution</span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <RechartsPie>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(((percent ?? 0) * 100)).toFixed(0)}%`} labelLine={false}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={SIGNAL_COLORS[entry.name] ?? "#64748b"} />
                  ))}
                </Pie>
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
              </RechartsPie>
            </ResponsiveContainer>
          </div>

          {/* Avg profit growth by signal */}
          <div
            className="rounded-xl p-6"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
          >
            <div className="mb-4 flex items-center gap-2">
              <TrendingUp size={16} className="text-green-400" />
              <span className="text-[13px] font-semibold text-white">Avg PAT Growth by Signal</span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={avgGrowth}>
                <XAxis dataKey="signal" tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip {...tooltipStyle} formatter={(v) => [`${Number(v ?? 0)}%`, "Avg YoY"]} />
                <Bar dataKey="avg" radius={[4, 4, 0, 0]}>
                  {avgGrowth.map((entry) => (
                    <Cell key={entry.signal} fill={SIGNAL_COLORS[entry.signal] ?? "#64748b"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Top 10 by confidence */}
          <div
            className="rounded-xl p-6 lg:col-span-2"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
          >
            <div className="mb-4 flex items-center gap-2">
              <TrendingDown size={16} className="text-amber-400" />
              <span className="text-[13px] font-semibold text-white">Top 10 by AI Confidence</span>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData} layout="vertical">
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--text-muted)" }} unit="%" axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 10, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
                <Tooltip {...tooltipStyle} formatter={(v) => [`${Number(v ?? 0)}%`, "Confidence"]} />
                <Bar dataKey="confidence" radius={[0, 4, 4, 0]}>
                  {barData.map((entry) => (
                    <Cell key={entry.name} fill={SIGNAL_COLORS[entry.signal] ?? "#64748b"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </AppShell>
  );
}
