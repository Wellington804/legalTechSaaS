"use client";

import { useEffect } from "react";

export interface ShortcutMap {
  [key: string]: () => void;
}

export function useKeyboardShortcuts(shortcuts: ShortcutMap) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isCmdOrCtrl = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();

      // Check if target is editable input
      const target = event.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      // Allow Cmd/Ctrl + K even inside inputs
      if (isCmdOrCtrl && key === "k") {
        if (shortcuts["cmd+k"]) {
          event.preventDefault();
          shortcuts["cmd+k"]();
          return;
        }
      }

      if (isInput) return;

      if (isCmdOrCtrl) {
        const combo = `cmd+${key}`;
        if (shortcuts[combo]) {
          event.preventDefault();
          shortcuts[combo]();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [shortcuts]);
}
