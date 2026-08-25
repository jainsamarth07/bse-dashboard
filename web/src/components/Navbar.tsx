"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clsx } from "clsx";
import {
  Building2,
  Wrench,
  Settings,
  ArrowLeftRight,
  LayoutDashboard,
  LogOut,
} from "lucide-react";
import { LiveIndicator } from "./LiveIndicator";
import { logout } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/stocks", label: "Stocks", icon: Building2 },
  { href: "/trades", label: "Trades", icon: ArrowLeftRight },
  { href: "/tools", label: "BSE Tools", icon: Wrench },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface Props {
  wsConnected?: boolean;
}

export function Navbar({ wsConnected }: Props) {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-slate-700 bg-[#0f172a]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        {/* ── Logo ─────────────────────────────────────────────────────── */}
        <Link href="/" className="flex items-center gap-3">
          <span className="text-2xl">📊</span>
          <h1 className="text-lg font-bold text-white">BSE Result Analyser</h1>
        </Link>

        {/* ── Nav links ────────────────────────────────────────────────── */}
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition",
                  active
                    ? "bg-slate-700/60 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                )}
              >
                <Icon size={16} />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
          <div className="ml-3 flex items-center gap-3">
            <LiveIndicator
              connected={wsConnected}
              label={wsConnected ? "Live" : "Offline"}
            />
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-red-400 transition"
              title="Sign out"
            >
              <LogOut size={16} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </nav>
      </div>
    </header>
  );
}
