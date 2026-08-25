"use client";

import { create } from "zustand";
import { useEffect } from "react";
import { clsx } from "clsx";

// ── Toast store (Zustand) ────────────────────────────────────────────────────

export interface ToastItem {
  id: string;
  message: string;
  type: "success" | "error" | "info" | "warning";
}

interface ToastState {
  toasts: ToastItem[];
  addToast: (t: Omit<ToastItem, "id">) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (t) => {
    const id = Math.random().toString(36).slice(2, 9);
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }));
    // Auto-remove after 4s
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) }));
    }, 4000);
  },
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));

/** Convenience function — call from anywhere */
export function toast(message: string, type: ToastItem["type"] = "info") {
  useToastStore.getState().addToast({ message, type });
}

// ── Renderer ─────────────────────────────────────────────────────────────────

const TYPE_STYLES: Record<string, string> = {
  success: "border-green-500/50 bg-green-500/10 text-green-300",
  error: "border-red-500/50 bg-red-500/10 text-red-300",
  warning: "border-amber-500/50 bg-amber-500/10 text-amber-300",
  info: "border-blue-500/50 bg-blue-500/10 text-blue-300",
};

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={clsx(
            "flex items-center gap-3 rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur-sm animate-in slide-in-from-right",
            TYPE_STYLES[t.type] || TYPE_STYLES.info
          )}
        >
          <span className="flex-1">{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            className="text-inherit opacity-60 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
