"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search, Bell, ChevronDown, User, LogOut } from "lucide-react";
import { LiveIndicator } from "./LiveIndicator";
import { logout } from "@/lib/api";
import { clsx } from "clsx";

interface Props {
  wsConnected?: boolean;
  newResultCount?: number;
  onSearch?: (q: string) => void;
}

function isMarketOpen(): boolean {
  const now = new Date();
  // IST = UTC+5:30
  const utcMs  = now.getTime() + now.getTimezoneOffset() * 60_000;
  const ist    = new Date(utcMs + 5.5 * 3_600_000);
  const h      = ist.getHours();
  const m      = ist.getMinutes();
  const day    = ist.getDay(); // 0=Sun 6=Sat
  if (day === 0 || day === 6) return false;
  const minutes = h * 60 + m;
  return minutes >= 555 && minutes <= 930; // 9:15 – 15:30
}

export function TopBar({ wsConnected, newResultCount = 0, onSearch }: Props) {
  const router      = useRouter();
  const [search, setSearch]   = useState("");
  const [userOpen, setUserOpen] = useState(false);
  const inputRef    = useRef<HTMLInputElement>(null);
  const open        = isMarketOpen();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header
      className="fixed z-40 flex h-[60px] items-center justify-between px-5 gap-4"
      style={{
        left: "220px",
        right: "280px",
        top: 0,
        background: "var(--bg-panel)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      {/* ── Global search ────────────────────────────────────────────── */}
      <div className="relative flex-1 max-w-md">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: "var(--text-muted)" }}
        />
        <input
          ref={inputRef}
          type="text"
          placeholder="Search company or scrip code…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            onSearch?.(e.target.value);
          }}
          className="w-full rounded-lg py-2 pl-9 pr-4 text-[13px] outline-none focus:ring-1 focus:ring-blue-500/50 transition"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            color: "var(--text-primary)",
          }}
        />
      </div>

      {/* ── Right controls ───────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        {/* Market status pill */}
        <div
          className={clsx(
            "flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide",
            open
              ? "bg-green-500/10 text-green-400"
              : "bg-slate-700/50 text-slate-500"
          )}
        >
          <span className={clsx("h-1.5 w-1.5 rounded-full", open ? "bg-green-400 animate-pulse" : "bg-slate-500")} />
          {open ? "Market Open" : "Market Closed"}
        </div>

        {/* WS live indicator */}
        <LiveIndicator connected={wsConnected} label={wsConnected ? "Live" : "Offline"} />

        {/* Notification bell */}
        <button
          className="relative rounded-lg p-2 transition hover:bg-white/5"
          style={{ color: "var(--text-secondary)" }}
        >
          <Bell size={18} />
          {newResultCount > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-[9px] font-bold text-white">
              {newResultCount > 9 ? "9+" : newResultCount}
            </span>
          )}
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setUserOpen((v) => !v)}
            className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-[13px] transition hover:bg-white/5"
            style={{ color: "var(--text-secondary)" }}
          >
            <div
              className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600/30 text-blue-400"
            >
              <User size={14} />
            </div>
            <ChevronDown size={12} />
          </button>
          {userOpen && (
            <div
              className="absolute right-0 top-full mt-1 w-40 rounded-xl border py-1 shadow-2xl"
              style={{
                background: "var(--bg-elevated)",
                borderColor: "var(--border-default)",
              }}
            >
              <button
                onClick={() => { setUserOpen(false); router.push("/settings"); }}
                className="flex w-full items-center gap-2 px-4 py-2 text-[13px] transition hover:bg-white/5"
                style={{ color: "var(--text-secondary)" }}
              >
                <User size={14} /> Settings
              </button>
              <div className="my-1 border-t" style={{ borderColor: "var(--border-subtle)" }} />
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-4 py-2 text-[13px] text-red-400 transition hover:bg-red-500/10"
              >
                <LogOut size={14} /> Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
