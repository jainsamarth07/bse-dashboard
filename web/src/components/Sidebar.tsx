"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  Rss,
  Building2,
  ArrowLeftRight,
  BarChart2,
  Wrench,
  Settings,
  LogOut,
  TrendingUp,
} from "lucide-react";
import { logout } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/",          label: "Dashboard",    icon: LayoutDashboard },
  { href: "/feed",      label: "Earnings Feed", icon: Rss           },
  { href: "/stocks",    label: "Stocks",        icon: Building2      },
  { href: "/trades",    label: "Trades",        icon: ArrowLeftRight },
  { href: "/analytics", label: "Analytics",     icon: BarChart2      },
  { href: "/tools",     label: "Tools",         icon: Wrench         },
  { href: "/settings",  label: "Settings",      icon: Settings       },
];

export function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-[220px] flex-col"
      style={{ background: "var(--bg-panel)", borderRight: "1px solid var(--border-subtle)" }}
    >
      {/* ── Logo ─────────────────────────────────────────────────────── */}
      <div className="flex h-[60px] shrink-0 items-center gap-2.5 border-b px-5"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
          <TrendingUp size={16} className="text-white" />
        </div>
        <div>
          <div className="text-[13px] font-bold leading-tight text-white">BSE Analyser</div>
          <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>Intelligence Platform</div>
        </div>
      </div>

      {/* ── Nav ──────────────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-muted)" }}
        >
          Navigation
        </div>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-150",
                active
                  ? "text-white"
                  : "hover:text-white"
              )}
              style={
                active
                  ? { background: "var(--bg-elevated)", color: "var(--text-primary)" }
                  : { color: "var(--text-secondary)" }
              }
            >
              {/* Active indicator bar */}
              {active && (
                <span
                  className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-blue-500"
                />
              )}
              <Icon size={16} className={clsx(active ? "text-blue-400" : "text-inherit")} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <div className="shrink-0 border-t p-3" style={{ borderColor: "var(--border-subtle)" }}>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-150 hover:text-red-400"
          style={{ color: "var(--text-secondary)" }}
        >
          <LogOut size={16} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
