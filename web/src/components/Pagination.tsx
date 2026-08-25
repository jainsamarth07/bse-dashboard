"use client";

import { clsx } from "clsx";

interface Props {
  page: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pages, total, onPageChange }: Props) {
  if (pages <= 1) return null;

  // Build visible page numbers
  const visible: (number | "...")[] = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || (i >= page - 1 && i <= page + 1)) {
      visible.push(i);
    } else if (visible[visible.length - 1] !== "...") {
      visible.push("...");
    }
  }

  return (
    <div className="flex items-center justify-between pt-4">
      <span className="text-xs text-slate-500">
        {total.toLocaleString()} total
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent"
        >
          ← Prev
        </button>
        {visible.map((v, i) =>
          v === "..." ? (
            <span key={`dots-${i}`} className="px-1 text-xs text-slate-500">
              …
            </span>
          ) : (
            <button
              key={v}
              onClick={() => onPageChange(v)}
              className={clsx(
                "rounded-lg px-3 py-1 text-xs font-medium transition",
                v === page
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              )}
            >
              {v}
            </button>
          )
        )}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          className="rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-30 disabled:hover:bg-transparent"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
