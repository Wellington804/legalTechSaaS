"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Bot, LogOut, Monitor, Moon, Search, Sun } from "lucide-react";
import { useUser } from "@/context/user-context";
import { navigationItemForPath } from "@/lib/navigation";
import { getThemePreference, setThemePreference, THEME_CHANGE_EVENT, type ThemePreference } from "@/lib/theme";

const themes: ThemePreference[] = ["light", "dark", "system"];
const themeLabels: Record<ThemePreference, string> = { light: "Claro", dark: "Escuro", system: "Sistema" };
const themeIcons = { light: Sun, dark: Moon, system: Monitor };

export function Header() {
  const { user, logout } = useUser(); const pathname = usePathname();
  const [theme, setTheme] = useState<ThemePreference>("system");
  const current = navigationItemForPath(pathname);
  useEffect(() => {
    const sync = () => setTheme(getThemePreference());
    sync(); window.addEventListener(THEME_CHANGE_EVENT, sync); window.addEventListener("storage", sync);
    return () => { window.removeEventListener(THEME_CHANGE_EVENT, sync); window.removeEventListener("storage", sync); };
  }, []);
  const nextTheme = themes[(themes.indexOf(theme) + 1) % themes.length];
  const ThemeIcon = themeIcons[theme];
  return <header className="h-16 shrink-0 border-b border-zinc-800/80 bg-zinc-950/95 sticky top-0 z-30 px-4 md:px-6 flex items-center justify-between gap-3">
    <div className="min-w-0"><p className="text-sm font-medium truncate md:hidden">{current?.shortName || "LexFlow"}</p><p className="hidden md:block text-sm text-zinc-400 truncate">{current?.name || "Central do Advogado"}</p></div>
    <div className="flex min-w-0 items-center gap-2">
      <button type="button" onClick={() => window.dispatchEvent(new CustomEvent("lexflow:open-ai"))} className="hidden min-h-11 min-w-11 items-center justify-center gap-2 rounded-xl px-3 text-sm text-blue-300 hover:bg-zinc-900 md:inline-flex" aria-label="Abrir Assistente LexFlow"><Bot aria-hidden="true" size={17} /><span className="hidden lg:inline">Assistente</span></button>
      <button type="button" aria-label="Buscar" onClick={() => window.dispatchEvent(new Event("lexflow:open-search"))} className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-xl px-2 text-sm text-zinc-300 hover:bg-zinc-900 md:px-3"><Search aria-hidden="true" size={17} /><span className="hidden sm:inline">Buscar</span><kbd className="hidden text-xs text-zinc-500 md:inline">Ctrl K</kbd></button>
      <button type="button" onClick={() => setThemePreference(nextTheme)} aria-label={`Aparência: ${themeLabels[theme]}. Alterar para ${themeLabels[nextTheme]}`} title={`Aparência: ${themeLabels[theme]}`} className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-2 rounded-xl px-2 text-sm text-zinc-300 hover:bg-zinc-900 md:px-3"><ThemeIcon aria-hidden="true" size={18} /><span className="hidden xl:inline">{themeLabels[theme]}</span></button>
      <Link href="/dashboard/account" className="min-w-0 min-h-11 flex items-center text-sm text-zinc-300 truncate max-w-40">{user.name}</Link>
      <button onClick={() => void logout()} title="Sair" aria-label="Sair da conta" className="min-h-11 min-w-11 shrink-0 grid place-items-center rounded-xl text-zinc-400 hover:bg-zinc-900 hover:text-white"><LogOut aria-hidden="true" size={18} /></button>
    </div>
  </header>;
}
