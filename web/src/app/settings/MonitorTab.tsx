"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchMonitorRules,
  createMonitorRule,
  updateMonitorRule,
  deleteMonitorRule,
  reloadMonitorRules,
  fetchMonitorStatus,
} from "@/lib/api";
import { toast } from "@/components/Toast";
import { ConfirmModal } from "@/components/ConfirmModal";
import { LiveIndicator } from "@/components/LiveIndicator";
import {
  Plus,
  Trash2,
  RefreshCw,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { clsx } from "clsx";
import type { MonitorRule } from "@/lib/types";

const FIELDS = ["market_cap", "group", "industry", "scrip_name"];
const OPERATORS = ["gt", "lt", "equals", "contains", "in", "not_in"];

export function MonitorTab() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ["monitor-rules"],
    queryFn: fetchMonitorRules,
  });

  const { data: status } = useQuery({
    queryKey: ["monitor-status"],
    queryFn: fetchMonitorStatus,
    refetchInterval: 10_000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteMonitorRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitor-rules"] });
      toast("Rule deleted", "success");
      setDeleteTarget(null);
    },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateMonitorRule(id, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitor-rules"] });
    },
  });

  const reloadMut = useMutation({
    mutationFn: reloadMonitorRules,
    onSuccess: () => toast("Reload signal sent to monitor", "success"),
    onError: () => toast("Failed to trigger reload", "error"),
  });

  return (
    <div>
      {/* ── Status bar ─────────────────────────────────────────────────── */}
      {status && (
        <div className="mb-6 flex flex-wrap items-center gap-6 rounded-xl border border-slate-700 bg-[#1e293b] p-4 text-sm">
          <div className="flex items-center gap-2">
            <LiveIndicator connected={!!status.last_poll} />
            <span className="text-slate-400">
              Last poll:{" "}
              {status.last_poll
                ? new Date(status.last_poll).toLocaleTimeString()
                : "Never"}
            </span>
          </div>
          <div className="text-slate-400">
            Results today:{" "}
            <span className="font-medium text-white">
              {status.results_today}
            </span>
          </div>
          <div className="text-slate-400">
            Announcements:{" "}
            <span className="font-medium text-white">
              {status.announcements_today}
            </span>
          </div>
          <div className="text-slate-400">
            Rules loaded:{" "}
            <span className="font-medium text-white">
              {status.rules_active}
            </span>
          </div>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">
          Monitor Filter Rules ({rules.length})
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => reloadMut.mutate()}
            disabled={reloadMut.isPending}
            className="flex items-center gap-1 rounded-lg bg-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-600 transition"
          >
            <RefreshCw size={12} className={reloadMut.isPending ? "animate-spin" : ""} />
            Reload Monitor
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition"
          >
            <Plus size={14} />
            Add Rule
          </button>
        </div>
      </div>

      {/* ── Rules list ─────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : rules.length === 0 ? (
        <div className="rounded-xl border border-slate-700 bg-[#1e293b] py-12 text-center text-slate-500">
          No rules configured. All stocks above market cap threshold will be processed.
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule: MonitorRule) => (
            <div
              key={rule.id}
              className={clsx(
                "flex items-center justify-between rounded-xl border bg-[#1e293b] p-4 transition",
                rule.enabled
                  ? "border-slate-700"
                  : "border-slate-800 opacity-60"
              )}
            >
              <div className="flex items-center gap-4">
                <button
                  onClick={() =>
                    toggleMut.mutate({
                      id: rule.id,
                      enabled: !rule.enabled,
                    })
                  }
                  className="text-slate-400 hover:text-white"
                >
                  {rule.enabled ? (
                    <ToggleRight size={20} className="text-green-400" />
                  ) : (
                    <ToggleLeft size={20} />
                  )}
                </button>
                <div>
                  <div className="font-medium text-white">
                    {rule.name || `${rule.field} ${rule.operator} ${rule.value}`}
                  </div>
                  <div className="text-xs text-slate-500">
                    <span className="font-mono">{rule.field}</span>{" "}
                    <span className="text-blue-400">{rule.operator}</span>{" "}
                    <span className="font-mono">{rule.value}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => setDeleteTarget(rule.id)}
                className="rounded-lg bg-slate-700 p-2 text-red-400 hover:bg-red-900/30 transition"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Add Rule Modal ─────────────────────────────────────────────── */}
      {showAdd && (
        <AddRuleModal onClose={() => setShowAdd(false)} />
      )}

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete Rule"
        message="Remove this monitor rule?"
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

// ── Add Rule Modal ───────────────────────────────────────────────────────────

function AddRuleModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [field, setField] = useState("market_cap");
  const [operator, setOperator] = useState("gt");
  const [value, setValue] = useState("");
  const [label, setLabel] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createMonitorRule({ name: label || `${field} ${operator} ${value}`, field, operator, value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitor-rules"] });
      toast("Rule created", "success");
      onClose();
    },
    onError: (err: any) =>
      toast(err?.response?.data?.detail || "Failed to create rule", "error"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-[#1e293b] p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">New Monitor Rule</h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Label (optional)</label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Large cap only"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Field</label>
              <select
                value={field}
                onChange={(e) => setField(e.target.value)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              >
                {FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Operator</label>
              <select
                value={operator}
                onChange={(e) => setOperator(e.target.value)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              >
                {OPERATORS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Value</label>
              <input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="e.g. 10000"
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              />
            </div>
          </div>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !value}
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 transition disabled:opacity-50"
          >
            {mutation.isPending ? "Creating…" : "Create Rule"}
          </button>
        </div>
      </div>
    </div>
  );
}
