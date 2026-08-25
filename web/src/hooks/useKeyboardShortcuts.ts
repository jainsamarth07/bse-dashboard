import { useEffect } from "react";

type Handler = () => void;
type Shortcut = { key: string; ctrl?: boolean; meta?: boolean; shift?: boolean };

/**
 * Global keyboard shortcuts.
 * Usage: useKeyboardShortcuts([{ key: "k", ctrl: true }], handler)
 */
export function useKeyboardShortcuts(
  shortcuts: Shortcut[],
  handler: Handler
) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      for (const sc of shortcuts) {
        const ctrlMatch = sc.ctrl ? e.ctrlKey || e.metaKey : true;
        const metaMatch = sc.meta ? e.metaKey : true;
        const shiftMatch = sc.shift ? e.shiftKey : true;

        if (
          e.key.toLowerCase() === sc.key.toLowerCase() &&
          ctrlMatch &&
          metaMatch &&
          shiftMatch
        ) {
          e.preventDefault();
          handler();
          return;
        }
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [shortcuts, handler]);
}
