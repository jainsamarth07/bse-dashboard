"use client";

import { clsx } from "clsx";

interface Column<T> {
  key: string;
  header: string;
  className?: string;
  render: (row: T) => React.ReactNode;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  loading?: boolean;
}

export function DataTable<T>({
  columns,
  data,
  keyFn,
  onRowClick,
  emptyMessage = "No data",
  loading,
}: Props<T>) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="py-16 text-center text-slate-500">{emptyMessage}</div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 bg-slate-800/50">
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(
                  "px-4 py-3 text-left text-xs font-medium uppercase text-slate-400",
                  col.className
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={keyFn(row)}
              onClick={() => onRowClick?.(row)}
              className={clsx(
                "border-b border-slate-700/50 transition",
                onRowClick
                  ? "cursor-pointer hover:bg-slate-800/50"
                  : ""
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={clsx("px-4 py-3 text-slate-300", col.className)}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
