"use client";

import { clsx } from "clsx";

interface Props {
  connected?: boolean;
  label?: string;
  className?: string;
}

export function LiveIndicator({
  connected = true,
  label,
  className,
}: Props) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 text-xs", className)}>
      <span
        className={clsx(
          "h-2 w-2 rounded-full",
          connected
            ? "bg-green-400 shadow-[0_0_6px_rgba(34,197,94,0.6)] animate-pulse"
            : "bg-slate-500"
        )}
      />
      {label && (
        <span className={connected ? "text-green-400" : "text-slate-500"}>
          {label}
        </span>
      )}
    </span>
  );
}
