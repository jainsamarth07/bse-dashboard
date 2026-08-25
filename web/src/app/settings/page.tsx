"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Settings as SettingsIcon, Key, Radio } from "lucide-react";
import { clsx } from "clsx";
import { GeneralTab } from "./GeneralTab";
import { BrokersTab } from "./BrokersTab";
import { MonitorTab } from "./MonitorTab";

type Tab = "general" | "brokers" | "monitor";

const TABS: { key: Tab; label: string; icon: React.ElementType }[] = [
  { key: "general", label: "General", icon: SettingsIcon },
  { key: "brokers", label: "Broker Keys", icon: Key },
  { key: "monitor", label: "Monitor Rules", icon: Radio },
];

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("general");

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <div className="mb-6">
          <h1 className="flex items-center gap-2.5 text-xl font-bold text-white">
            <SettingsIcon size={20} className="text-blue-400" />
            Settings
          </h1>
          <p className="mt-0.5 text-[13px]" style={{ color: "var(--text-muted)" }}>
            Configure brokers, monitor rules, and application preferences
          </p>
        </div>

        {/* ── Tabs ──────────────────────────────────────────────────────── */}
        <div className="mb-6 flex gap-1 border-b" style={{ borderColor: "var(--border-subtle)" }}>
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={clsx(
                "flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-medium transition border-b-2",
                tab === key ? "border-blue-500 text-white" : "border-transparent hover:text-white"
              )}
              style={{ color: tab === key ? "var(--text-primary)" : "var(--text-muted)" }}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {tab === "general" && <GeneralTab />}
        {tab === "brokers" && <BrokersTab />}
        {tab === "monitor" && <MonitorTab />}
      </div>
    </AppShell>
  );
}
