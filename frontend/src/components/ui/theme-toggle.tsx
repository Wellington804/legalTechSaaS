"use client";

import React from "react";
import { useTheme } from "@/context/theme-context";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      type="button"
      className={`px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 hover:border-blue-500 dark:hover:border-amber-400 transition-all cursor-pointer shadow-md flex items-center gap-2 text-xs font-semibold select-none ${className}`}
      title={`Alternar para modo ${theme === "dark" ? "Claro (Light)" : "Escuro (Dark)"}`}
    >
      {theme === "dark" ? (
        <>
          <Sun className="w-4 h-4 text-amber-400" />
          <span className="font-mono text-[11px] text-zinc-200">Modo Escuro</span>
        </>
      ) : (
        <>
          <Moon className="w-4 h-4 text-blue-600" />
          <span className="font-mono text-[11px] text-zinc-800 font-bold">Modo Claro</span>
        </>
      )}
    </button>
  );
}

