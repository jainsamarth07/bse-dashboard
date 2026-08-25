"use client";

import { useState } from "react";
import { placeTrade } from "@/lib/api";

interface Props {
  scrip_code: string;
  company_name: string;
  side: "BUY" | "SELL";
  onClose: () => void;
}

export function TradeModal({ scrip_code, company_name, side, onClose }: Props) {
  const [broker, setBroker] = useState("upstox");
  const [quantity, setQuantity] = useState(1);
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [price, setPrice] = useState<number | undefined>();
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      // Dhan identifies instruments by numeric securityId, which for BSE equity
      // maps 1-to-1 with the BSE scrip code. Other brokers use the trading symbol.
      const symbol =
        broker === "dhan"
          ? scrip_code
          : company_name.split(" ")[0].toUpperCase();

      const res = await placeTrade({
        broker,
        scrip_code,
        symbol,
        exchange: "BSE",
        side,
        quantity,
        order_type: orderType,
        price: orderType === "LIMIT" ? price : undefined,
      });
      setResult(
        `${res.simulated ? "📝 Simulated" : "✅ Placed"}: ${res.message} (${res.order_id})`
      );
    } catch (err: any) {
      setResult(`❌ ${err?.response?.data?.detail || err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-[#1e293b] p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">
            {side === "BUY" ? "📈" : "📉"} {side} — {company_name}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>

        {result ? (
          <div className="mb-4 rounded-lg bg-slate-800 p-4 text-sm text-slate-300">
            {result}
            <button
              onClick={onClose}
              className="mt-3 w-full rounded-lg bg-slate-700 py-2 text-sm text-white hover:bg-slate-600"
            >
              Close
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Broker</label>
              <select
                value={broker}
                onChange={(e) => setBroker(e.target.value)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              >
                <option value="upstox">Upstox</option>
                <option value="angel_one">Angel One</option>
                <option value="groww">Groww</option>
                <option value="kite">Kite (Zerodha)</option>
                <option value="dhan">Dhan</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Quantity</label>
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Order Type</label>
              <div className="flex gap-2">
                {(["MARKET", "LIMIT"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setOrderType(t)}
                    className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium ${
                      orderType === t
                        ? "bg-blue-600 text-white"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {orderType === "LIMIT" && (
              <div>
                <label className="mb-1 block text-xs text-slate-400">Price (₹)</label>
                <input
                  type="number"
                  step="0.05"
                  value={price || ""}
                  onChange={(e) => setPrice(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
                />
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className={`w-full rounded-lg py-2.5 font-semibold text-white transition ${
                side === "BUY"
                  ? "bg-green-600 hover:bg-green-500"
                  : "bg-red-600 hover:bg-red-500"
              } ${submitting ? "opacity-50" : ""}`}
            >
              {submitting
                ? "Placing…"
                : `${side} ${quantity} share${quantity > 1 ? "s" : ""}`}
            </button>

            <p className="text-center text-xs text-slate-500">
              Paper mode by default. Configure live keys in Broker settings.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
