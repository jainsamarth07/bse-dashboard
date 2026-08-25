"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/AppShell";
import { Pagination } from "@/components/Pagination";
import {
  fetchBseGainers,
  fetchBseLosers,
  fetchBseCalendar,
  fetchBseQuote,
  fetchBseActions,
  importEstimates,
  fetchEstimatesCount,
  apiDelete,
} from "@/lib/api";
import { toast } from "@/components/Toast";
import {
  Wrench, TrendingUp, TrendingDown, Calendar, Search,
  Activity, FileSpreadsheet, Upload, Trash2, ChevronRight, X,
} from "lucide-react";
import { clsx } from "clsx";

type ToolId = "gainers" | "losers" | "calendar" | "quote" | "actions" | "estimates";

const TOOLS: Array<{
  id: ToolId; label: string; description: string;
  icon: React.ElementType; color: string; bg: string;
}> = [
  { id: "gainers",   label: "Top Gainers",      description: "BSE500 top movers today",          icon: TrendingUp,      color: "text-green-400",  bg: "bg-green-500/10"  },
  { id: "losers",    label: "Top Losers",        description: "BSE500 bottom movers today",        icon: TrendingDown,    color: "text-red-400",    bg: "bg-red-500/10"    },
  { id: "calendar",  label: "Result Calendar",   description: "Upcoming result announcement dates",icon: Calendar,        color: "text-blue-400",   bg: "bg-blue-500/10"   },
  { id: "quote",     label: "Quote Lookup",      description: "OHLC + volume for any BSE scrip",  icon: Search,          color: "text-amber-400",  bg: "bg-amber-500/10"  },
  { id: "actions",   label: "Corp Actions",      description: "Dividends, bonus, splits",          icon: Activity,        color: "text-violet-400", bg: "bg-violet-500/10" },
  { id: "estimates", label: "Estimates Upload",  description: "Import analyst estimates (xlsx)",   icon: FileSpreadsheet, color: "text-emerald-400",bg: "bg-emerald-500/10"},
];

function ToolInput({ label, value, onChange, onSubmit, loading, placeholder }: {
  label: string; value: string; onChange: (v: string) => void;
  onSubmit: () => void; loading?: boolean; placeholder?: string;
}) {
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="mb-4 flex gap-2">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "Enter BSE scrip code…"}
        className="flex-1 rounded-lg py-2 px-3 text-[13px] outline-none focus:ring-1 focus:ring-blue-500/50"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
      />
      <button type="submit" disabled={loading} className="rounded-lg bg-blue-600 px-5 py-2 text-[13px] font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50">
        {loading ? "…" : label}
      </button>
    </form>
  );
}

function ToolTable({ cols, rows }: { cols: string[]; rows: (string | number | null)[][] }) {
  return (
    <div className="overflow-hidden rounded-xl" style={{ border: "1px solid var(--border-subtle)" }}>
      <table className="w-full text-[13px]">
        <thead>
          <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-subtle)" }}>
            {cols.map((c) => (
              <th key={c} className="px-4 py-2.5 text-left">
                <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>{c}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: "1px solid var(--border-subtle)" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "")}>
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2.5" style={{ color: "var(--text-secondary)" }}>
                  {cell !== null && cell !== undefined ? String(cell) : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
    </div>
  );
}

function GainersLosersPanel({ type }: { type: "gainers" | "losers" }) {
  const { data, isLoading } = useQuery({
    queryKey: [`bse-${type}`],
    queryFn: () => type === "gainers" ? fetchBseGainers("index", "BSE500") : fetchBseLosers("index", "BSE500"),
  });
  const items = Array.isArray(data) ? data : [];
  if (isLoading) return <Spinner />;
  if (!items.length) return <p className="py-8 text-center text-[13px]" style={{ color: "var(--text-muted)" }}>No data available</p>;
  return (
    <ToolTable
      cols={["Company", "LTP", "Change %", "Open", "High", "Low"]}
      rows={items.slice(0, 25).map((item: Record<string, unknown>) => [
        String(item.ScripName || item.LongName || ""),
        Number(item.LTP || 0).toLocaleString("en-IN"),
        `${Number(item.Chg || 0) >= 0 ? "+" : ""}${Number(item.Chg || 0).toFixed(2)}%`,
        Number(item.Open || 0).toLocaleString("en-IN"),
        Number(item.High || 0).toLocaleString("en-IN"),
        Number(item.Low  || 0).toLocaleString("en-IN"),
      ])}
    />
  );
}

function CalendarPanel() {
  const [page, setPage] = useState(1);
  const pageSize = 50;
  const { data, isLoading } = useQuery({ queryKey: ["bse-calendar"], queryFn: fetchBseCalendar });
  const items = Array.isArray(data) ? data : [];
  if (isLoading) return <Spinner />;
  if (!items.length) return <p className="py-8 text-center text-[13px]" style={{ color: "var(--text-muted)" }}>No upcoming result dates</p>;

  const total = items.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, pages);
  const start = (safePage - 1) * pageSize;
  const end = start + pageSize;
  const visible = items.slice(start, end);

  return (
    <div>
      <ToolTable
        cols={["Company", "Date", "Purpose"]}
        rows={visible.map((item: Record<string, unknown>) => [
          String(item.Long_Name || item.long_name || item.short_name || item.ScripName || ""),
          String(item.meeting_date || item.MeetingDate || item.date || ""),
          String(item.Purpose || item.purpose || "Result Date"),
        ])}
      />
      <Pagination page={safePage} pages={pages} total={total} onPageChange={setPage} />
    </div>
  );
}

function QuotePanel() {
  const [code, setCode] = useState("");
  const [lookupCode, setLookup] = useState("");
  const { data: quote, isLoading } = useQuery({
    queryKey: ["bse-quote", lookupCode],
    queryFn: () => fetchBseQuote(lookupCode),
    enabled: !!lookupCode,
    retry: false,
  });
  return (
    <div>
      <ToolInput label="Lookup" value={code} onChange={setCode} onSubmit={() => code.trim() && setLookup(code.trim())} loading={isLoading} placeholder="BSE scrip code e.g. 500325" />
      {isLoading && <Spinner />}
      {quote && !isLoading && (
        <div className="rounded-xl p-5" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}>
          <div className="mb-4 text-[15px] font-semibold text-white">
            {String((quote as Record<string, unknown>).CmpName || (quote as Record<string, unknown>).ScripName || lookupCode)}
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {([
              ["Open",      (quote as Record<string, unknown>).Open],
              ["High",      (quote as Record<string, unknown>).High],
              ["Low",       (quote as Record<string, unknown>).Low],
              ["Close",     (quote as Record<string, unknown>).CurrRate || (quote as Record<string, unknown>).Close],
              ["Prev Close",(quote as Record<string, unknown>).PrevClose],
              ["Change",    (quote as Record<string, unknown>).Change],
              ["Change %",  (quote as Record<string, unknown>).PerChange],
              ["Volume",    (quote as Record<string, unknown>).TtlTrdVol || (quote as Record<string, unknown>).Volume],
            ] as [string, unknown][]).map(([label, val]) => (
              <div key={label} className="rounded-xl p-3" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}>
                <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{label}</div>
                <div className="mt-1 font-mono font-semibold text-white tabular-nums">
                  {val !== undefined && val !== null ? Number(val).toLocaleString("en-IN") : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ActionsPanel() {
  const [code, setCode] = useState("");
  const [lookupCode, setLookup] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["bse-actions", lookupCode],
    queryFn: () => fetchBseActions(lookupCode || undefined),
    enabled: !!lookupCode,
    retry: false,
  });
  const items = Array.isArray(data) ? data : [];
  return (
    <div>
      <ToolInput label="Search" value={code} onChange={setCode} onSubmit={() => code.trim() && setLookup(code.trim())} loading={isLoading} placeholder="BSE scrip code e.g. 500325" />
      {isLoading && <Spinner />}
      {items.length > 0 && !isLoading && (
        <ToolTable
          cols={["Company", "Purpose", "Ex Date", "Record Date"]}
          rows={items.slice(0, 30).map((item: Record<string, unknown>) => [
            String(item.CompanyName || item.scrip_name || ""),
            String(item.Purpose     || item.purpose    || ""),
            String(item.ExDate      || item.ex_date    || "—"),
            String(item.RecordDate  || item.record_date || "—"),
          ])}
        />
      )}
    </div>
  );
}

function EstimatesPanel() {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const { data: countData } = useQuery({ queryKey: ["estimates-count"], queryFn: fetchEstimatesCount });

  const importMutation = useMutation({
    mutationFn: (file: File) => importEstimates(file),
    onSuccess: (data: { imported: number; message: string }) => {
      toast(data.message || `Imported ${data.imported} estimates`, "success");
      queryClient.invalidateQueries({ queryKey: ["estimates-count"] });
    },
    onError: () => toast("Failed to import estimates", "error"),
  });

  const clearMutation = useMutation({
    mutationFn: () => apiDelete("/api/estimates"),
    onSuccess: () => {
      toast("All estimates cleared", "success");
      queryClient.invalidateQueries({ queryKey: ["estimates-count"] });
    },
    onError: () => toast("Failed to clear estimates", "error"),
  });

  function handleFile(file: File) {
    if (!file.name.endsWith(".xlsx")) { toast("Only .xlsx files are supported", "error"); return; }
    importMutation.mutate(file);
  }

  const count: number = (countData as { count?: number })?.count ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between rounded-xl p-4" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}>
        <div>
          <div className="text-[13px] font-semibold text-white">Analyst Estimates</div>
          <div className="mt-0.5 text-[12px]" style={{ color: "var(--text-muted)" }}>
            {count > 0 ? `${count} companies loaded — Beat/Miss/In-Line comparison active` : "No estimates loaded — upload your sheet to enable comparison"}
          </div>
        </div>
        {count > 0 && (
          <button onClick={() => clearMutation.mutate()} disabled={clearMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium text-red-400 transition hover:bg-red-500/10 disabled:opacity-50"
            style={{ border: "1px solid rgba(239,68,68,0.3)" }}>
            <Trash2 size={12} /> Clear All
          </button>
        )}
      </div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
        onClick={() => fileRef.current?.click()}
        className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition"
        style={{ borderColor: dragOver ? "#3b82f6" : "var(--border-strong)", background: dragOver ? "rgba(59,130,246,0.05)" : "transparent" }}
      >
        <Upload size={28} style={{ color: dragOver ? "#3b82f6" : "var(--text-muted)" }} />
        <div>
          <div className="text-[14px] font-semibold text-white">{importMutation.isPending ? "Importing…" : "Drop estimates .xlsx here"}</div>
          <div className="mt-1 text-[12px]" style={{ color: "var(--text-muted)" }}>or click to browse · Excel format with "Est vs Actuals" sheet</div>
        </div>
        <div className="mt-1 rounded-lg px-4 py-2 text-[11px] max-w-md" style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}>
          Col C: BSE Code · D: Company · G: Sector · J: Est Revenue · S: Est EBITDA · AD: Est PAT
        </div>
      </div>
      <input ref={fileRef} type="file" accept=".xlsx" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
      />
    </div>
  );
}

export default function ToolsPage() {
  const [active, setActive] = useState<ToolId | null>(null);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="flex items-center gap-2.5 text-xl font-bold text-white">
          <Wrench size={20} className="text-blue-400" />
          BSE Toolbox
        </h1>
        <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>Market data tools and utilities</p>
      </div>

      {active ? (
        <div>
          <button onClick={() => setActive(null)} className="mb-5 flex items-center gap-2 text-[13px] transition hover:text-white" style={{ color: "var(--text-muted)" }}>
            <X size={14} /> Back to Toolbox
          </button>
          {(() => {
            const tool = TOOLS.find((t) => t.id === active)!;
            const Icon = tool.icon;
            return (
              <div className="mb-5 flex items-center gap-3">
                <div className={clsx("flex h-10 w-10 items-center justify-center rounded-xl", tool.bg)}>
                  <Icon size={18} className={tool.color} />
                </div>
                <div>
                  <div className="text-[16px] font-bold text-white">{tool.label}</div>
                  <div className="text-[12px]" style={{ color: "var(--text-muted)" }}>{tool.description}</div>
                </div>
              </div>
            );
          })()}
          {active === "gainers"   && <GainersLosersPanel type="gainers" />}
          {active === "losers"    && <GainersLosersPanel type="losers"  />}
          {active === "calendar"  && <CalendarPanel />}
          {active === "quote"     && <QuotePanel />}
          {active === "actions"   && <ActionsPanel />}
          {active === "estimates" && <EstimatesPanel />}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((tool) => {
            const Icon = tool.icon;
            return (
              <button
                key={tool.id}
                onClick={() => setActive(tool.id)}
                className="group flex items-center gap-4 rounded-xl p-5 text-left transition-all duration-150 hover:scale-[1.01]"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
              >
                <div className={clsx("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl", tool.bg)}>
                  <Icon size={22} className={tool.color} />
                </div>
                <div className="flex-1">
                  <div className="text-[14px] font-semibold text-white">{tool.label}</div>
                  <div className="mt-0.5 text-[12px]" style={{ color: "var(--text-muted)" }}>{tool.description}</div>
                </div>
                <ChevronRight size={16} className="shrink-0 transition group-hover:translate-x-0.5" style={{ color: "var(--text-muted)" }} />
              </button>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
