"use client";
import { cloneElement, isValidElement, useCallback, useEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { api, apiBlob, API_BASE_URL, SESSION_RESTORED_EVENT } from "@/lib/api-client";
import { formatBrazilianPhone } from "@/lib/phone";
import { useUser } from "@/context/user-context";
import Link from "next/link";
import { ArrowLeft, ChevronDown } from "lucide-react";

export const control = "w-full min-w-0 min-h-11 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-base md:text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500";
export const button = "inline-flex min-h-11 max-w-full items-center justify-center rounded-lg border border-zinc-700 px-3 py-2 text-sm text-center text-zinc-200 hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed";
export const primary = `${button} bg-blue-600 border-blue-500 hover:bg-blue-500 text-white`;
export function errorText(error: unknown) { return error instanceof Error ? error.message : "Não foi possível concluir a operação."; }
export function dateText(value: unknown) { if (!value) return "—"; if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) return String(value).split("-").reverse().join("/"); const date = new Date(String(value)); return Number.isNaN(date.valueOf()) ? "—" : date.toLocaleString("pt-BR"); }
export function money(value: unknown) { return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0)); }
export function scrollWorkspaceToTop() { document.getElementById("main-content")?.scrollTo({ top: 0, behavior: "smooth" }); }

// Deliberately memory-only: legal drafts must never enter offline/browser storage.
export function useDraftGuard(key?: string, initiallyDirty = false) {
  const { drafts } = useUser();
  const formRef = useRef<HTMLFormElement>(null);
  type Snapshot = { values: Record<string, string>; checks: Record<string, boolean> };
  const snapshot = key ? drafts.get(key) as Snapshot | undefined : undefined;
  const [dirty, updateDirty] = useState(Boolean(snapshot) || initiallyDirty);
  useEffect(() => { if (key) updateDirty(drafts.has(key)); }, [key, drafts]);
  const setDirty = (value: boolean) => {
    updateDirty(value);
    if (!key) return;
    if (!value) { drafts.delete(key); return; }
    if (!formRef.current) return;
    const next: Snapshot = { values: {}, checks: {} };
    for (const field of Array.from(formRef.current.elements)) {
      if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement) || !field.name || ["password", "file"].includes(field.type)) continue;
      if (field instanceof HTMLInputElement && ["checkbox", "radio"].includes(field.type)) next.checks[`${field.name}:${field.value}`] = field.checked;
      else next.values[field.name] = field.value;
    }
    drafts.set(key, next);
  };
  // Reapply after asynchronously loaded relation options, without writing any browser storage.
  useEffect(() => {
    const saved = key ? drafts.get(key) as Snapshot | undefined : undefined;
    if (!saved || !formRef.current) return;
    for (const field of Array.from(formRef.current.elements)) {
      if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement) || !field.name) continue;
      if (field instanceof HTMLInputElement && ["checkbox", "radio"].includes(field.type)) field.checked = saved.checks[`${field.name}:${field.value}`] ?? field.checked;
      else if (saved.values[field.name] != null) field.value = saved.values[field.name];
    }
  });
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  return { dirty, setDirty, formRef, initialValues: snapshot?.values, discard: () => !dirty || window.confirm("Descartar as alterações ainda não salvas?") };
}
export function useAccountDraft<T>(key: string, initial: T) {
  const { drafts } = useUser();
  const [value, update] = useState<T>(() => { if (!drafts.has(key)) drafts.set(key, initial); return drafts.get(key) as T; });
  const setValue = (next: T | ((previous: T) => T)) => { const result = typeof next === "function" ? (next as (previous: T) => T)(value) : next; drafts.set(key, result); update(result); };
  return [value, setValue] as const;
}
export function DraftNotice({ dirty }: { dirty: boolean }) {
  return dirty ? <p role="status" data-unsaved-draft className="text-sm text-amber-300">Rascunho não salvo nesta aba. Salve antes de recarregar, fechar ou trocar de conta.</p> : null;
}
export function confirmDiscardDrafts() {
  return !document.querySelector("[data-unsaved-draft]") || window.confirm("Há alterações não salvas. Continuar? Ao voltar à tela nesta mesma aba, você poderá retomar o rascunho; fechar ou recarregar o aplicativo o descarta.");
}
export function ConnectivityNotice() {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    const guard = (event: MouseEvent) => {
      const link = (event.target as HTMLElement).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target === "_blank" || link.download || event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin === location.origin && url.pathname === location.pathname && url.search === location.search) return;
      if (!confirmDiscardDrafts()) { event.preventDefault(); event.stopPropagation(); }
    };
    sync(); window.addEventListener("online", sync); window.addEventListener("offline", sync);
    document.addEventListener("click", guard, true);
    return () => { window.removeEventListener("online", sync); window.removeEventListener("offline", sync); document.removeEventListener("click", guard, true); };
  }, []);
  return offline ? <p role="alert" className="mb-4 rounded-lg border border-amber-800 p-3 text-sm text-amber-200">Sem conexão. Não feche esta tela: os campos digitados continuam nela, mas ainda não foram salvos. Reconecte e tente salvar novamente. Dados jurídicos não ficam disponíveis offline.</p> : null;
}

export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    const revalidate = () => { if (path) { setData(null); setLoading(true); reload(); } };
    window.addEventListener(SESSION_RESTORED_EVENT, revalidate);
    return () => window.removeEventListener(SESSION_RESTORED_EVENT, revalidate);
  }, [path, reload]);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(""); setLoading(Boolean(path));
    if (path) api.get<T>(path, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setData(value); }).catch(err => {
      if (!controller.signal.aborted) setError(errorText(err));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, revision]);
  return { data, error, loading, reload };
}
export function Page({ title, subtitle, backHref, backLabel = "Voltar", children }: { title: string; subtitle?: string; backHref?: string; backLabel?: string; children: ReactNode }) {
  return <div className="workspace-page mx-auto min-w-0 max-w-6xl space-y-7 pb-4 [overflow-wrap:anywhere]"><header className="max-w-3xl">{backHref && <Link href={backHref} className="mb-3 inline-flex min-h-11 items-center gap-2 text-sm text-blue-300"><ArrowLeft aria-hidden="true" size={17} />{backLabel}</Link>}<h1 className="text-2xl font-semibold tracking-[-0.02em] text-zinc-50 md:text-3xl">{title}</h1>{subtitle && <p className="mt-2 max-w-[72ch] text-base leading-relaxed text-zinc-400">{subtitle}</p>}</header>{children}</div>;
}
export function Panel({ title, description, status, children, collapsibleOnMobile = false, expanded = false }: { title: string; description?: string; status?: string; children: ReactNode; collapsibleOnMobile?: boolean; expanded?: boolean }) {
  const details = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (!collapsibleOnMobile) return;
    const desktop = window.matchMedia("(min-width: 768px)");
    const sync = () => { if (details.current) details.current.open = expanded || desktop.matches; };
    sync(); desktop.addEventListener("change", sync);
    return () => desktop.removeEventListener("change", sync);
  }, [collapsibleOnMobile, expanded]);
  const style = "min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/25 p-4 shadow-sm md:p-5";
  return collapsibleOnMobile
    ? <details ref={details} className={`${style} group`}><summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3"><span><h2 className="text-base font-semibold text-zinc-100">{title}</h2>{description && <span className="mt-1 block text-sm font-normal text-zinc-400">{description}</span>}</span><span className="flex shrink-0 items-center gap-2">{status && <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs font-medium text-zinc-300">{status}</span>}<ChevronDown aria-hidden="true" size={18} className="transition-transform group-open:rotate-180" /></span></summary><div className="mt-4 space-y-4 border-t border-zinc-800 pt-4">{children}</div></details>
    : <section className={`${style} space-y-4`}><div><h2 className="text-base font-semibold text-zinc-100">{title}</h2>{description && <p className="mt-1 text-sm text-zinc-400">{description}</p>}</div>{children}</section>;
}
export function State({ loading, error, empty, emptyText = "Ainda não há registros nesta área." }: { loading?: boolean; error?: string; empty?: boolean; emptyText?: string }) {
  return error ? <p role="alert" className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>
    : loading ? <p role="status" className="text-sm text-zinc-400">Carregando registros…</p>
    : empty ? <p className="text-sm text-zinc-400">{emptyText}</p> : null;
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  // A textarea's initial text must not become part of its accessible label.
  const input = isValidElement<{
    "aria-label"?: string;
    type?: string;
    value?: string | number | readonly string[];
    defaultValue?: string | number | readonly string[];
    inputMode?: string;
    autoComplete?: string;
    placeholder?: string;
    onChange?: (event: ChangeEvent<HTMLInputElement>) => void;
  }>(children) && typeof children.type === "string" && ["input", "select", "textarea"].includes(children.type)
    ? cloneElement(children, {
      "aria-label": children.props["aria-label"] || label,
      ...(children.type === "input" && children.props.type === "tel" ? {
        inputMode: children.props.inputMode || "tel",
        autoComplete: children.props.autoComplete || "tel",
        placeholder: children.props.placeholder || "(11) 99999-9999",
        defaultValue: children.props.value == null && children.props.defaultValue != null ? formatBrazilianPhone(String(children.props.defaultValue)) : children.props.defaultValue,
        value: children.props.value != null ? formatBrazilianPhone(String(children.props.value)) : children.props.value,
        onChange: (event: ChangeEvent<HTMLInputElement>) => {
          event.currentTarget.value = formatBrazilianPhone(event.currentTarget.value);
          children.props.onChange?.(event);
        },
      } : {}),
    }) : children;
  if (isValidElement<{ type?: string }>(children) && children.type === "input" && children.props.type === "checkbox") {
    return <label className="flex min-h-11 min-w-0 cursor-pointer items-center gap-3 text-sm font-medium text-zinc-300">{input}<span>{label}</span></label>;
  }
  return <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300"><span>{label}</span>{input}</label>;
}
export function Action({ run, children, onDone, className = button }: { run: () => Promise<unknown>; children: ReactNode; onDone?: () => void; className?: string }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  return <span className="inline-flex min-w-0 max-w-full flex-col gap-1"><button type="button" disabled={busy} className={className} onClick={async () => {
    setBusy(true); setError(""); try { await run(); onDone?.(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }}>{busy ? "Processando…" : children}</button>{error && <span role="alert" className="text-xs text-red-300 max-w-sm">{error}</span>}</span>;
}
export async function download(path: string, filename: string) {
  const url = URL.createObjectURL(await apiBlob(path)); const link = document.createElement("a");
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function PrivatePdfPreview({ blob, title, filename, onClose }: { blob: Blob; title: string; filename: string; onClose: () => void }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (blob.type !== "application/pdf") { setUrl(""); return; }
    const objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [blob]);
  return <section aria-label={title} className="space-y-3 min-w-0">
    <p className="text-sm font-medium">{title}</p>
    {blob.type !== "application/pdf" && <State error="O servidor não devolveu um PDF válido. A prévia não foi aberta." />}
    <p className="text-xs text-zinc-400">Prévia do PDF real. Se o navegador do celular não exibir todas as páginas, baixe o mesmo arquivo abaixo.</p>
    {url && <><iframe src={url} title={title} className="w-full h-[65dvh] min-h-80 rounded-lg border border-zinc-700 bg-white" />
      <a href={url} download={filename} className={button}>Baixar este PDF</a></>}
    <button type="button" className={`${button} sm:ml-2`} onClick={onClose}>Fechar prévia</button>
  </section>;
}
export function JsonExport({ path, filename = "escritorio.json" }: { path: string; filename?: string }) {
  // Native download streams large exports without buffering the whole office in JS.
  return <a className={button} href={`${API_BASE_URL}${path}`} download={filename} target="_blank" rel="noopener noreferrer">Exportar registros e arquivos</a>;
}
