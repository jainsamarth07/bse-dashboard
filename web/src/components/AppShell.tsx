"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { AICopilot } from "@/components/AICopilot";
import { useRealtimeUpdates } from "@/hooks/useRealtimeUpdates";
import { toast } from "@/components/Toast";
import type { WsMessage } from "@/lib/types";

interface Props {
  children: React.ReactNode;
}

export function AppShell({ children }: Props) {
  const router       = useRouter();
  const queryClient  = useQueryClient();
  const [checked, setChecked]               = useState(false);
  const [newResultCount, setNewResultCount] = useState(0);
  const [signalFilter, setSignalFilter]     = useState<string | null>(null);

  // Auth guard
  useEffect(() => {
    const token = localStorage.getItem("bse_token");
    if (!token) {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [router]);

  const handleWsMessage = useCallback(
    (msg: WsMessage) => {
      if (msg.event === "new_result" || msg.event === "updated_result" || msg.event === "deleted_result") {
        queryClient.invalidateQueries({ queryKey: ["results"] });
        if (msg.event === "new_result") {
          setNewResultCount((n) => n + 1);
          const name = (msg.data?.scrip_name as string) || "New";
          toast(`${name} — new result analysed`, "success");
        }
      }
    },
    [queryClient]
  );

  const { connected } = useRealtimeUpdates(handleWsMessage);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ background: "var(--bg-app)" }}>
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      {/* Fixed left sidebar */}
      <Sidebar />

      {/* Fixed top bar */}
      <TopBar
        wsConnected={connected}
        newResultCount={newResultCount}
        onSearch={() => {}}
      />

      {/* Fixed right AI copilot */}
      <AICopilot onFilterSignal={(s) => setSignalFilter(s)} />

      {/* Scrollable main content — inset by sidebar + topbar + copilot */}
      <main
        className="min-h-screen overflow-y-auto"
        style={{
          marginLeft:  "220px",
          marginRight: "280px",
          paddingTop:  "60px",
        }}
      >
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
