"use client";

import { Search, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { control, State, useResource } from "@/components/workspace/shared";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { workspaceNavigation } from "@/lib/navigation";

type SearchResult = {
  kind: "client" | "case" | "document" | "task" | "publication" | "library" | "message";
  id: string;
  title: string;
  subtitle: string;
  snippet: string | null;
  href: string;
  updated_at: string;
};

const kindLabels: Record<SearchResult["kind"], string> = {
  client: "Cliente", case: "Processo", document: "Documento", task: "Agenda",
  publication: "Andamento", library: "Biblioteca", message: "Mensagem",
};

export default function CommandPalette() {
  const { isLoggedIn, user } = useUser();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);
  const results = useResource<{ results: SearchResult[] }>(
    open && search.length >= 2 ? `/workspace/search?q=${encodeURIComponent(search)}&limit=30` : null,
  );
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (isLoggedIn && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setOpen(value => !value);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isLoggedIn]);
  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener("lexflow:open-search", handler);
    return () => window.removeEventListener("lexflow:open-search", handler);
  }, []);
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  useEffect(() => { if (!isLoggedIn) { setOpen(false); setQuery(""); setSearch(""); } }, [isLoggedIn]);
  if (!isLoggedIn) return null;

  const close = () => { setOpen(false); setQuery(""); setSearch(""); };
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matchingModules = normalizedQuery ? workspaceNavigation.filter(item =>
    (!item.admin || isOfficeAdminRole(user.role))
    && (!item.lawyer || user.role === "ASSOCIADO" || isOfficeAdminRole(user.role))
    && `${item.name} ${item.shortName}`.toLocaleLowerCase().includes(normalizedQuery),
  ) : [];
  const matches = search === query.trim() ? results.data?.results || [] : [];

  return <dialog ref={dialog} aria-labelledby="central-search-title" onCancel={close} onClose={() => setOpen(false)}
    onClick={event => { if (event.target === event.currentTarget) close(); }}
    className="max-h-[88dvh] w-[calc(100%_-_2rem)] max-w-2xl overflow-y-auto overscroll-contain rounded-2xl border border-zinc-700 bg-zinc-950 p-4 text-zinc-100 shadow-2xl backdrop:bg-black/70 [overflow-wrap:anywhere]">
    <div className="mb-3 flex items-center justify-between gap-2">
      <div><h2 id="central-search-title" className="text-lg font-semibold">Buscar no escritório</h2><p className="text-xs text-zinc-400">Clientes, processos, agenda, documentos, andamentos e mensagens.</p></div>
      <button className="grid min-h-11 min-w-11 place-items-center" onClick={close} aria-label="Fechar busca"><X aria-hidden="true" size={20} /></button>
    </div>
    <label className="relative block"><span className="sr-only">O que deseja encontrar?</span><Search aria-hidden="true" size={18} className="pointer-events-none absolute left-3 top-3.5 text-zinc-500" /><input autoFocus className={`${control} pl-10`} type="search" maxLength={200} value={query} onChange={event => setQuery(event.target.value)} placeholder="Nome, CPF/CNPJ, número, tarefa ou palavra do documento…" /></label>
    <div className="mt-3 space-y-1">
      {matchingModules.map(item => <Link key={item.href} href={item.href} onClick={close} className="flex min-h-11 flex-col justify-center rounded-lg p-2 text-sm hover:bg-zinc-800"><span className="font-medium">{item.name}</span><span className="text-xs text-zinc-400">Abrir área</span></Link>)}
      <State error={results.error} loading={query.trim().length >= 2 && (results.loading || search !== query.trim())}
        empty={search.length >= 2 && search === query.trim() && !results.loading && !matchingModules.length && !matches.length}
        emptyText="Nada foi encontrado com esses termos." />
      {query.trim().length < 2 && <p className="p-2 text-xs text-zinc-400">Digite ao menos 2 caracteres.</p>}
      {matches.map(item => <Link key={`${item.kind}:${item.id}`} href={item.href} onClick={close} className="block min-h-11 rounded-lg p-3 hover:bg-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
        <span className="flex items-start justify-between gap-3"><span className="font-medium">{item.title}</span><span className="shrink-0 rounded-full bg-zinc-800 px-2 py-1 text-[11px] text-zinc-300">{kindLabels[item.kind]}</span></span>
        <span className="mt-1 block text-xs text-zinc-400">{item.subtitle}</span>
        {item.snippet && <span className="mt-1 line-clamp-2 block text-xs text-zinc-500">{item.snippet}</span>}
      </Link>)}
    </div>
  </dialog>;
}
