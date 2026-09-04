"use client";
import { useRef, useState, type FormEvent } from "react";
import { api, apiClient } from "@/lib/api-client";
import { Action, DraftNotice, Field, Page, Panel, State, button, control, dateText, download, errorText, primary, scrollWorkspaceToTop, useDraftGuard, useResource } from "./shared";
import type { List, Row } from "./records";
import { DocumentExports } from "./document-exports";
import { DocumentKit } from "./document-kit";
import { FileCenter } from "./file-center";
import { DocumentReview } from "./document-review";
import { LegalAiWorkbench } from "./legal-ai-workbench";
import { DOCUMENT_TYPES, documentTypeLabels, type DocumentType } from "@/lib/branding";

export function Documents({ templates = false, caseId, embedded = false }: { templates?: boolean; caseId?: string; embedded?: boolean }) {
  const base = templates ? "/workspace/templates" : "/workspace/documents";
  const resource = useResource<List>(base + (caseId ? `?case_id=${caseId}` : ""));
  const cases = useResource<List>(templates ? null : "/workspace/cases");
  const models = useResource<List>(templates ? null : "/workspace/templates");
  const storage = useResource<{ direct_uploads: boolean }>(templates ? null : "/workspace/document-storage");
  const [editing, setEditing] = useState<Row | null>(null); const [creating, setCreating] = useState(false); const [kitOpen, setKitOpen] = useState(false); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [versionsFor, setVersionsFor] = useState<string | null>(null);
  const [exportsFor, setExportsFor] = useState<string | null>(null);
  const [reviewFor, setReviewFor] = useState<string | null>(null);
  const [editorView, setEditorView] = useState<"write" | "preview">("write");
  const [section, setSection] = useState<"files" | "create" | "ai">("files");
  const draft = useDraftGuard(`document:${templates ? "template" : caseId || "all"}:${editing?.id || "new"}`); const formRef = draft.formRef;
  const versions = useResource<List>(versionsFor ? `/workspace/documents/${versionsFor}/versions` : null);
  const [review, setReview] = useState<{ text: string; stale: boolean; source: { version: number }; sources?: { citation_id: string; label: string; locator: string; excerpt: string }[]; provider?: string; model?: string; purpose?: "summary" | "tasks" | "draft" } | null>(null);
  const [aiRequest, setAiRequest] = useState<{ row: Row; purpose: "summary" | "tasks" | "draft" } | null>(null);
  const [aiConsent, setAiConsent] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiError, setAiError] = useState("");
  async function confirmAiRequest() {
    if (!aiRequest || !aiConsent) return;
    setAiBusy(true); setAiError("");
    try {
      const result = await api.post<NonNullable<typeof review>>(`/engagement/documents/${aiRequest.row.id}/assist`, { purpose: aiRequest.purpose, consent: true });
      setReview({ ...result, purpose: aiRequest.purpose }); setAiRequest(null); setAiConsent(false);
    } catch (reason) { setAiError(errorText(reason)); } finally { setAiBusy(false); }
  }
  async function attachVersion(row: Row, file: File) {
    if (!storage.data?.direct_uploads || !row.client_id) {
      const data = new FormData(); data.set("file", file); data.set("expected_version", String(row.current_version));
      await apiClient(`/workspace/documents/${row.id}/upload`, { method: "POST", body: data });
      return;
    }
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer())), value => value.toString(16).padStart(2, "0")).join("");
    const session = await api.post<{ id: string; upload_url: string; upload_headers: Record<string, string> }>("/workspace/document-uploads", {
      client_id: row.client_id, case_id: row.case_id || null, folder_id: row.folder_id || null,
      document_id: row.id, expected_version: row.current_version, filename: file.name, size: file.size, sha256: digest,
    });
    const sent = await fetch(session.upload_url, { method: "PUT", headers: session.upload_headers, body: file, referrerPolicy: "no-referrer" });
    if (!sent.ok) throw new Error("O armazenamento recusou o envio.");
    await api.post(`/workspace/document-uploads/${session.id}/complete`, {});
    for (let attempt = 0; attempt < 45; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const state = await api.get<{ status: string; error?: string }>(`/workspace/document-uploads/${session.id}`);
      if (state.status === "completed") return;
      if (state.status === "failed") throw new Error(state.error || "O arquivo não passou pela verificação.");
    }
    throw new Error("O arquivo continua em verificação. Atualize a lista em alguns minutos.");
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    const body = editing ? { title: values.get("title"), content_text: values.get("content_text"), content_format: values.get("content_format"), expected_version: Number(values.get("draft_version")), expected_revision: Number(values.get("draft_revision")) }
      : { title: values.get("title"), case_id: templates ? null : values.get("case_id") || null, kind: templates ? "template" : "document", document_type: values.get("document_type") || "general", content_text: values.get("content_text"), content_format: values.get("content_format") };
    setBusy(true); setError("");
    try { if (editing) await api.put(`${base}/${editing.id}`, body); else await api.post(base, body); draft.setDirty(false); setEditing(null); setCreating(false); form.reset(); resource.reload(); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const newLabel = templates ? "Criar modelo" : "Novo documento";
  const closeEditor = () => { if (draft.discard()) { draft.setDirty(false); setEditing(null); setCreating(false); } };
  const editorContent = <>
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-zinc-400">Escolha como começar; nenhum rascunho é salvo ou enviado sem sua confirmação.</p><div className="flex flex-wrap gap-2"><button type="button" className={primary} onClick={() => { if (draft.discard()) { setKitOpen(false); setEditing(null); setCreating(true); setEditorView("write"); scrollWorkspaceToTop(); } }}>{templates ? newLabel : "Começar em branco"}</button>{!templates && <><button type="button" className={button} onClick={() => { if (draft.discard()) { setEditing(null); setCreating(false); setKitOpen(value => !value); } }}>{kitOpen ? "Fechar biblioteca" : "Usar modelo guiado"}</button><button type="button" className={button} onClick={() => window.dispatchEvent(new CustomEvent("lexflow:open-ai", { detail: { contextKind: caseId ? "case" : "global", caseId } }))}>Preparar com IA</button></>}</div></div>
    {!templates && kitOpen && <DocumentKit key={caseId || "all"} caseId={caseId} onSaved={resource.reload} />}
    {(creating || editing) && <Panel title={editing ? `Editar: ${editing.title} · versão ${editing.current_version}` : newLabel}>
      <form ref={formRef} key={editing?.id || "new"} onSubmit={save} onChange={() => draft.setDirty(true)} className="space-y-3"><fieldset disabled={busy} className="min-w-0 space-y-3">
        {editing && <><input type="hidden" name="draft_version" defaultValue={editing.current_version} /><input type="hidden" name="draft_revision" defaultValue={editing.revision} /></>}
        {!templates && !editing && <Field label="Preencher com um modelo (revise antes de salvar)"><select className={control} defaultValue="" onChange={e => {
          const model = models.data?.items.find(row => row.id === e.target.value); const form = formRef.current; if (!model || !form) return;
          (form.elements.namedItem("title") as HTMLInputElement).value = model.title;
          (form.elements.namedItem("content_text") as HTMLTextAreaElement).value = model.content_text || "";
          (form.elements.namedItem("content_format") as HTMLSelectElement).value = model.content_format || "plain";
          (form.elements.namedItem("document_type") as HTMLSelectElement).value = model.document_type || "general";
          const preview = form.querySelector<HTMLElement>("[data-document-preview]"); if (preview) preview.textContent = model.content_text || "Comece a escrever para revisar a leitura do documento.";
        }}><option value="">Documento em branco</option>{models.data?.items.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.current_version}</option>)}</select></Field>}
        <div className="grid sm:grid-cols-2 gap-3"><Field label="Título"><input className={control} name="title" required maxLength={200} defaultValue={editing?.title || ""} /></Field>
          {!templates && <Field label="Processo"><select key={Boolean(cases.data).toString()} className={control} name="case_id" required disabled={Boolean(editing)} defaultValue={editing?.case_id || caseId || ""}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>}
        </div>
        {!editing && <Field label="Tipo de documento"><select className={control} name="document_type" defaultValue="general">{DOCUMENT_TYPES.map(type => <option key={type} value={type}>{documentTypeLabels[type]}</option>)}</select></Field>}
        <input type="hidden" name="content_format" value={editing?.content_format || "plain"} />
        <section aria-labelledby="document-text-label" className="min-w-0 space-y-2"><div className="flex flex-wrap items-center justify-between gap-2"><label id="document-text-label" htmlFor="document-text" className="text-sm font-medium text-zinc-300">Texto do documento</label><div className="flex gap-1 md:hidden"><button type="button" className={`${button} px-2 ${editorView === "write" ? "border-blue-500 text-blue-100" : ""}`} aria-pressed={editorView === "write"} onClick={() => setEditorView("write")}>Editar</button><button type="button" className={`${button} px-2 ${editorView === "preview" ? "border-blue-500 text-blue-100" : ""}`} aria-pressed={editorView === "preview"} onClick={() => setEditorView("preview")}>Prévia</button></div></div><div className="grid min-w-0 gap-3 md:grid-cols-2"><div className={editorView === "preview" ? "hidden md:block" : "min-w-0"}><textarea id="document-text" aria-label="Texto do documento" className={`${control} font-sans leading-relaxed`} name="content_text" rows={16} maxLength={100000} defaultValue={editing?.content_text || ""} onInput={event => { const preview = event.currentTarget.closest("form")?.querySelector<HTMLElement>("[data-document-preview]"); if (preview) preview.textContent = event.currentTarget.value || "Comece a escrever para revisar a leitura do documento."; }} /></div><aside className={`${editorView === "write" ? "hidden md:block" : ""} min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4`} aria-live="polite"><h3 className="text-sm font-medium text-zinc-100">Prévia de leitura</h3><p className="mt-1 text-xs text-zinc-400">Confirme a estrutura aqui. A prévia em PDF ou Word usa a versão salva e a identidade documental publicada.</p><p data-document-preview className="mt-4 whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-200">{editing?.content_text || "Comece a escrever para revisar a leitura do documento."}</p></aside></div></section>
        {editing && draft.dirty && <p className="text-xs text-zinc-400">Base preservada do rascunho: versão {draft.initialValues?.draft_version || editing.current_version}. Se houver conflito, cancele a edição e confira o texto atual antes de reaplicar suas alterações.</p>}
        <DraftNotice dirty={draft.dirty} /><State error={error || cases.error || models.error} /><div className="flex flex-wrap gap-2"><button className={primary} disabled={busy}>{busy ? "Salvando…" : editing ? "Salvar nova versão" : templates ? "Salvar modelo" : "Salvar documento"}</button><button type="button" className={button} onClick={closeEditor}>{editing ? "Cancelar edição" : "Cancelar cadastro"}</button></div></fieldset>
      </form>
    </Panel>}
    <Panel title={templates ? "Modelos salvos" : "Documentos salvos"}>
      <State loading={resource.loading} error={resource.error} />
      {!resource.loading && !resource.error && !resource.data?.items.length && <p className="text-sm text-zinc-400">Ainda não há {templates ? "modelos" : "documentos"} salvos. {newLabel} quando estiver pronto para registrar uma versão.</p>}
      <div className="divide-y divide-zinc-800">{resource.data?.items.map(row => <article key={row.id} className="py-3 space-y-2">
        <p className="text-sm font-medium break-words">{row.title} <span className="text-xs text-zinc-400">· v{row.current_version}</span></p>
        <p className="text-xs text-zinc-400">{documentTypeLabels[(row.document_type || "general") as DocumentType]} · {row.filename || "Documento de texto"} · {dateText(row.updated_at || row.created_at)}</p>
        {!templates && <p className="text-xs text-blue-300">Revisão: {({ draft: "Rascunho", in_review: "Em revisão", approved: "Aprovado", final: "Versão final" } as Record<string, string>)[row.review_status || "draft"]}</p>}
        {row.content_text && <details><summary className="min-h-11 content-center cursor-pointer text-sm text-blue-300">Ler documento</summary><div className="whitespace-pre-wrap text-sm leading-relaxed py-3">{row.content_text}</div></details>}
        <div className="flex flex-wrap gap-2">
          <button className={primary} onClick={() => { if (draft.discard()) { draft.setDirty(false); setKitOpen(false); setCreating(false); setEditorView("write"); setEditing(row); scrollWorkspaceToTop(); } }}>{templates ? "Editar modelo" : "Editar documento"}</button>
          <details className="min-w-0"><summary className={`${button} cursor-pointer list-none`}>Mais ações</summary><div className="mt-2 flex flex-wrap gap-2">
          <button className={button} onClick={() => setVersionsFor(row.id)}>Ver histórico</button>
          {!templates && <button className={button} onClick={() => setReviewFor(row.id)}>Revisar e aprovar</button>}
          <button className={button} onClick={() => setExportsFor(row.id)}>Exportar PDF / Word</button>
          {row.filename && <Action run={() => download(`/workspace/documents/${row.id}/download`, row.filename)}>Baixar anexo original</Action>}
          {!templates && <label className={`${button} cursor-pointer`}>Anexar nova versão<input aria-label={`Anexar arquivo a ${row.title}`} type="file" className="sr-only" onChange={async e => {
            const file = e.target.files?.[0]; if (!file) return; setError("");
            if (file.size > 25 * 1024 * 1024) { setError("Arquivo maior que 25 MB."); return; }
            try { await attachVersion(row, file); resource.reload(); } catch (err) { setError(errorText(err)); }
          }} accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png" /></label>}
          {!templates && <><button type="button" className={button} onClick={() => { setAiRequest({ row, purpose: "summary" }); setAiConsent(false); setAiError(""); }}>Resumir com IA</button><button type="button" className={button} onClick={() => { setAiRequest({ row, purpose: "tasks" }); setAiConsent(false); setAiError(""); }}>Extrair tarefas para revisão</button><button type="button" className={button} onClick={() => { setAiRequest({ row, purpose: "draft" }); setAiConsent(false); setAiError(""); }}>Sugerir nova redação</button></>}</div></details>
        </div>
      </article>)}</div>
    </Panel>
    {exportsFor && resource.data?.items.filter(row => row.id === exportsFor).map(row => <DocumentExports key={`${row.id}:${row.current_version}`} document={row} onClose={() => setExportsFor(null)} />)}
    {reviewFor && resource.data?.items.filter(row => row.id === reviewFor).map(row => <DocumentReview key={`${row.id}:${row.revision}`} document={row} onClose={() => setReviewFor(null)} onChanged={resource.reload} />)}
    {versionsFor && <Panel title="Histórico preservado"><State loading={versions.loading} error={versions.error} />{versions.data?.items.map(row => <details key={row.id} className="border-b border-zinc-800 py-2"><summary className="cursor-pointer text-sm">Versão {row.version} · {dateText(row.created_at)}</summary><pre className="whitespace-pre-wrap break-words text-xs text-zinc-400 mt-2">{row.content_text || row.filename || "Arquivo binário"}</pre></details>)}<button className={button} onClick={() => setVersionsFor(null)}>Fechar histórico</button></Panel>}
    {aiRequest && <Panel title="Confirmar envio para a IA"><p className="text-sm text-zinc-300">A versão atual de <strong>{aiRequest.row.title}</strong> será enviada ao serviço de IA para {aiRequest.purpose === "summary" ? "produzir um resumo" : aiRequest.purpose === "tasks" ? "sugerir tarefas" : "sugerir uma nova redação"}. O resultado exige revisão humana e não será salvo automaticamente.</p><label className="flex min-h-11 items-start gap-3 text-sm text-zinc-300"><input type="checkbox" className="mt-1 h-4 w-4" checked={aiConsent} onChange={event => setAiConsent(event.target.checked)} />Autorizo este envio específico e confirmei que posso compartilhar os dados deste documento para a análise.</label><State error={aiError} /><div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={!aiConsent || aiBusy} onClick={confirmAiRequest}>{aiBusy ? "Enviando…" : "Autorizar e enviar"}</button><button type="button" className={button} disabled={aiBusy} onClick={() => { setAiRequest(null); setAiConsent(false); setAiError(""); }}>Cancelar</button></div></Panel>}
    {review && <Panel title="Resultado da IA — revisão humana obrigatória"><p className="text-xs text-amber-300">Documento analisado: versão {review.source.version}. {review.stale && "O documento mudou durante a geração; confira a versão atual. "}Confirme todas as afirmações no documento original. Este resultado não foi salvo nem protocolado.</p><div className="whitespace-pre-wrap break-words text-sm leading-relaxed">{review.text}</div>{review.sources?.length ? <details className="rounded-lg border border-zinc-800 p-3"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium">Trechos citados ({review.sources.length})</summary><div className="mt-2 space-y-2">{review.sources.map(source => <article key={source.citation_id} className="rounded bg-zinc-950 p-2 text-xs"><strong>{source.label}</strong><p className="mt-1 whitespace-pre-wrap text-zinc-400">{source.excerpt}</p></article>)}</div></details> : null}<div className="flex flex-wrap gap-2"><button className={button} onClick={() => navigator.clipboard.writeText(review.text)}>Copiar resultado</button><button className={button} onClick={() => setReview(null)}>Descartar resultado</button></div></Panel>}
  </>;
  const content = templates ? editorContent : <><nav aria-label="Área de documentos" className="flex flex-wrap gap-2 border-b border-zinc-800 pb-4"><button className={section === "files" ? primary : button} aria-pressed={section === "files"} onClick={() => setSection("files")}>Arquivos</button><button className={section === "create" ? primary : button} aria-pressed={section === "create"} onClick={() => setSection("create")}>Criar documento</button><button className={section === "ai" ? primary : button} aria-pressed={section === "ai"} onClick={() => setSection("ai")}>Analisar e preparar com IA</button></nav>{section === "files" ? <FileCenter caseId={caseId} embedded /> : section === "ai" ? <LegalAiWorkbench caseId={caseId} onSaved={resource.reload} /> : editorContent}</>;
  return embedded ? <section aria-label="Documentos do caso" className="space-y-4">{content}</section> : <Page title={templates ? "Biblioteca de modelos do escritório" : "Central de Arquivos"} subtitle={templates ? "Modelos reutilizáveis e versionados do escritório." : "Consulte arquivos por cliente ou processo e crie documentos com modelos, identidade visual e IA."}>{content}</Page>;
}
