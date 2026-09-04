"use client";
import { useMemo, useRef, useState } from "react";
import { Camera, FileText, Folder, FolderOpen, Search, Share2, Trash2, UploadCloud } from "lucide-react";
import { api, apiClient } from "@/lib/api-client";
import { Action, Field, Panel, State, button, control, dateText, download, errorText, primary, useResource } from "./shared";
import type { List, Row } from "./records";

type UploadSession = { id: string; status: string; document_id?: string; upload_url: string; upload_headers: Record<string, string>; error?: string };

async function sha256(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
}

function folderPaths(folders: Row[]) {
  const byId = new Map(folders.map(folder => [folder.id, folder]));
  const path = (folder: Row) => {
    const names = [String(folder.name)]; let cursor = folder; let guard = 0;
    while (cursor.parent_id && guard++ < 8) { const parent = byId.get(cursor.parent_id); if (!parent || parent.id === cursor.id) break; cursor = parent; names.unshift(String(cursor.name)); }
    return names.join(" / ");
  };
  return [...folders].sort((a, b) => path(a).localeCompare(path(b), "pt-BR")).map(folder => ({ ...folder, path: path(folder) }));
}

export function FileCenter({ clientId, caseId, embedded = false, captureOnMobile = false }: { clientId?: string; caseId?: string; embedded?: boolean; captureOnMobile?: boolean }) {
  const clients = useResource<List>(clientId || caseId ? null : "/workspace/clients?limit=200");
  const cases = useResource<List>("/workspace/cases?limit=200");
  const [selectedClient, setSelectedClient] = useState(clientId || "");
  const fixedCase = caseId || "";
  const currentCase = cases.data?.items.find(row => row.id === fixedCase);
  const effectiveClient = clientId || currentCase?.client_id || selectedClient;
  const relatedCases = cases.data?.items.filter(row => row.client_id === effectiveClient) || [];
  const [scope, setScope] = useState(caseId || "general");
  const effectiveCase = fixedCase || (scope === "general" ? "" : scope);
  const [folderId, setFolderId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [uploading, setUploading] = useState(false); const [newFolder, setNewFolder] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);
  const folderQuery = effectiveClient ? `/workspace/document-folders?client_id=${encodeURIComponent(effectiveClient)}${effectiveCase ? `&case_id=${encodeURIComponent(effectiveCase)}` : ""}` : null;
  const folders = useResource<{ items: Row[] }>(folderQuery);
  const storage = useResource<{ direct_uploads: boolean }>(effectiveClient ? "/workspace/document-storage" : null);
  const fileQuery = effectiveClient ? `/workspace/documents?client_id=${encodeURIComponent(effectiveClient)}${effectiveCase ? `&case_id=${encodeURIComponent(effectiveCase)}` : "&general_only=true"}${query.trim() ? `&q=${encodeURIComponent(query.trim())}` : ""}&limit=200` : null;
  const files = useResource<List>(fileQuery);
  const orderedFolders = useMemo(() => folderPaths(folders.data?.items || []), [folders.data]);
  const visibleFiles = files.data?.items.filter(row => query.trim() || (row.folder_id || null) === folderId) || [];
  const invites = useResource<{ items: Row[] }>(effectiveCase ? `/engagement/cases/${effectiveCase}/portal-invites` : null);
  const shares = useResource<{ items: Row[] }>(effectiveCase ? `/engagement/cases/${effectiveCase}/folder-shares` : null);

  async function upload(file: File) {
    if (!effectiveClient) return;
    setUploading(true); setError(""); setNotice("");
    try {
      if (file.size > 25 * 1024 * 1024) throw new Error("O arquivo excede 25 MB.");
      if (!storage.data) throw new Error("Aguarde a verificação do armazenamento e tente novamente.");
      if (storage.data && !storage.data.direct_uploads) {
        const body = new FormData(); body.set("client_id", effectiveClient); if (effectiveCase) body.set("case_id", effectiveCase); if (folderId) body.set("folder_id", folderId); body.set("file", file);
        await apiClient("/workspace/documents/upload-file", { method: "POST", body });
        setNotice("Arquivo salvo no armazenamento local de desenvolvimento."); files.reload(); return;
      }
      const session = await api.post<UploadSession>("/workspace/document-uploads", {
        client_id: effectiveClient, case_id: effectiveCase || null, folder_id: folderId,
        filename: file.name, size: file.size, sha256: await sha256(file),
      });
      const response = await fetch(session.upload_url, { method: "PUT", headers: session.upload_headers, body: file, referrerPolicy: "no-referrer" });
      if (!response.ok) throw new Error("O armazenamento recusou o envio. Confira a configuração CORS do bucket.");
      await api.post(`/workspace/document-uploads/${session.id}/complete`, {});
      let completed = false;
      for (let attempt = 0; attempt < 45; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const status = await api.get<UploadSession>(`/workspace/document-uploads/${session.id}`);
        if (status.status === "completed") { setNotice("Arquivo verificado e disponível."); files.reload(); completed = true; break; }
        if (status.status === "failed") throw new Error(status.error || "O arquivo não passou pela verificação de segurança.");
      }
      if (!completed) throw new Error("A verificação continua em andamento. Consulte esta pasta novamente em instantes.");
    } catch (reason) { setError(errorText(reason)); }
    finally { setUploading(false); if (uploadRef.current) uploadRef.current.value = ""; }
  }

  const content = <>
    {!caseId && <div className="grid gap-3 md:grid-cols-2">
      {!clientId && <Field label="Cliente"><select className={control} value={effectiveClient} onChange={event => { setSelectedClient(event.target.value); setScope("general"); setFolderId(null); }}><option value="">Selecione o cliente</option>{clients.data?.items.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>}
      {effectiveClient && <Field label="Local dos arquivos"><select className={control} value={scope} onChange={event => { setScope(event.target.value); setFolderId(null); }}><option value="general">Documentos gerais do cliente</option>{relatedCases.map(row => <option key={row.id} value={row.id}>{row.title} · {row.number || "sem número"}</option>)}</select></Field>}
    </div>}
    {!effectiveClient ? <State empty emptyText="Selecione um cliente para consultar seus arquivos." /> : <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <Field label="Buscar nos nomes e no conteúdo"><div className="relative"><Search className="absolute left-3 top-3.5 text-zinc-500" size={17} aria-hidden="true" /><input className={`${control} pl-10`} type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Nome, trecho, processo…" /></div></Field>
        <div className="flex flex-wrap gap-2"><label className={`${primary} cursor-pointer`}><UploadCloud size={17} aria-hidden="true" className="mr-2" />{uploading ? "Verificando…" : "Enviar arquivo"}<input ref={uploadRef} className="sr-only" type="file" disabled={uploading || storage.loading} accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png" onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); }} /></label>{captureOnMobile && <label className={`${button} cursor-pointer sm:hidden`}><Camera size={17} aria-hidden="true" className="mr-2" />Fotografar comprovante<input className="sr-only" type="file" capture="environment" disabled={uploading || storage.loading} accept="image/jpeg,image/png" onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); event.currentTarget.value = ""; }} /></label>}<button className={button} onClick={() => setNewFolder(true)}><Folder size={17} aria-hidden="true" className="mr-2" />Nova pasta</button></div>
      </div>
      <State error={error || folders.error || files.error} />{notice && <p role="status" className="text-sm text-green-300">{notice}</p>}
      {newFolder && <form className="grid gap-3 rounded-lg border border-zinc-800 p-4 sm:grid-cols-[1fr_auto]" onSubmit={async event => { event.preventDefault(); const form = event.currentTarget; const name = new FormData(form).get("name"); setError(""); try { await api.post("/workspace/document-folders", { client_id: effectiveClient, case_id: effectiveCase || null, parent_id: folderId, name }); form.reset(); setNewFolder(false); folders.reload(); } catch (reason) { setError(errorText(reason)); } }}><Field label={folderId ? "Nome da subpasta" : "Nome da pasta"}><input className={control} name="name" required maxLength={160} autoFocus /></Field><div className="flex items-end gap-2"><button className={primary}>Criar pasta</button><button type="button" className={button} onClick={() => setNewFolder(false)}>Cancelar</button></div></form>}
      <div className="grid min-w-0 gap-5 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <nav aria-label="Pastas" className="min-w-0 space-y-1 border-r-0 border-zinc-800 lg:border-r lg:pr-4"><button className={`${folderId === null ? primary : button} w-full justify-start`} onClick={() => setFolderId(null)}><FolderOpen size={17} className="mr-2" aria-hidden="true" />Início</button>{orderedFolders.map(folder => <button key={folder.id} className={`${folderId === folder.id ? primary : button} w-full justify-start overflow-hidden`} title={folder.path} onClick={() => setFolderId(folder.id)}><Folder size={16} className="mr-2 shrink-0" aria-hidden="true" /><span className="truncate">{folder.path}</span></button>)}</nav>
        <section className="min-w-0 space-y-3" aria-label="Arquivos da pasta">
          <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium">{query ? `Resultados para “${query}”` : folderId ? orderedFolders.find(folder => folder.id === folderId)?.path : "Arquivos sem pasta"}</p>{folderId && <Action className={button} run={async () => { await api.delete(`/workspace/document-folders/${folderId}`); setFolderId(null); folders.reload(); }}>Remover pasta vazia</Action>}</div>
          <State loading={files.loading || folders.loading} empty={!files.loading && !visibleFiles.length} emptyText={query ? "Nenhum arquivo corresponde à busca." : "Esta pasta ainda está vazia."} />
          <div className="divide-y divide-zinc-800">{visibleFiles.map(row => <article key={row.id} className="flex min-w-0 flex-col gap-3 py-3 sm:flex-row sm:items-center"><FileText className="shrink-0 text-blue-300" aria-hidden="true" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{row.title}</p><p className="truncate text-xs text-zinc-400">{row.filename || "Documento criado no LexFlow"} · {row.file_size ? `${Math.max(1, Math.round(Number(row.file_size) / 1024))} KB` : "texto"} · {dateText(row.updated_at)}</p>{query && row.content_text && <p className="mt-1 line-clamp-2 text-xs text-zinc-500">{row.content_text}</p>}</div><div className="flex flex-wrap gap-2"><Action className={primary} run={() => download(`/workspace/documents/${row.id}/download`, row.filename || `${row.title}.txt`)}>Baixar</Action><details><summary className={`${button} cursor-pointer list-none`}>Mais</summary><div className="mt-2 flex flex-wrap gap-2 sm:absolute sm:right-8 sm:z-10 sm:rounded-lg sm:border sm:border-zinc-700 sm:bg-zinc-950 sm:p-2"><label className="text-xs"><span className="sr-only">Mover arquivo</span><select className={control} value={row.folder_id || ""} onChange={async event => { try { await api.put(`/workspace/documents/${row.id}/move`, { folder_id: event.target.value || null, expected_revision: row.revision }); files.reload(); } catch (reason) { setError(errorText(reason)); } }}><option value="">Sem pasta</option>{orderedFolders.map(folder => <option key={folder.id} value={folder.id}>{folder.path}</option>)}</select></label><Action className={button} run={async () => { if (!confirm("Mover este arquivo para a lixeira por 30 dias?")) return; await api.delete(`/workspace/documents/${row.id}`); files.reload(); }}><Trash2 size={15} className="mr-1" aria-hidden="true" />Lixeira</Action></div></details></div></article>)}</div>
          {effectiveCase && folderId && <Panel title="Compartilhar esta pasta no portal"><p className="text-xs text-zinc-400">O cliente verá esta pasta, suas subpastas e os arquivos adicionados futuramente. O convite continua restrito a este processo.</p><form className="grid gap-3 sm:grid-cols-[1fr_auto]" onSubmit={async event => { event.preventDefault(); const data = new FormData(event.currentTarget); try { await api.post(`/engagement/cases/${effectiveCase}/folder-shares`, { grant_id: data.get("grant_id"), folder_id: folderId, can_upload: data.get("can_upload") === "on" }); shares.reload(); setNotice("Pasta compartilhada com o convite selecionado."); } catch (reason) { setError(errorText(reason)); } }}><div className="space-y-2"><Field label="Convite ativo"><select name="grant_id" className={control} required><option value="">Selecione</option>{invites.data?.items.filter(row => !row.revoked_at && new Date(String(row.expires_at)) > new Date()).map(row => <option key={row.id} value={row.id}>Acesso até {dateText(row.expires_at)}</option>)}</select></Field><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" name="can_upload" />Permitir que o cliente envie arquivos</label></div><button className={button}><Share2 size={16} className="mr-2" aria-hidden="true" />Compartilhar</button></form>{shares.data?.items.filter(row => row.folder_id === folderId).map(row => <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 text-xs"><span>Compartilhada · {row.can_upload ? "envio permitido" : "somente leitura"}</span><Action run={async () => { await api.delete(`/engagement/folder-shares/${row.id}`); shares.reload(); }}>Revogar</Action></div>)}</Panel>}
        </section>
      </div>
    </>}
  </>;
  return embedded ? <section className="space-y-4" aria-label="Central de arquivos">{content}</section> : <Panel title="Arquivos por cliente e processo">{content}</Panel>;
}
