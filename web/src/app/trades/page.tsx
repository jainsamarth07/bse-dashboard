"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchOrders } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Pagination } from "@/components/Pagination";
import { fmtDateTime, formatINR } from "@/lib/format";
import { clsx } from "clsx";
import { ReceiptText, TrendingUp, TrendingDown, Activity } from "lucide-react";
import type { Order } from "@/lib/types";

const STATUS_OPTIONS = ["all", "PLACED", "COMPLETE", "REJECTED", "CANCELLED"] as const;
const BROKER_OPTIONS = ["all", "paper", "upstox", "angel_one", "groww", "kite", "dhan"] as const;
const PAGE_SIZE = 20;

function PortfolioSummary({ orders }: { orders: Order[] }) {
  const completed = orders.filter((o) => o.status === "COMPLETE");
  const buys = completed.filter((o) => o.side === "BUY");
  const sells = completed.filter((o) => o.side === "SELL");

  const stats = [
    { label: "Total Orders", value: orders.length, icon: ReceiptText, color: "text-blue-400", bg: "bg-blue-500/10" },
    { label: "Completed", value: completed.length, icon: Activity, color: "text-green-400", bg: "bg-green-500/10" },
    { label: "Buy Orders", value: buys.length, icon: TrendingUp, color: "text-green-400", bg: "bg-green-500/10" },
    { label: "Sell Orders", value: sells.length, icon: TrendingDown, color: "text-red-400", bg: "bg-red-500/10" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map(({ label, value, icon: Icon, color, bg }) => (
        <div key={label} className="flex items-center gap-3 rounded-xl p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}>
          <div className={clsx("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg", bg)}>
            <Icon size={18} className={color} />
          </div>
          <div>
            <div className="text-2xl font-bold tabular-nums text-white">{value}</div>
            <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, { bg: string; text: string }> = {
    PLACED: { bg: "rgba(59,130,246,0.12)", text: "#60a5fa" },
    COMPLETE: { bg: "rgba(34,197,94,0.12)", text: "#22c55e" },
    REJECTED: { bg: "rgba(239,68,68,0.12)", text: "#ef4444" },
    CANCELLED: { bg: "rgba(100,116,139,0.12)", text: "#94a3b8" },
  };
  const s = styles[status] ?? styles.CANCELLED;
  return (
    <span className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold" style={{ background: s.bg, color: s.text }}>
      {status}
    </span>
  );
}

export default function TradesPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [brokerFilter, setBrokerFilter] = useState("all");
  const [simFilter, setSimFilter] = useState<"all" | "true" | "false">("all");
  const [page, setPage] = useState(1);

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ["orders", statusFilter, brokerFilter, simFilter],
    queryFn: () =>
      fetchOrders({
        status: statusFilter !== "all" ? statusFilter : undefined,
        broker: brokerFilter !== "all" ? brokerFilter : undefined,
        simulated: simFilter !== "all" ? simFilter === "true" : undefined,
      }),
  });

  const totalPages = Math.max(1, Math.ceil(orders.length / PAGE_SIZE));
  const paginated = orders.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="flex items-center gap-2.5 text-xl font-bold text-white">
            <ReceiptText size={20} className="text-blue-400" />
            Trades
          </h1>
          <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>Order history across all brokers</p>
        </div>

        <PortfolioSummary orders={orders} />

        <div className="flex flex-wrap items-center gap-4 rounded-xl p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}>
          {[
            { label: "Status", value: statusFilter, onChange: setStatusFilter, options: STATUS_OPTIONS },
            { label: "Broker", value: brokerFilter, onChange: setBrokerFilter, options: BROKER_OPTIONS },
          ].map(({ label, value, onChange, options }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>{label}</span>
              <select
                value={value}
                onChange={(e) => {
                  onChange(e.target.value);
                  setPage(1);
                }}
                className="rounded-lg py-1.5 px-3 text-[12px] outline-none"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
              >
                {options.map((o) => (
                  <option key={o} value={o}>{o === "all" ? "All" : o}</option>
                ))}
              </select>
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>Type</span>
            <select
              value={simFilter}
              onChange={(e) => {
                setSimFilter(e.target.value as "all" | "true" | "false");
                setPage(1);
              }}
              className="rounded-lg py-1.5 px-3 text-[12px] outline-none"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
            >
              <option value="all">All</option>
              <option value="true">Paper</option>
              <option value="false">Live</option>
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          </div>
        ) : orders.length === 0 ? (
          <div className="rounded-xl py-16 text-center text-[13px]" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
            No orders found. Place a trade from the Dashboard.
          </div>
        ) : (
          <>
            <div className="overflow-hidden rounded-xl" style={{ border: "1px solid var(--border-subtle)" }}>
              <table className="w-full text-left text-sm">
                <thead>
                  <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-subtle)" }}>
                    {["Time", "Symbol", "Side", "Qty", "Type", "Price", "Broker", "Status", "Mode"].map((h) => (
                      <th key={h} className="px-4 py-3">
                        <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>{h}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paginated.map((order: Order) => (
                    <tr key={order.id} className="transition-colors" style={{ borderBottom: "1px solid var(--border-subtle)" }} onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")} onMouseLeave={(e) => (e.currentTarget.style.background = "")}
                    >
                      <td className="whitespace-nowrap px-4 py-3 text-[11px]" style={{ color: "var(--text-muted)" }}>{fmtDateTime(order.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-white text-[13px]">{order.symbol}</div>
                        <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{order.scrip_code} · {order.exchange}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-full px-2.5 py-0.5 text-[11px] font-bold" style={{ background: order.side === "BUY" ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)", color: order.side === "BUY" ? "#22c55e" : "#ef4444" }}>
                          {order.side}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-semibold text-white">{order.quantity}</td>
                      <td className="px-4 py-3 text-[13px]" style={{ color: "var(--text-secondary)" }}>{order.order_type}</td>
                      <td className="px-4 py-3 font-mono font-semibold text-white tabular-nums">{order.price ? formatINR(order.price) : "—"}</td>
                      <td className="px-4 py-3 capitalize text-[13px]" style={{ color: "var(--text-secondary)" }}>{order.broker}</td>
                      <td className="px-4 py-3"><StatusBadge status={order.status} /></td>
                      <td className="px-4 py-3">
                        {order.simulated ? (
                          <span className="rounded-full px-2.5 py-0.5 text-[11px] font-medium text-amber-400" style={{ background: "rgba(245,158,11,0.12)" }}>Paper</span>
                        ) : (
                          <span className="rounded-full px-2.5 py-0.5 text-[11px] font-medium text-blue-400" style={{ background: "rgba(59,130,246,0.12)" }}>Live</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && <Pagination page={page} pages={totalPages} total={orders.length} onPageChange={setPage} />}
          </>
        )}
      </div>
    </AppShell>
  );
}
