"use client";

import { useQuery } from "@tanstack/react-query";
import { useState, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { fetchStocks } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Pagination } from "@/components/Pagination";
import { formatMcap } from "@/lib/format";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { Search, Building2, ChevronsUpDown, ChevronUp, ChevronDown, ArrowUpRight } from "lucide-react";
import { clsx } from "clsx";
import type { Stock } from "@/lib/types";

const GROUPS = ["ALL", "A", "B", "T", "X", "XT", "Z", "M", "P"] as const;

type SortKey = "company_name" | "market_cap" | "group" | "industry";
type SortDir = "asc" | "desc";

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey; sortDir: SortDir }) {
  if (col !== sortKey) return <ChevronsUpDown size={11} className="opacity-30 ml-1" />;
  return sortDir === "asc"
    ? <ChevronUp size={11} className="text-blue-400 ml-1" />
    : <ChevronDown size={11} className="text-blue-400 ml-1" />;
}

export default function StocksPage() {
  const router = useRouter();
  const searchRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("ALL");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<SortKey>("market_cap");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const PAGE_SIZE = 50;

  const debouncedSearch = useDebouncedValue(search, 300);

  useKeyboardShortcuts([{ key: "k", ctrl: true }], useCallback(() => searchRef.current?.focus(), []));

  const { data, isLoading } = useQuery({
    queryKey: ["stocks", debouncedSearch, group, page],
    queryFn: () =>
      fetchStocks({
        page,
        page_size: PAGE_SIZE,
        search: debouncedSearch || undefined,
        group: group === "ALL" ? undefined : group,
      }),
  });

  const stocks = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  const sorted = useMemo(() => {
    return [...stocks].sort((a, b) => {
      let av: string | number = "";
      let bv: string | number = "";
      if (sortKey === "company_name") {
        av = a.company_name ?? "";
        bv = b.company_name ?? "";
      } else if (sortKey === "market_cap") {
        av = a.market_cap ?? 0;
        bv = b.market_cap ?? 0;
      } else if (sortKey === "group") {
        av = a.group ?? "";
        bv = b.group ?? "";
      } else if (sortKey === "industry") {
        av = a.industry ?? "";
        bv = b.industry ?? "";
      }
      if (typeof av === "string") {
        return sortDir === "asc" ? av.localeCompare(bv as string) : (bv as string).localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [stocks, sortKey, sortDir]);

  function handleSort(col: SortKey) {
    if (col === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(col);
      setSortDir("desc");
    }
  }

  return (
    <AppShell>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2.5 text-xl font-bold text-white">
            <Building2 size={20} className="text-blue-400" />
            Stocks
          </h1>
          <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
            {total.toLocaleString()} companies tracked
          </p>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl p-4" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)" }}>
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
          <input
            ref={searchRef}
            type="text"
            placeholder="Search stocks… (Ctrl+K)"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-64 rounded-lg py-2 pl-9 pr-4 text-[13px] outline-none focus:ring-1 focus:ring-blue-500/50"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }}
          />
        </div>

        <div className="flex gap-1 flex-wrap">
          {GROUPS.map((g) => (
            <button
              key={g}
              onClick={() => {
                setGroup(g);
                setPage(1);
              }}
              className={clsx("rounded-lg px-3 py-1.5 text-[11px] font-medium transition", group === g ? "bg-blue-600 text-white" : "hover:text-white")}
              style={group !== g ? { background: "var(--bg-elevated)", color: "var(--text-muted)" } : undefined}
            >
              {g}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded-xl py-20 text-center text-[13px]" style={{ background: "var(--bg-card)", border: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
          No stocks found matching your criteria.
        </div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl" style={{ border: "1px solid var(--border-subtle)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-subtle)" }}>
                  {([
                    { key: "company_name" as SortKey, label: "Company", align: "left" },
                    { key: "group" as SortKey, label: "Group", align: "left" },
                    { key: "industry" as SortKey, label: "Industry", align: "left" },
                    { key: "market_cap" as SortKey, label: "Market Cap", align: "right" },
                  ] as const).map(({ key, label, align }) => (
                    <th key={key} onClick={() => handleSort(key)} className={clsx("cursor-pointer select-none px-4 py-3", align === "right" ? "text-right" : "text-left")}>
                      <span className="inline-flex items-center text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>
                        {label}
                        <SortIcon col={key} sortKey={sortKey} sortDir={sortDir} />
                      </span>
                    </th>
                  ))}
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((s: Stock, idx) => (
                  <tr
                    key={s.scrip_code}
                    onClick={() => router.push(`/stocks/${s.scrip_code}`)}
                    className="cursor-pointer transition-colors"
                    style={{ borderBottom: "1px solid var(--border-subtle)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = idx % 2 === 0 ? "var(--bg-card)" : "transparent")}
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-white text-[13px]">{s.company_name}</div>
                      <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                        {s.scrip_code} · {s.scrip_name}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded px-2 py-0.5 text-[11px] font-medium" style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)" }}>
                        {s.group}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[13px]" style={{ color: "var(--text-secondary)" }}>
                      {s.industry || "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="font-mono font-semibold text-white text-[13px] tabular-nums">{formatMcap(s.market_cap)}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ArrowUpRight size={14} style={{ color: "var(--text-muted)" }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pages={pages} total={total} onPageChange={setPage} />
        </>
      )}
    </AppShell>
  );
}
