"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { fetchUserSettings, updateUserSettings } from "@/lib/api";
import { toast } from "@/components/Toast";
import type { UserSettings, Signal } from "@/lib/types";

const SIGNAL_OPTIONS: Signal[] = ["BUY", "SELL", "HOLD", "NEUTRAL"];
const BROKERS = ["upstox", "angel_one", "groww", "kite", "dhan"];

export function GeneralTab() {
  const queryClient = useQueryClient();

  const { data: settings, isLoading } = useQuery({
    queryKey: ["user-settings"],
    queryFn: fetchUserSettings,
  });

  const [form, setForm] = useState<UserSettings>({});
  const [initialized, setInitialized] = useState(false);

  // Sync form with fetched settings once
  if (settings && !initialized) {
    setForm(settings);
    setInitialized(true);
  }

  const mutation = useMutation({
    mutationFn: () => updateUserSettings(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-settings"] });
      toast("Settings saved", "success");
    },
    onError: () => toast("Failed to save settings", "error"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="max-w-lg space-y-6">
      {/* Default broker */}
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-300">
          Default Broker
        </label>
        <select
          value={form.default_broker || ""}
          onChange={(e) => setForm({ ...form, default_broker: e.target.value })}
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
        >
          <option value="">None</option>
          {BROKERS.map((b) => (
            <option key={b} value={b}>
              {b.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
            </option>
          ))}
        </select>
      </div>

      {/* Default quantity */}
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-300">
          Default Trade Quantity
        </label>
        <input
          type="number"
          min={1}
          value={form.default_quantity || 1}
          onChange={(e) =>
            setForm({ ...form, default_quantity: Number(e.target.value) })
          }
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
        />
      </div>

      {/* Signal filter */}
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-300">
          Default Signal Filter
        </label>
        <div className="flex flex-wrap gap-2">
          {SIGNAL_OPTIONS.map((s) => {
            const active = form.signal_filter?.includes(s);
            return (
              <button
                key={s}
                onClick={() => {
                  const current = form.signal_filter || [];
                  setForm({
                    ...form,
                    signal_filter: active
                      ? current.filter((x) => x !== s)
                      : [...current, s],
                  });
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? "bg-blue-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {s}
              </button>
            );
          })}
        </div>
      </div>

      {/* Dashboard layout */}
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-300">
          Dashboard Layout
        </label>
        <div className="flex gap-2">
          {(["grid", "list"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setForm({ ...form, dashboard_layout: v })}
              className={`rounded-lg px-4 py-2 text-sm font-medium capitalize transition ${
                form.dashboard_layout === v
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Notifications toggle */}
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="notif"
          checked={form.notifications_enabled ?? true}
          onChange={(e) =>
            setForm({ ...form, notifications_enabled: e.target.checked })
          }
          className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-blue-600"
        />
        <label htmlFor="notif" className="text-sm text-slate-300">
          Enable desktop notifications
        </label>
      </div>

      {/* Save */}
      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-500 transition disabled:opacity-50"
      >
        {mutation.isPending ? "Saving…" : "Save Settings"}
      </button>
    </div>
  );
}
