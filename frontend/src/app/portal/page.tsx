"use client";
import { useEffect, useRef, useState } from "react";
import { api, apiClient } from "@/lib/api-client";
import { Action, Field, Page, Panel, State, control, dateText, download, errorText, primary, useResource } from "@/components/workspace/shared";
import type { Row } from "@/components/workspace/records";
export default function PortalPage() {
  const [token, setToken] = useState(""); const [error, setError] = useState(""); const [requestId, setRequestId] = useState(() => crypto.randomUUID()); const [busy, setBusy] = useState(false); const [uploading, setUploading] = useState(""); const [section, setSection] = useState<"documents" | "messages">("documents");
  const markedRead = useRef("");
  const portal = useResource<Row>("/client-portal");
  useEffect(() => { const value = new URLSearchParams(location.hash.slice(1)).get("token"); if (value) { setToken(value); history.replaceState(null, "", location.pathname); } }, []);
  useEffect(() => {
    if (!portal.data || section !== "messages") return;
    const fingerprint = portal.data.messages.filter((message: Row) => message.direction === "outbound" && !message.read_at).map((message: Row) => message.id).join(":");
    if (!fingerprint || markedRead.current === fingerprint) return;
    markedRead.current = fingerprint;
    void api.post("/client-portal/messages/read", {}).catch(() => { markedRead.current = ""; });
  }, [portal.data, section]);
  return <main className="p-4 md:p-10"><Page title="Portal do cliente" subtitle="Acompanhe o caso e converse com seu escritório em um ambiente privado.">
    {token && <Panel title="Confirmar acesso"><p className="text-sm text-zinc-400">Use apenas o link recebido diretamente do seu escritório. Este acesso é pessoal e não deve ser compartilhado.</p><Action run={async () => { await api.post("/client-portal/redeem", { token }); setToken(""); portal.reload(); }}>Entrar com o convite recebido</Action></Panel>}
    <State loading={portal.loading} error={error || (!token ? portal.error : "")} />
    {!token && !portal.loading && !portal.data && <p className="text-sm text-zinc-400">Entre pelo link seguro enviado pelo escritório. Se já o utilizou ou ele expirou, solicite um novo acesso.</p>}
    {portal.data && <>
      <Panel title={portal.data.case.title}><p className="text-sm text-zinc-400">{portal.data.case.number || "Atendimento sem número judicial"} · {portal.data.case.status}</p><Action run={async () => { await api.post("/client-portal/logout", {}); portal.reload(); }}>Encerrar acesso</Action></Panel>
      <nav aria-label="Conteúdo do portal" className="grid grid-cols-2 gap-2 rounded-xl border border-zinc-800 p-1"><button type="button" className={section === "documents" ? primary : "min-h-11 rounded-lg text-sm text-zinc-300"} aria-pressed={section === "documents"} onClick={() => setSection("documents")}>Documentos</button><button type="button" className={section === "messages" ? primary : "min-h-11 rounded-lg text-sm text-zinc-300"} aria-pressed={section === "messages"} onClick={() => setSection("messages")}>Mensagens</button></nav>
      {section === "documents" && <><Panel title="Documentos e solicitações">{portal.data.checklist.map((item: Row) => <div key={item.id} className="flex flex-wrap justify-between gap-2 border-b border-zinc-800 pb-3"><p className="text-sm">{item.title}</p>{item.has_document ? <Action run={() => download(`/client-portal/documents/${item.id}`, "documento")}>Baixar documento compartilhado</Action> : <Field label="Enviar arquivo (até 25 MB)"><input className="text-xs max-w-full" type="file" accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png" onChange={async e => {
        const file = e.target.files?.[0]; if (!file) return; setError(""); if (file.size > 25 * 1048576) { setError("Arquivo maior que 25 MB."); return; }
        const data = new FormData(); data.set("file", file); try { await apiClient(`/client-portal/documents/${item.id}/upload`, { method: "POST", body: data }); portal.reload(); } catch (err) { setError(errorText(err)); }
      }} /></Field>}</div>)}</Panel>
      {!!portal.data.folders?.length && <Panel title="Pastas compartilhadas"><p className="text-xs text-zinc-400">O escritório escolheu estas pastas deste processo. Arquivos jurídicos não ficam disponíveis offline.</p><div className="space-y-4">{portal.data.folders.map((folder: Row) => <section key={folder.id} className="rounded-lg border border-zinc-800 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium">{folder.name}</p>{folder.can_upload && <label className={`${primary} cursor-pointer`}>{uploading === folder.id ? "Verificando…" : "Enviar arquivo"}<input className="sr-only" type="file" disabled={Boolean(uploading)} accept=".pdf,.docx,.xlsx,.txt,.jpg,.jpeg,.png" onChange={async event => {
        const file = event.target.files?.[0]; if (!file) return; setUploading(folder.id); setError("");
        const input = event.currentTarget;
        try {
            if (file.size > 25 * 1024 * 1024) throw new Error("O arquivo excede 25 MB.");
            const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer())), value => value.toString(16).padStart(2, "0")).join("");
            const session = await api.post<{ id: string; upload_url: string; upload_headers: Record<string, string> }>("/client-portal/file-uploads", { folder_id: folder.id, filename: file.name, size: file.size, sha256: digest });
            const sent = await fetch(session.upload_url, { method: "PUT", headers: session.upload_headers, body: file, referrerPolicy: "no-referrer" });
            if (!sent.ok) throw new Error("O armazenamento recusou o envio.");
            await api.post(`/client-portal/file-uploads/${session.id}/complete`, {});
            let completed = false;
            for (let attempt = 0; attempt < 45; attempt++) { await new Promise(resolve => setTimeout(resolve, 2000)); const status = await api.get<{ status: string; error?: string }>(`/client-portal/file-uploads/${session.id}`); if (status.status === "completed") { portal.reload(); completed = true; break; } if (status.status === "failed") throw new Error(status.error || "O arquivo não passou pela verificação."); }
            if (!completed) throw new Error("A verificação continua em andamento. Atualize a página em instantes.");
          } catch (reason) { setError(errorText(reason)); } finally { setUploading(""); input.value = ""; }
        }} /></label>}</div><div className="mt-3 divide-y divide-zinc-800">{portal.data?.files?.filter((file: Row) => file.folder_id === folder.id).map((file: Row) => <div key={file.id} className="flex flex-wrap items-center justify-between gap-2 py-2"><div className="min-w-0"><p className="truncate text-sm">{file.title}</p><p className="truncate text-xs text-zinc-500">{file.filename || "Documento"} · {dateText(file.updated_at)}</p></div><Action run={() => download(`/client-portal/files/${file.id}`, file.filename || "documento")}>Baixar</Action></div>)}</div></section>)}</div></Panel>}</>}
      {section === "messages" && <Panel title="Conversa com o escritório"><form className="space-y-3" onSubmit={async e => { e.preventDefault(); const form = e.currentTarget; const body = new FormData(form).get("body"); setBusy(true); setError(""); try { await api.post("/client-portal/messages", { body, channel: "portal", request_id: requestId }); form.reset(); setRequestId(crypto.randomUUID()); portal.reload(); } catch (err) { setError(errorText(err)); } finally { setBusy(false); } }}><Field label="Mensagem"><textarea className={control} name="body" rows={3} maxLength={8000} required /></Field><button className={primary} disabled={busy}>Enviar mensagem</button></form>
        {portal.data.messages.map((row: Row) => <article key={row.id} className="border-b border-zinc-800 pb-3"><p className="text-xs text-zinc-500">{row.direction === "inbound" ? "Você" : "Escritório"} · {dateText(row.created_at)}</p><p className="text-sm whitespace-pre-wrap break-words">{row.body}</p></article>)}
      </Panel>}
    </>}
  </Page></main>;
}
