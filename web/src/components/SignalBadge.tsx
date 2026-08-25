"use client";

import { clsx } from "clsx";
import { SIGNAL_STYLES } from "@/lib/format";
import type { Signal } from "@/lib/types";

interface Props {
  signal: Signal;
  size?: "sm" | "md";
  className?: string;
}

export function SignalBadge({ signal, size = "sm", className }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border font-bold uppercase",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        SIGNAL_STYLES[signal] || SIGNAL_STYLES.NEUTRAL,
        className
      )}
    >
      {signal}
    </span>
  );
}
