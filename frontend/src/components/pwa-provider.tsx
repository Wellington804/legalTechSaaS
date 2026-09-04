"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useUser } from "@/context/user-context";
import { pwaRegistration, reconcileBrowserPush } from "@/lib/pwa";

interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}
interface PwaState {
  registration: ServiceWorkerRegistration | null;
  installPrompt: InstallEvent | null;
  installed: boolean;
  ios: boolean;
  supported: boolean;
  ready: boolean;
  error: string;
  install: () => Promise<void>;
}
const PwaContext = createContext<PwaState | null>(null);

export function PwaProvider({ children }: { children: ReactNode }) {
  const { isLoggedIn, user } = useUser();
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [installPrompt, setInstallPrompt] = useState<InstallEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [ios, setIos] = useState(false);
  const [supported, setSupported] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);
  const [updating, setUpdating] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const wantsReload = useRef(false);

  useEffect(() => {
    const display = window.matchMedia("(display-mode: standalone)");
    const syncInstalled = () => setInstalled(display.matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
    syncInstalled();
    setIos(/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
    display.addEventListener("change", syncInstalled);
    const prompt = (event: Event) => { event.preventDefault(); setInstallPrompt(event as InstallEvent); };
    const complete = () => { setInstalled(true); setInstallPrompt(null); };
    window.addEventListener("beforeinstallprompt", prompt);
    window.addEventListener("appinstalled", complete);
    const available = window.isSecureContext && "serviceWorker" in navigator;
    setSupported(available);
    let active = true;
    let registered: ServiceWorkerRegistration | null = null;
    const refresh = () => {
      if (!active) return;
      setReady(Boolean(registered?.active));
      if (registered?.waiting) { setWaiting(registered.waiting); setDismissed(false); }
    };
    const updateFound = () => {
      const worker = registered?.installing;
      worker?.addEventListener("statechange", refresh);
    };
    const controllerChanged = () => {
      if (wantsReload.current) window.location.reload();
      else setWaiting(null);
    };
    if (available) {
      navigator.serviceWorker.addEventListener("controllerchange", controllerChanged);
      pwaRegistration().then(result => {
        if (!active) return;
        registered = result; setRegistration(result); refresh(); updateFound();
        result.addEventListener("updatefound", updateFound);
      }).catch(() => { if (active) setError("Não foi possível preparar o aplicativo. Recarregue quando estiver conectado."); });
    }
    return () => {
      active = false;
      display.removeEventListener("change", syncInstalled);
      window.removeEventListener("beforeinstallprompt", prompt);
      window.removeEventListener("appinstalled", complete);
      registered?.removeEventListener("updatefound", updateFound);
      if (available) navigator.serviceWorker.removeEventListener("controllerchange", controllerChanged);
    };
  }, []);

  useEffect(() => {
    if (registration && ready && isLoggedIn && user.id) {
      // A transient backend failure must not discard an existing browser subscription.
      reconcileBrowserPush(registration).catch(() => {});
    }
  }, [registration, ready, isLoggedIn, user.id]);

  async function install() {
    if (!installPrompt) return;
    try {
      await installPrompt.prompt();
      await installPrompt.userChoice;
    } finally { setInstallPrompt(null); }
  }

  return <PwaContext.Provider value={{ registration, installPrompt, installed, ios, supported, ready, error, install }}>
    {children}
    {waiting && !dismissed && <aside role="status" aria-label="Atualização do aplicativo" className="fixed z-[70] bottom-20 md:bottom-4 left-3 right-3 md:left-auto md:max-w-md rounded-xl border border-blue-700 bg-zinc-950 p-4 shadow-xl space-y-3">
      <p className="text-sm">Há uma atualização do LexFlow. Salve o que estiver editando antes de recarregar.</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={updating} className="min-h-11 rounded-lg bg-blue-600 px-3 py-2 text-sm disabled:opacity-50" onClick={() => {
          setUpdating(true); wantsReload.current = true; waiting.postMessage({ type: "ACTIVATE_UPDATE" });
        }}>{updating ? "Atualizando…" : "Salvei, atualizar agora"}</button>
        <button type="button" disabled={updating} className="min-h-11 rounded-lg border border-zinc-700 px-3 py-2 text-sm" onClick={() => setDismissed(true)}>Mais tarde</button>
      </div>
    </aside>}
  </PwaContext.Provider>;
}

export function usePwa() {
  const context = useContext(PwaContext);
  if (!context) throw new Error("usePwa deve ser usado dentro de PwaProvider");
  return context;
}
