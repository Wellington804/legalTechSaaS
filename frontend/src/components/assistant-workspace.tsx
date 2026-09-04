"use client";

import { Bot, CheckSquare, ChevronDown, Copy, FilePlus2, History, Mic, Paperclip, Pencil, Plus, RotateCcw, Search, Send, Square, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { useUser } from "@/context/user-context";
import { api, apiClient } from "@/lib/api-client";
import { button, control, errorText, Field, Page, State, useResource } from "@/components/workspace/shared";
import type { List } from "@/components/workspace/records";

type ContextKind = "global" | "client" | "case" | "document" | "library" | "branding";
type Source = { kind: string; id: string; label: string; url?: string; citation_id?: string; locator?: string; excerpt?: string };
type Message = { id: string; role: "user" | "assistant"; text: string; sources?: Source[]; attachments?: { label: string }[] };
type Conversation = { id: string; title: string; context_kind: ContextKind; client_id?: string; case_id?: string; document_id?: string; retention_days: 30 | 90 | 365; message_count: number; updated_at: string; messages?: Message[] };
type Answer = { text: string; sources: Source[]; limitations: string[]; conversation_id: string; conversation: Conversation };

const contextNames: Record<ContextKind, string> = { global: "Orientação geral", client: "Cliente", case: "Processo", document: "Documento", library: "Biblioteca", branding: "Identidade documental" };

function StructuredAnswer({ text }: { text: string }) {
  const parts = text.split(/^##\s+/m).filter(Boolean);
  if (parts.length < 2) return <p className="whitespace-pre-wrap text-sm leading-relaxed">{text}</p>;
  return <div className="space-y-3">{parts.map((part, index) => {
    const [title, ...body] = part.trim().split("\n");
    return <section key={`${title}:${index}`} className={index ? "border-t border-zinc-800 pt-3" : ""}><h3 className="text-sm font-semibold text-zinc-100">{title}</h3><p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">{body.join("\n").trim()}</p></section>;
  })}</div>;
}

export function AssistantWorkspace() {
  const { user } = useUser();
  const fileInput = useRef<HTMLInputElement>(null); const log = useRef<HTMLDivElement>(null); const aborter = useRef<AbortController | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]); const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]); const [question, setQuestion] = useState(""); const [search, setSearch] = useState("");
  const [kind, setKind] = useState<ContextKind>("global"); const [clientId, setClientId] = useState(""); const [caseId, setCaseId] = useState(""); const [documentId, setDocumentId] = useState("");
  const [retention, setRetention] = useState<30 | 90 | 365>(90); const [attachments, setAttachments] = useState<File[]>([]);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [historyOpen, setHistoryOpen] = useState(false); const [showJump, setShowJump] = useState(false);
  const clients = useResource<List>("/workspace/clients?limit=200"); const cases = useResource<List>("/workspace/cases?limit=200"); const documents = useResource<List>("/workspace/documents?limit=200");

  async function loadConversations(query = "") {
    try { setConversations((await api.get<{ items: Conversation[] }>(`/engagement/assistant/conversations?limit=100${query ? `&query=${encodeURIComponent(query)}` : ""}`)).items); }
    catch (reason) { setError(errorText(reason)); }
  }
  useEffect(() => { void loadConversations(); }, []);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); setShowJump(false); }, [messages, busy]);

  async function openConversation(id: string) {
    setError("");
    try {
      const item = await api.get<Conversation & { messages: Message[] }>(`/engagement/assistant/conversations/${id}`);
      setConversationId(item.id); setMessages(item.messages); setKind(item.context_kind); setClientId(item.client_id || ""); setCaseId(item.case_id || ""); setDocumentId(item.document_id || ""); setRetention(item.retention_days); setHistoryOpen(false);
    } catch (reason) { setError(errorText(reason)); }
  }
  function newConversation() { aborter.current?.abort(); setConversationId(null); setMessages([]); setQuestion(""); setAttachments([]); setKind("global"); setClientId(""); setCaseId(""); setDocumentId(""); setNotice(""); setError(""); setHistoryOpen(false); }

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const next = [...attachments, ...Array.from(event.target.files || [])].filter((file, index, all) => all.findIndex(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified) === index).slice(0, 3);
    if (next.reduce((total, file) => total + file.size, 0) > 25 * 1024 * 1024) setError("Os anexos não podem ultrapassar 25 MB no total."); else { setAttachments(next); setError(""); }
    event.target.value = "";
  }

  async function ask(prompt = question.trim()) {
    if (busy || prompt.length < 5) return;
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", text: prompt, attachments: attachments.map(file => ({ label: file.name })) };
    setMessages(current => [...current, userMessage]); setQuestion(""); setBusy(true); setError(""); setNotice("");
    const controller = new AbortController(); aborter.current = controller;
    try {
      const form = new FormData(); form.set("question", prompt); form.set("context_kind", kind); form.set("consent", "true"); form.set("retention_days", String(retention));
      if (conversationId) form.set("conversation_id", conversationId); if (clientId) form.set("client_id", clientId); if (caseId) form.set("case_id", caseId); if (documentId) form.set("document_id", documentId);
      form.set("history", JSON.stringify(messages.slice(-6).map(item => ({ role: item.role, content: item.text.slice(0, 2000) })))); attachments.forEach(file => form.append("files", file));
      const answer = await apiClient<Answer>("/engagement/assistant/chat", { method: "POST", body: form, signal: controller.signal });
      setConversationId(answer.conversation_id); setMessages(current => [...current, { id: crypto.randomUUID(), role: "assistant", text: answer.text, sources: answer.sources }]); setAttachments([]);
      await loadConversations(search);
    } catch (reason) {
      if (!controller.signal.aborted) { setMessages(current => current.filter(item => item.id !== userMessage.id)); setQuestion(prompt); setError(errorText(reason)); }
    } finally { setBusy(false); aborter.current = null; }
  }

  async function renameConversation(item: Conversation) {
    const title = window.prompt("Nome da conversa", item.title)?.trim(); if (!title || title === item.title) return;
    try { await api.patch(`/engagement/assistant/conversations/${item.id}`, { title }); await loadConversations(search); } catch (reason) { setError(errorText(reason)); }
  }
  async function deleteConversation(item: Conversation) {
    if (!window.confirm(`Excluir definitivamente “${item.title}” e todo o histórico?`)) return;
    try { await api.delete(`/engagement/assistant/conversations/${item.id}`); if (conversationId === item.id) newConversation(); await loadConversations(search); } catch (reason) { setError(errorText(reason)); }
  }
  async function changeRetention(days: 30 | 90 | 365) {
    setRetention(days); if (!conversationId) return;
    try { await api.patch(`/engagement/assistant/conversations/${conversationId}`, { retention_days: days }); await loadConversations(search); } catch (reason) { setError(errorText(reason)); }
  }
  async function saveDocument(kindValue: "document" | "note", prefix: string) {
    const last = [...messages].reverse().find(item => item.role === "assistant"); if (!last) return;
    const title = window.prompt("Nome do rascunho", `${prefix} — ${new Date().toLocaleDateString("pt-BR")}`)?.trim(); if (!title) return;
    await api.post("/workspace/documents", { title, content_text: last.text, content_format: "markdown", kind: kindValue, case_id: caseId || null, client_id: clientId || null }); setNotice("Rascunho salvo em Documentos. Revise antes de usar ou enviar.");
  }
  async function createTask() {
    const title = window.prompt("Qual tarefa deseja criar?", "Revisar resposta do Copiloto")?.trim(); if (!title) return;
    await api.post("/workspace/tasks", { request_id: crypto.randomUUID(), title, kind: "task", case_id: caseId || null, assigned_user_id: user.id, manually_reviewed: true }); setNotice("Tarefa criada sem prazo. Defina e confira a data na Agenda.");
  }
  async function createChecklist() {
    const value = window.prompt("Itens do checklist, um por linha", "Conferir fatos e documentos\nRevisar fundamentos jurídicos\nValidar versão final com o responsável")?.trim();
    if (!value) return;
    const items = value.split("\n").map(item => item.trim()).filter(Boolean).slice(0, 10);
    if (!items.length || !window.confirm(`Criar ${items.length} tarefas sem prazo?`)) return;
    await Promise.all(items.map(title => api.post("/workspace/tasks", { request_id: crypto.randomUUID(), title, kind: "task", case_id: caseId || null, assigned_user_id: user.id, manually_reviewed: true })));
    setNotice(`${items.length} itens criados na Agenda, sem datas automáticas.`);
  }
  async function copyLast() { const last = [...messages].reverse().find(item => item.role === "assistant"); if (last) { await navigator.clipboard.writeText(last.text); setNotice("Resposta copiada."); } }
  async function runAction(work: () => Promise<void>) { setError(""); setNotice(""); try { await work(); } catch (reason) { setError(errorText(reason)); } }
  function dictate() {
    const Speech = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition; if (!Speech) { setError("Ditado não disponível neste navegador."); return; }
    const recognition = new Speech(); recognition.lang = "pt-BR"; recognition.interimResults = false; recognition.onresult = (event: any) => setQuestion(value => `${value}${value ? " " : ""}${event.results[0][0].transcript}`); recognition.onerror = () => setError("Não foi possível usar o microfone."); recognition.start();
  }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ask(); } }
  const active = conversations.find(item => item.id === conversationId);

  return <Page title="Copiloto jurídico" subtitle="Converse com contexto do escritório, analise documentos e transforme respostas em rascunhos ou tarefas sempre sob sua confirmação.">
    <div className="grid h-[calc(100dvh-9rem)] min-h-[28rem] max-h-[56rem] overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/20 md:min-h-[36rem] lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className={`${historyOpen ? "fixed inset-0 z-50 flex" : "hidden"} min-h-0 flex-col border-r border-zinc-800 bg-zinc-950 lg:static lg:flex`} aria-label="Histórico pessoal">
        <div className="flex items-center justify-between gap-2 border-b border-zinc-800 p-3"><h2 className="font-semibold">Suas conversas</h2><button className="grid min-h-11 min-w-11 place-items-center lg:hidden" onClick={() => setHistoryOpen(false)} aria-label="Fechar histórico"><X size={18} /></button></div>
        <div className="space-y-2 p-3"><button type="button" className={`${button} w-full gap-2`} onClick={newConversation}><Plus size={16} />Nova conversa</button><label className="relative block"><Search className="absolute left-3 top-3.5 text-zinc-500" size={16} /><input className={`${control} pl-9`} value={search} onChange={event => { setSearch(event.target.value); void loadConversations(event.target.value); }} placeholder="Buscar conversas" aria-label="Buscar conversas" /></label></div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">{conversations.map(item => { const selected = item.id === conversationId; return <div key={item.id} className={`group rounded-xl p-2 ${selected ? "bg-blue-500/15" : "hover:bg-zinc-900"}`}><button className="w-full text-left" onClick={() => void openConversation(item.id)}><span className="block truncate text-sm font-medium">{item.title}</span><span className={`text-xs ${selected ? "text-blue-200" : "text-zinc-500"}`}>{item.message_count} mensagens · {new Date(item.updated_at).toLocaleDateString("pt-BR")}</span></button><div className="mt-1 flex gap-1"><button className={`min-h-9 min-w-9 rounded-lg hover:bg-zinc-800 ${selected ? "text-blue-100" : "text-zinc-400"}`} onClick={() => void renameConversation(item)} aria-label={`Renomear ${item.title}`}><Pencil className="mx-auto" size={14} /></button><button className={`min-h-9 min-w-9 rounded-lg hover:bg-zinc-800 ${selected ? "text-blue-100" : "text-zinc-400"}`} onClick={() => void deleteConversation(item)} aria-label={`Excluir ${item.title}`}><Trash2 className="mx-auto" size={14} /></button></div></div>; })}{conversations.length === 0 && <p className="p-3 text-sm text-zinc-500">Nenhuma conversa salva.</p>}</div>
      </aside>

      <section className="flex min-h-0 min-w-0 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 p-3"><button className={`${button} gap-2 lg:hidden`} onClick={() => setHistoryOpen(true)}><History size={16} />Histórico</button><button className={`${button} gap-2`} onClick={newConversation}><Plus size={16} />Nova</button><span className="ml-auto text-xs text-zinc-500">{active?.title || "Nova conversa"}</span></div>
        <details className="border-b border-zinc-800 px-3 py-2">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium"><span>Contexto: {contextNames[kind]}</span><span className="text-xs font-normal text-zinc-500">Alterar</span></summary>
          <div className="grid gap-3 pb-3 sm:grid-cols-3">
            <Field label="Usar informações de"><select className={control} value={kind} onChange={event => { const value = event.target.value as ContextKind; setKind(value); setClientId(""); setCaseId(""); setDocumentId(""); }}><option value="global">Orientação geral</option><option value="client">Cliente</option><option value="case">Processo</option><option value="document">Documento</option><option value="library">Biblioteca</option><option value="branding">Identidade documental</option></select></Field>
            {kind === "client" ? <Field label="Cliente"><select className={control} value={clientId} onChange={event => setClientId(event.target.value)}><option value="">Selecione…</option>{clients.data?.items.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field> : kind === "case" ? <Field label="Processo"><select className={control} value={caseId} onChange={event => setCaseId(event.target.value)}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field> : kind === "document" ? <Field label="Documento"><select className={control} value={documentId} onChange={event => setDocumentId(event.target.value)}><option value="">Selecione…</option>{documents.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field> : <p className="self-end pb-3 text-sm text-zinc-400">{contextNames[kind]}</p>}
            <Field label="Guardar esta conversa"><select className={control} value={retention} onChange={event => void changeRetention(Number(event.target.value) as 30 | 90 | 365)}><option value={30}>30 dias</option><option value={90}>90 dias</option><option value={365}>1 ano</option></select></Field>
          </div>
        </details>

        <div className="relative min-h-0 flex-1">
        <div ref={log} role="log" aria-live="polite" onScroll={event => { const node = event.currentTarget; setShowJump(node.scrollHeight - node.scrollTop - node.clientHeight > 120); }} className="h-full space-y-5 overflow-y-auto p-4 md:p-6">
          {messages.length === 0 && <div className="mx-auto max-w-xl py-10 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-500/15 text-blue-300"><Bot size={24} /></span><h2 className="mt-5 text-xl font-semibold">Como posso ajudar?</h2><p className="mt-2 text-sm leading-relaxed text-zinc-400">Escreva sua pergunta ou anexe documentos. Você revisa a resposta antes de salvar ou usar.</p></div>}
          {messages.map(message => <article key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[94%] md:max-w-[85%] ${message.role === "user" ? "rounded-2xl bg-blue-600 px-4 py-3 text-white" : "w-full space-y-3"}`}>{message.role === "assistant" ? <><StructuredAnswer text={message.text} />{message.sources && message.sources.length > 0 && <details className="rounded-xl border border-zinc-800 p-3"><summary className="cursor-pointer text-sm font-medium">Fontes e registros usados ({message.sources.length})</summary><div className="mt-2 space-y-2 text-xs text-zinc-400">{message.sources.map((source, index) => <article className="rounded-lg bg-zinc-950 p-2" key={`${source.kind}:${source.id}:${index}`}><strong>{source.label}</strong>{source.excerpt && <p className="mt-1 whitespace-pre-wrap">{source.excerpt}</p>}</article>)}</div></details>}</> : <><p className="whitespace-pre-wrap text-sm">{message.text}</p>{message.attachments && message.attachments.length > 0 && <p className="mt-2 text-xs text-blue-100">{message.attachments.map(item => item.label).join(" · ")}</p>}<button className="mt-2 text-xs underline" onClick={() => setQuestion(message.text)}>Editar e reenviar</button></>}</div></article>)}
          {busy && <p role="status" className="text-sm text-zinc-400">Analisando o contexto e preparando uma resposta…</p>}
          <State error={clients.error || cases.error || documents.error || error} />{notice && <p role="status" className="rounded-xl border border-emerald-800 bg-emerald-950/20 p-3 text-sm text-emerald-200">{notice}</p>}
          {messages.some(item => item.role === "assistant") && !busy && <div className="flex flex-wrap gap-2 border-t border-zinc-800 pt-4" aria-label="Ações da resposta"><button className={button} onClick={() => void runAction(copyLast)}><Copy size={15} />Copiar</button><button className={button} onClick={() => void runAction(() => saveDocument("document", "Rascunho com IA"))}><FilePlus2 size={15} />Salvar documento</button><details className="w-full"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium">Outras ações</summary><div className="flex flex-wrap gap-2 pb-1"><button className={button} onClick={() => void runAction(createTask)}><CheckSquare size={15} />Criar tarefa</button><button className={button} onClick={() => void runAction(createChecklist)}><CheckSquare size={15} />Criar checklist</button><button className={button} onClick={() => void runAction(() => saveDocument("note", "Mensagem ao cliente"))}><FilePlus2 size={15} />Preparar mensagem</button><button className={button} onClick={() => { const lastUser = [...messages].reverse().find(item => item.role === "user"); if (lastUser) void ask(lastUser.text); }}><RotateCcw size={15} />Tentar novamente</button><Link className={button} href="/dashboard/petitions/editor">Abrir editor</Link></div></details></div>}
        </div>
        {showJump && <button type="button" className={`${button} absolute bottom-3 right-3 gap-2 shadow-lg shadow-black/20`} onClick={() => log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" })}><ChevronDown aria-hidden="true" size={16} />Ir ao fim</button>}
        </div>

        <footer className="space-y-2 border-t border-zinc-800 bg-zinc-950 p-3 md:p-4">
          {attachments.length > 0 && <div className="flex flex-wrap gap-2">{attachments.map(file => <span key={`${file.name}:${file.lastModified}`} className="inline-flex min-h-9 max-w-full items-center gap-2 rounded-full bg-zinc-800 px-3 text-xs"><span className="truncate">{file.name}</span><button onClick={() => setAttachments(current => current.filter(item => item !== file))} aria-label={`Remover ${file.name}`}><X size={13} /></button></span>)}</div>}
          <div className="flex items-end gap-1 rounded-2xl border border-zinc-700 bg-zinc-900 p-2 focus-within:ring-2 focus-within:ring-blue-500"><input ref={fileInput} className="sr-only" type="file" multiple accept=".pdf,.docx,.xlsx,.txt" onChange={selectFiles} /><button className="grid min-h-11 min-w-11 place-items-center rounded-xl hover:bg-zinc-800" onClick={() => fileInput.current?.click()} disabled={busy || attachments.length >= 3} aria-label="Anexar documentos"><Paperclip size={18} /></button><button className="grid min-h-11 min-w-11 place-items-center rounded-xl hover:bg-zinc-800" onClick={dictate} disabled={busy} aria-label="Ditar mensagem"><Mic size={18} /></button><textarea className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-base outline-none placeholder:text-zinc-500 md:text-sm" rows={1} minLength={5} maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={keyDown} placeholder="Pergunte ou use @ para escolher um contexto…" aria-label="Mensagem para o Copiloto" />{busy ? <button className="grid min-h-11 min-w-11 place-items-center rounded-xl bg-zinc-700" onClick={() => aborter.current?.abort()} aria-label="Parar resposta"><Square size={16} /></button> : <button className="grid min-h-11 min-w-11 place-items-center rounded-xl bg-blue-600 text-white disabled:opacity-50" disabled={question.trim().length < 5} onClick={() => void ask()} aria-label="Enviar mensagem"><Send size={18} /></button>}</div>
          <p className="text-xs text-zinc-500">Anexos são processados para esta pergunta e não são arquivados. Respostas são rascunhos para revisão profissional.</p>
        </footer>
      </section>
    </div>
  </Page>;
}
