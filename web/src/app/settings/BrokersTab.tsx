"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchBrokerKeys,
  addBrokerKey,
  deleteBrokerKey,
  testBrokerConnection,
  toggleBrokerMode,
} from "@/lib/api";
import { toast } from "@/components/Toast";
import { ConfirmModal } from "@/components/ConfirmModal";
import { LiveIndicator } from "@/components/LiveIndicator";
import {
  Trash2,
  TestTube2,
  Plus,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { clsx } from "clsx";
import type { BrokerKey } from "@/lib/types";

const BROKERS = [
  { value: "upstox", label: "Upstox" },
  { value: "angel_one", label: "Angel One" },
  { value: "groww", label: "Groww" },
  { value: "kite", label: "Kite (Zerodha)" },
  { value: "dhan", label: "Dhan" },
];
                                                                                                                                      
export function BrokersTab() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [modeTarget, setModeTarget] = useState<{ id: number; mode: "live" | "paper" } | null>(null);
  const [modePassword, setModePassword] = useState("");

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["broker-keys"],
    queryFn: fetchBrokerKeys,
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteBrokerKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["broker-keys"] });
      toast("Broker key deleted", "success");
      setDeleteTarget(null);
    },
    onError: () => toast("Failed to delete key", "error"),
  });

  const testMut = useMutation({
    mutationFn: (id: number) => testBrokerConnection(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["broker-keys"] });
      toast(
        data.connected
          ? `✅ ${data.message}`
          : `❌ ${data.message}`,
        data.connected ? "success" : "error"
      );
    },
    onError: (err: any) =>
      toast(err?.response?.data?.detail || "Test connection request failed", "error"),
  });

  const modeMut = useMutation({
    mutationFn: ({ id, mode }: { id: number; mode: string }) =>
      toggleBrokerMode(id, mode as "paper" | "live", modePassword || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["broker-keys"] });
      toast("Mode updated", "success");
      setModeTarget(null);
      setModePassword("");
    },
    onError: (err: any) =>
      toast(err?.response?.data?.detail || "Failed to switch mode", "error"),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">
          Configured Brokers ({keys.length})
        </h3>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition"
        >
          <Plus size={14} />
          Add Broker
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : keys.length === 0 ? (
        <div className="rounded-xl border border-slate-700 bg-[#1e293b] py-12 text-center text-slate-500">
          No broker keys configured yet. Add one to start trading.
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map((k: BrokerKey) => (
            <div
              key={k.id}
              className="flex items-center justify-between rounded-xl border border-slate-700 bg-[#1e293b] p-4"
            >
              <div className="flex items-center gap-4">
                <div>
                  <div className="font-medium text-white capitalize">
                    {k.broker.replace("_", " ")}
                  </div>
                  <div className="text-xs text-slate-500">
                    {k.api_key_masked}
                  </div>
                </div>
                <LiveIndicator
                  connected={k.is_connected}
                  label={k.is_connected ? "Connected" : "Not tested"}
                />
                <span
                  className={clsx(
                    "rounded px-2 py-0.5 text-xs font-medium",
                    k.mode === "live"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-slate-700 text-slate-400"
                  )}
                >
                  {k.mode.toUpperCase()}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => testMut.mutate(k.id)}
                  disabled={testMut.isPending}
                  className="rounded-lg bg-slate-700 p-2 text-slate-300 hover:bg-slate-600 transition"
                  title="Test connection"
                >
                  <TestTube2 size={14} />
                </button>
                <button
                  onClick={() =>
                    setModeTarget({
                      id: k.id,
                      mode: k.mode === "live" ? "paper" : "live",
                    })
                  }
                  className="rounded-lg bg-slate-700 p-2 text-slate-300 hover:bg-slate-600 transition"
                  title={`Switch to ${k.mode === "live" ? "paper" : "live"}`}
                >
                  {k.mode === "live" ? (
                    <ShieldCheck size={14} />
                  ) : (
                    <ShieldAlert size={14} />
                  )}
                </button>
                <button
                  onClick={() => setDeleteTarget(k.id)}
                  className="rounded-lg bg-slate-700 p-2 text-red-400 hover:bg-red-900/30 transition"
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Add Broker Modal ───────────────────────────────────────────── */}
      {showAdd && (
        <AddBrokerModal onClose={() => setShowAdd(false)} />
      )}

      {/* ── Delete Confirmation ────────────────────────────────────────── */}
      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete Broker Key"
        message="This will permanently remove the broker key. Any open orders may be affected."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* ── Mode Switch Modal (password for live) ──────────────────────── */}
      {modeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-xl border border-slate-700 bg-[#1e293b] p-6">
            <h3 className="mb-2 text-lg font-bold text-white">
              Switch to {modeTarget.mode.toUpperCase()} Mode
            </h3>
            {modeTarget.mode === "live" ? (
              <>
                <p className="mb-4 text-sm text-slate-400">
                  Re-enter your password to enable live trading.
                </p>
                <input
                  type="password"
                  value={modePassword}
                  onChange={(e) => setModePassword(e.target.value)}
                  placeholder="Your account password"
                  className="mb-4 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
                />
              </>
            ) : (
              <p className="mb-4 text-sm text-slate-400">
                Switch back to paper trading mode.
              </p>
            )}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setModeTarget(null);
                  setModePassword("");
                }}
                className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  modeMut.mutate({
                    id: modeTarget.id,
                    mode: modeTarget.mode,
                  })
                }
                disabled={
                  modeMut.isPending ||
                  (modeTarget.mode === "live" && !modePassword)
                }
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {modeMut.isPending ? "Switching…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Add Broker Modal ─────────────────────────────────────────────────────────

// Per-broker field labels and hints
const BROKER_FIELDS: Record<
  string,
  { apiKeyLabel: string; apiSecretLabel: string; apiKeyHint?: string; apiSecretHint?: string; extraField?: { stateKey: string; label: string; hint: string } }
> = {
  dhan: {
    apiKeyLabel: "Access Token",
    apiKeyHint: "Generate from web.dhan.co → My Profile → Access DhanHQ APIs (valid 24 h)",
    apiSecretLabel: "Client ID",
    apiSecretHint: "Your Dhan Client ID (e.g. 1000000001)",
    extraField: { stateKey: "pin", label: "Dhan PIN (optional — for TOTP auto-refresh)", hint: "6-digit Dhan PIN. Required only if you also set a TOTP secret above." },
  },
  upstox: { apiKeyLabel: "API Key", apiSecretLabel: "API Secret" },
  angel_one: { apiKeyLabel: "Client Code", apiSecretLabel: "Password", apiKeyHint: "Your Angel One Client Code", apiSecretHint: "Your Angel One login password" },
  groww: { apiKeyLabel: "API Key", apiSecretLabel: "API Secret" },
  kite: { apiKeyLabel: "API Key", apiSecretLabel: "API Secret" },
};

function AddBrokerModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [broker, setBroker] = useState("upstox");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [totp, setTotp] = useState("");
  const [pin, setPin] = useState("");

  const fields = BROKER_FIELDS[broker] ?? { apiKeyLabel: "API Key", apiSecretLabel: "API Secret" };

  const mutation = useMutation({
    mutationFn: () =>
      addBrokerKey({
        broker,
        api_key: apiKey,
        api_secret: apiSecret,
        totp_secret: totp || undefined,
        redirect_uri: broker === "dhan" && pin ? pin : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["broker-keys"] });
      toast("Broker key added", "success");
      onClose();
    },
    onError: (err: any) =>
      toast(err?.response?.data?.detail || "Failed to add key", "error"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-[#1e293b] p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">Add Broker Key</h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Broker</label>
            <select
              value={broker}
              onChange={(e) => setBroker(e.target.value)}
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            >
              {BROKERS.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">{fields.apiKeyLabel}</label>
            {fields.apiKeyHint && (
              <p className="mb-1 text-xs text-slate-500">{fields.apiKeyHint}</p>
            )}
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">{fields.apiSecretLabel}</label>
            {fields.apiSecretHint && (
              <p className="mb-1 text-xs text-slate-500">{fields.apiSecretHint}</p>
            )}
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">
              TOTP Secret (optional)
            </label>
            <input
              type="password"
              value={totp}
              onChange={(e) => setTotp(e.target.value)}
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            />
          </div>
          {broker === "dhan" && (
            <div>
              <label className="mb-1 block text-xs text-slate-400">
                Dhan PIN (optional)
              </label>
              <p className="mb-1 text-xs text-slate-500">
                Your 6-digit Dhan PIN — only needed if you set a TOTP secret above (for auto token refresh).
              </p>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </div>
          )}
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !apiKey || !apiSecret}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 transition disabled:opacity-50"
          >
            {mutation.isPending ? "Adding…" : "Add Broker Key"}
          </button>
        </div>
      </div>
    </div>
  );
}
