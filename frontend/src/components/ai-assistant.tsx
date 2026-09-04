"use client";

import { Copy, FilePlus2, Paperclip, Send, Trash2, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { useUser } from "@/context/user-context";
import { api, apiClient } from "@/lib/api-client";
import { button, control, errorText, Field, State, useResource } from "@/components/workspace/shared";
import type { Row } from "@/components/workspace/records";

type ContextKind = "global" | "client" | "case" | "document" | "library" | "branding";
type ContextDetail = { contextKind?: ContextKind; clientId?: string; caseId?: string; documentId?: string; prompt?: string };
type Answer = { text: string; sources: Array<{ kind: string; id: string; label: string; url?: string; citation_id?: string; locator?: string; excerpt?: string }>; limitations: string[]; review_required: true; saved: false; conversation_id?: string };
type ChatMessage = { id: string; role: "user" | "assistant"; text: string };
type List = { items: Row[] };
export const OPEN_AI_EVENT = "lexflow:open-ai";

const welcome = (): ChatMessage[] => [{
  id: "welcome",
  role: "assistant",
  text: "Olá. Posso organizar informações, revisar textos e preparar rascunhos. Você pode conversar normalmente ou anexar até três documentos.",
}];

function inferredContext(pathname: string): ContextDetail {
  const caseMatch = pathname.match(/^\/dashboard\/cases\/([^/]+)/);
  if (caseMatch) return { contextKind: "case", caseId: caseMatch[1] };
  if (pathname === "/dashboard/library") return { contextKind: "library" };
  if (pathname === "/dashboard/brand") return { contextKind: "branding" };
  return { contextKind: "global" };
}

export function AiAssistant() {
  const { isLoggedIn } = useUser();
  const pathname = usePathname();
  const dialog = useRef<HTMLDialogElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<ContextDetail>(() => inferredContext(pathname));
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>(welcome);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [savedDocument, setSavedDocument] = useState<Row | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const cases = useResource<List>(open ? "/workspace/cases?limit=200" : null);
  const clients = useResource<List>(open ? "/workspace/clients?limit=200" : null);
  const documents = useResource<List>(open ? "/workspace/documents?limit=200" : null);
  const kind = context.contextKind || "global";

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<ContextDetail>).detail || {};
      setContext({ ...inferredContext(pathname), ...detail });
      setQuestion(detail.prompt || "");
      setMessages(welcome()); setConversationId(null); setAttachments([]); setAnswer(null); setSavedDocument(null); setError(""); setOpen(true);
    };
    window.addEventListener(OPEN_AI_EVENT, handler);
    return () => window.removeEventListener(OPEN_AI_EVENT, handler);
  }, [pathname]);
  useEffect(() => { if (open) dialog.current?.showModal(); else dialog.current?.close(); }, [open]);
  useEffect(() => { if (!isLoggedIn) setOpen(false); }, [isLoggedIn]);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [messages, busy]);
  if (!isLoggedIn) return null;

  const close = () => {
    setOpen(false); setQuestion(""); setMessages(welcome()); setConversationId(null); setAttachments([]); setAnswer(null);
    setSavedDocument(null); setError("");
  };
  const chooseKind = (next: ContextKind) => {
    setContext({ contextKind: next }); setMessages(welcome()); setAnswer(null); setSavedDocument(null); setError("");
  };
  const suggestions: Record<ContextKind, string[]> = {
    global: ["Organize minhas prioridades de hoje sem inventar prazos.", "Aponte pendências da agenda que precisam de conferência."],
    client: ["Resuma o atendimento e liste os dados que ainda faltam.", "Prepare um roteiro de próximos passos para este cliente."],
    case: ["Monte uma cronologia com os dados registrados.", "Liste providências, lacunas e itens que exigem conferência."],
    document: ["Resuma o documento e destaque inconsistências.", "Sugira uma revisão de redação sem alterar os fatos."],
    library: ["Organize as referências por tema e indique lacunas.", "Resuma as referências recentes sem criar novas fontes."],
    branding: ["Sugira uma direção visual coerente para os documentos.", "Transforme meu direcionamento em regras visuais objetivas."],
  };
  const contextLabel = kind === "global" ? "Orientação geral" : kind === "case" ? "Processo" : kind === "client" ? "Cliente" : kind === "document" ? "Documento" : kind === "branding" ? "Identidade documental" : "Biblioteca";

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = [...attachments, ...Array.from(event.target.files || [])]
      .filter((file, index, all) => all.findIndex(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified) === index)
      .slice(0, 3);
    if (selected.reduce((sum, file) => sum + file.size, 0) > 25 * 1024 * 1024) {
      setError("Os anexos da conversa não podem ultrapassar 25 MB no total.");
    } else {
      setAttachments(selected); setError("");
    }
    event.target.value = "";
  }

  async function ask() {
    const prompt = question.trim();
    if (busy || prompt.length < 5) return;
    const previous = messages.filter(item => item.id !== "welcome").slice(-6);
    setMessages(current => [...current, { id: crypto.randomUUID(), role: "user", text: prompt }]);
    setQuestion(""); setBusy(true); setError(""); setAnswer(null); setSavedDocument(null);
    try {
      const form = new FormData();
      form.set("question", prompt); form.set("context_kind", kind); form.set("consent", "true");
      if (context.clientId) form.set("client_id", context.clientId);
      if (context.caseId) form.set("case_id", context.caseId);
      if (context.documentId) form.set("document_id", context.documentId);
      if (conversationId) form.set("conversation_id", conversationId);
      form.set("history", JSON.stringify(previous.map(item => ({ role: item.role, content: item.text.slice(0, 2000) }))));
      attachments.forEach(file => form.append("files", file));
      const response = await apiClient<Answer>("/engagement/assistant/chat", { method: "POST", body: form });
      setConversationId(response.conversation_id || null);
      setAnswer(response);
      setMessages(current => [...current, { id: crypto.randomUUID(), role: "assistant", text: response.text }]);
      setDraftTitle(`Rascunho com IA — ${prompt.slice(0, 80)}`);
    } catch (reason) {
      setMessages(current => current.slice(0, -1)); setError(errorText(reason)); setQuestion(prompt);
    } finally { setBusy(false); }
  }

  async function saveDraft() {
    if (!answer || draftTitle.trim().length < 2) return;
    setSaveBusy(true); setError("");
    try {
      setSavedDocument(await api.post<Row>("/workspace/documents", {
        title: draftTitle.trim(), content_text: answer.text, content_format: "markdown", kind: "document",
        case_id: kind === "case" ? context.caseId || null : null,
        client_id: kind === "client" ? context.clientId || null : null,
      }));
    } catch (reason) { setError(errorText(reason)); } finally { setSaveBusy(false); }
  }

  function composerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault(); void ask();
    }
  }

  return <dialog ref={dialog} aria-labelledby="ai-assistant-title" onCancel={close} onClose={() => setOpen(false)}
    className="m-0 mt-auto h-[92dvh] w-full max-w-none overflow-hidden rounded-t-2xl border border-zinc-700 bg-zinc-950 p-0 text-zinc-100 backdrop:bg-black/70 md:ml-auto md:mt-0 md:h-dvh md:w-[min(100%,38rem)] md:rounded-none md:border-y-0 md:border-r-0">
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <div><h2 id="ai-assistant-title" className="font-semibold">Assistente LexFlow</h2><p className="text-xs text-zinc-400">Pergunta rápida com o contexto desta tela.</p></div>
        <button type="button" className="grid min-h-11 min-w-11 place-items-center" onClick={close} aria-label="Fechar assistente"><X aria-hidden="true" size={20} /></button>
      </header>

      <details className="border-b border-zinc-800 px-4 py-2">
        <summary className="flex min-h-11 cursor-pointer list-none items-center text-sm font-medium">Contexto: {contextLabel}</summary>
        <div className="space-y-3 pb-3">
          <Field label="Usar informações de"><select className={control} value={kind} onChange={event => chooseKind(event.target.value as ContextKind)}>
            <option value="global">Orientação geral</option><option value="client">Um cliente</option><option value="case">Um processo</option>
            <option value="document">Um documento salvo</option><option value="library">Biblioteca do escritório</option><option value="branding">Identidade documental</option>
          </select></Field>
          {kind === "client" && <Field label="Cliente"><select className={control} value={context.clientId || ""} onChange={event => setContext({ contextKind: kind, clientId: event.target.value })}><option value="">Selecione…</option>{clients.data?.items.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>}
          {kind === "case" && <Field label="Processo"><select className={control} value={context.caseId || ""} onChange={event => setContext({ contextKind: kind, caseId: event.target.value })}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>}
          {kind === "document" && <Field label="Documento"><select className={control} value={context.documentId || ""} onChange={event => setContext({ contextKind: kind, documentId: event.target.value })}><option value="">Selecione…</option>{documents.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>}
        </div>
      </details>

      <div ref={log} role="log" aria-live="polite" aria-label="Conversa com o assistente" className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map(message => <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[88%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${message.role === "user" ? "bg-blue-600 text-white" : "border border-zinc-800 bg-zinc-900 text-zinc-100"}`}>{message.text}</div></div>)}
        {busy && <p role="status" className="text-sm text-zinc-400">Preparando resposta…</p>}
        {messages.length === 1 && <div className="flex flex-wrap gap-2" aria-label="Sugestões de perguntas">{suggestions[kind].map(item => <button key={item} type="button" className={button} onClick={() => setQuestion(item)}>{item}</button>)}</div>}
        <State error={cases.error || clients.error || documents.error || error} />
        {answer && !busy && <section className="space-y-3 rounded-xl border border-zinc-800 p-3" aria-label="Ações da última resposta">
          <p className="text-xs text-amber-300">Rascunho sujeito à revisão profissional. Nenhum prazo ou ação foi criado.</p>
          <div className="flex flex-wrap gap-2"><button type="button" className={button} onClick={() => navigator.clipboard.writeText(answer.text)}><Copy aria-hidden="true" size={16} />Copiar</button>{!savedDocument && <button type="button" className={button} disabled={saveBusy || draftTitle.trim().length < 2} onClick={saveDraft}><FilePlus2 aria-hidden="true" size={16} />{saveBusy ? "Salvando…" : "Salvar em Documentos"}</button>}</div>
          {!savedDocument && <Field label="Nome do rascunho"><input className={control} value={draftTitle} maxLength={300} onChange={event => setDraftTitle(event.target.value)} /></Field>}
          {savedDocument && <p role="status" className="text-sm text-emerald-200">Rascunho salvo. <Link className="underline" href={kind === "case" && context.caseId ? `/dashboard/cases/${context.caseId}` : "/dashboard/petitions/editor"} onClick={close}>Abrir documento</Link></p>}
          {answer.sources.length > 0 && <details><summary className="min-h-11 cursor-pointer content-center text-sm">Fontes utilizadas ({answer.sources.length})</summary><div className="space-y-2 text-xs text-zinc-400">{answer.sources.map(source => <article className="rounded-lg bg-zinc-950 p-2" key={`${source.kind}:${source.id}`}><strong>{source.label}</strong>{source.excerpt && <p className="mt-1 whitespace-pre-wrap">{source.excerpt}</p>}</article>)}</div></details>}
        </section>}
      </div>

      <footer className="space-y-3 border-t border-zinc-800 bg-zinc-950 p-4">
        {attachments.length > 0 && <div aria-label="Documentos desta conversa" className="flex flex-wrap gap-2">{attachments.map(file => <span key={`${file.name}:${file.lastModified}`} className="inline-flex min-h-9 max-w-full items-center gap-2 rounded-full bg-zinc-800 px-3 text-xs"><span className="truncate">{file.name}</span><button type="button" aria-label={`Remover ${file.name}`} onClick={() => setAttachments(current => current.filter(item => item !== file))}><Trash2 aria-hidden="true" size={14} /></button></span>)}</div>}
        <div className="flex items-end gap-2 rounded-2xl border border-zinc-700 bg-zinc-900 p-2 focus-within:ring-2 focus-within:ring-blue-500">
          <input ref={fileInput} className="sr-only" type="file" multiple accept=".pdf,.docx,.xlsx,.txt" onChange={selectFiles} />
          <button type="button" className="grid min-h-11 min-w-11 place-items-center rounded-lg hover:bg-zinc-800" onClick={() => fileInput.current?.click()} disabled={attachments.length >= 3 || busy} aria-label="Anexar documentos"><Paperclip aria-hidden="true" size={19} /></button>
          <textarea className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-base outline-none placeholder:text-zinc-500 md:text-sm" rows={1} minLength={5} maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={composerKeyDown} placeholder="Digite sua mensagem…" aria-label="Mensagem para o assistente" />
          <button type="button" className="grid min-h-11 min-w-11 place-items-center rounded-xl bg-blue-600 text-white disabled:opacity-50" disabled={busy || question.trim().length < 5} onClick={ask} aria-label="Enviar mensagem"><Send aria-hidden="true" size={18} /></button>
        </div>
        <div className="flex items-center justify-between gap-3"><p className="text-xs text-zinc-500">Anexos não são arquivados. A conversa fica no seu histórico pessoal.</p><Link href="/dashboard/assistant" onClick={close} className="shrink-0 text-xs font-medium text-blue-300 underline">Abrir Copiloto</Link></div>
      </footer>
    </div>
  </dialog>;
}
