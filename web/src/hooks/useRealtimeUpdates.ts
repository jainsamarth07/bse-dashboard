import { useEffect, useRef, useState, useCallback } from "react";
import type { WsMessage } from "@/lib/types";

/**
 * Hook for real-time WebSocket updates from the API.
 * Falls back gracefully if WS is unavailable.
 */
export function useRealtimeUpdates(
  onMessage?: (msg: WsMessage) => void
) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;

    const token = localStorage.getItem("bse_token");
    if (!token) return;

    // When NEXT_PUBLIC_API_URL is set, use it directly (converts http→ws).
    // When empty (rewrite mode), derive from the current page origin so the
    // WS connection goes through the same tunnel/host — no CORS issues.
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
    let wsBase: string;
    if (apiUrl) {
      wsBase = apiUrl.replace(/^http/, "ws").replace(/\/$/, "");
    } else {
      // Same host as the page: https://xyz.trycloudflare.com → wss://xyz...
      wsBase = window.location.origin.replace(/^http/, "ws");
    }
    const url = `${wsBase}/ws/updates?token=${token}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (e) => {
        try {
          const msg: WsMessage = JSON.parse(e.data);
          onMessage?.(msg);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 30s to reduce server load and reconnect churn
        reconnectTimer.current = setTimeout(connect, 30000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      setConnected(false);
    }
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
