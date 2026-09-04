"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { getThemePreference, setThemePreference, THEME_CHANGE_EVENT, type ThemePreference } from "@/lib/theme";
import { Panel } from "./shared";

const options: Array<{ value: ThemePreference; label: string; description: string; icon: typeof Sun }> = [
  { value: "light", label: "Claro", description: "Fundo claro em todas as telas.", icon: Sun },
  { value: "dark", label: "Escuro", description: "Menos brilho em ambientes escuros.", icon: Moon },
  { value: "system", label: "Sistema", description: "Acompanha a configuração do aparelho.", icon: Monitor },
];

export function ThemeSettings() {
  const [preference, setPreference] = useState<ThemePreference>("system");

  useEffect(() => {
    const sync = () => setPreference(getThemePreference());
    sync();
    window.addEventListener(THEME_CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return <Panel title="Aparência">
    <fieldset>
      <legend className="text-sm text-zinc-400">Tema do aplicativo</legend>
      <div className="mt-3 grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Tema do aplicativo">
        {options.map(option => {
          const Icon = option.icon;
          const selected = preference === option.value;
          return <label key={option.value} className={`min-h-24 cursor-pointer rounded-xl border p-4 transition-colors ${selected ? "border-blue-500 bg-blue-500/10" : "border-zinc-700 hover:bg-zinc-900"}`}>
            <input className="sr-only" type="radio" name="theme" value={option.value} aria-label={option.label} checked={selected} onChange={() => { setThemePreference(option.value); setPreference(option.value); }} />
            <span className="flex items-center gap-2 text-sm font-medium"><Icon aria-hidden="true" size={18} />{option.label}</span>
            <span className="mt-2 block text-xs leading-relaxed text-zinc-400">{option.description}</span>
          </label>;
        })}
      </div>
    </fieldset>
    <p className="text-xs text-zinc-400">A preferência fica salva somente neste navegador e não contém dados do escritório.</p>
  </Panel>;
}
