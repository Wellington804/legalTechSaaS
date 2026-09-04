"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { Action, Field, Page, Panel, State, control, dateText, errorText, primary, useResource } from "./shared";
import { display, type List, type Row } from "./records";
import { formatBrazilianPhone } from "@/lib/phone";

type WhatsAppStatus = { status: string; connected: boolean; number?: string; last_checked_at?: string; verification_unavailable?: boolean };

function verificationText(value?: string) {
  if (!value) return "Ainda não verificado";
  const date = new Date(value); if (Number.isNaN(date.valueOf())) return "Ainda não verificado";
  const today = new Date(); const sameDay = date.toDateString() === today.toDateString();
  return `${sameDay ? "hoje" : date.toLocaleDateString("pt-BR")}, ${date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function Communications() {
  const { user } = useUser(); const cases = useResource<List>("/workspace/cases"); const [caseId, setCaseId] = useState("");
  const messages = useResource<List>(caseId ? `/engagement/cases/${caseId}/messages` : null);
  const documents = useResource<List>(caseId ? `/workspace/documents?case_id=${caseId}` : null);
  const checklist = useResource<List>(caseId ? `/engagement/cases/${caseId}/checklist` : null);
  const invites = useResource<List>(caseId ? `/engagement/cases/${caseId}/portal-invites` : null);
  const admin = isOfficeAdminRole(user.role);
  const channels = useResource<{ whatsapp: WhatsAppStatus }>("/engagement/channels");
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false); const [link, setLink] = useState("");
  const [accessDays, setAccessDays] = useState("7");
  const [qrCode, setQrCode] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const whatsapp = channels.data?.whatsapp;
  useEffect(() => {
    if (whatsapp?.connected) { setQrCode(""); return; }
    if (whatsapp?.status !== "pending") return;
    const refresh = async () => {
      channels.reload();
      if (!qrCode && admin) {
        try { const result = await api.get<{ qr_code?: string }>("/engagement/whatsapp/qr"); if (result.qr_code) setQrCode(result.qr_code); } catch { /* status card keeps the actionable provider error */ }
      }
    };
    const timer = window.setInterval(refresh, 3000);
    return () => window.clearInterval(timer);
  }, [admin, channels.reload, qrCode, whatsapp?.connected, whatsapp?.status]);

  return <Page title="Comunicações e portal" subtitle="Selecione um processo para enviar, acompanhar recibos e controlar o acesso do cliente.">
    <Panel title="WhatsApp do escritório">
      <div className="space-y-5 rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        <div><p className="font-medium">Status: {whatsapp?.connected ? "Conectado" : whatsapp?.status === "pending" ? qrCode ? "Aguardando leitura do QR Code" : "Conectando" : "Desconectado"}</p>
          {whatsapp?.connected ? <dl className="mt-2 grid gap-1 text-sm text-zinc-400"><div className="flex gap-2"><dt>Número:</dt><dd className="text-zinc-200">{formatBrazilianPhone(whatsapp.number || "") || "Número conectado"}</dd></div><div className="flex gap-2"><dt>Última verificação:</dt><dd className="text-zinc-200">{verificationText(whatsapp.last_checked_at)}</dd></div></dl>
            : <p className="mt-2 max-w-xl text-sm text-zinc-400">Conecte o WhatsApp para enviar mensagens e acompanhar confirmações pelo LexFlow.</p>}
          {whatsapp?.verification_unavailable && <p role="status" className="mt-2 text-sm text-amber-300">Não foi possível atualizar o estado agora. A última informação confirmada foi mantida.</p>}
        </div>
        {qrCode && !whatsapp?.connected && <div className="max-w-sm rounded-xl border border-blue-700 bg-blue-950/30 p-4"><p className="mb-3 text-sm font-medium">Leia este QR Code no WhatsApp</p><Image src={qrCode} width={256} height={256} unoptimized alt="QR Code para conectar o WhatsApp do escritório" className="mx-auto rounded-lg bg-white p-2" /></div>}
        {admin && <div className="flex flex-wrap gap-2">{whatsapp?.connected ? <><Action className={primary} run={() => api.post("/engagement/whatsapp/reconnect", {})} onDone={() => { channels.reload(); setMessage("Reconexão iniciada."); }}>Reconectar</Action><Action run={async () => { if (!window.confirm("Desconectar o WhatsApp deste escritório? Será necessário ler um novo QR Code para conectar novamente.")) return; await api.delete("/engagement/whatsapp/connection"); setQrCode(""); channels.reload(); setMessage("WhatsApp desconectado."); }}>Desconectar</Action></>
          : whatsapp?.status === "pending" ? <Action run={async () => { const result = await api.get<{ qr_code?: string }>("/engagement/whatsapp/qr"); setQrCode(result.qr_code || ""); }}>Atualizar QR Code</Action>
          : <Action className={primary} run={async () => { const result = await api.post<{ qr_code?: string }>("/engagement/whatsapp/connect", {}); setQrCode(result.qr_code || ""); channels.reload(); setMessage(result.qr_code ? "QR Code pronto para leitura." : "Conexão iniciada. Aguarde o QR Code."); }}>Conectar WhatsApp</Action>}</div>}
        {!whatsapp?.connected && <div className="border-t border-zinc-800 pt-4"><p className="text-sm font-medium">Como conectar:</p><ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-zinc-400"><li>Clique em conectar</li><li>Leia o QR Code com o WhatsApp</li><li>Aguarde a confirmação</li></ol></div>}
      </div><State loading={channels.loading} error={channels.error} />
    </Panel>
    <Panel title="Selecionar processo"><Field label="Processo"><select className={control} value={caseId} onChange={event => { setCaseId(event.target.value); setLink(""); setRequestId(crypto.randomUUID()); }}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><State error={cases.error || error} />{message && <p role="status" className="text-sm text-green-300">{message}</p>}</Panel>
    {caseId && <>
      <Panel title="Enviar ao cliente"><form className="space-y-3" onSubmit={async event => {
        event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setError(""); setBusy(true);
        try { const result = await api.post<Row>(`/engagement/cases/${caseId}/messages`, { body: data.get("body"), channel: data.get("channel"), request_id: requestId }); form.reset(); setRequestId(crypto.randomUUID()); setMessage(`Mensagem registrada. Situação: ${display(result.status)}.`); messages.reload(); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
      }}><Field label="Canal"><select className={control} name="channel"><option value="portal">Portal do cliente</option><option value="email">E-mail</option><option value="whatsapp">WhatsApp</option></select></Field><Field label="Mensagem"><textarea className={control} rows={4} name="body" required maxLength={8000} onChange={() => { if (error) { setRequestId(crypto.randomUUID()); setError(""); } }} /></Field><button className={primary} disabled={busy}>{busy ? "Registrando…" : "Registrar ou enviar mensagem"}</button></form></Panel>
      <Panel title="Acesso do cliente"><div className="grid gap-4 md:grid-cols-3"><div><p className="text-xs text-zinc-500">1. Validade</p><Field label="Tempo de acesso"><select className={control} value={accessDays} onChange={event => setAccessDays(event.target.value)}><option value="7">7 dias</option><option value="14">14 dias</option><option value="30">30 dias</option></select></Field></div><div className="md:col-span-2"><p className="text-xs text-zinc-500">2. Criar e compartilhar</p><p className="mt-2 text-xs text-zinc-400">O link é pessoal, de uso único e válido por 24 horas para o primeiro acesso. Confirme o destinatário por outro canal.</p><Action className={primary} run={async () => { const result = await api.post<{ invite_link: string }>(`/engagement/cases/${caseId}/portal-invites`, { access_days: Number(accessDays) }); setLink(result.invite_link); invites.reload(); }}>Criar link seguro</Action></div></div>
        {link && <div className="space-y-2 rounded-lg border border-blue-800 bg-blue-950/20 p-3"><Field label="Link pronto. Nenhum envio foi feito automaticamente."><input className={control} readOnly value={link} onFocus={event => event.target.select()} /></Field><button type="button" className={primary} onClick={async () => { await navigator.clipboard.writeText(link); setMessage("Link do portal copiado."); }}>Copiar link</button></div>}
        {invites.data?.items.map(row => <div key={row.id} className="flex flex-wrap items-center gap-2 text-xs text-zinc-400"><span>{row.revoked_at ? "Revogado" : row.redeemed_at ? "Utilizado" : "Aguardando uso"} · limite do acesso {dateText(row.expires_at)}</span>{!row.revoked_at && <Action run={() => api.delete(`/engagement/portal-invites/${row.id}`)} onDone={invites.reload}>Revogar acesso</Action>}</div>)}
        <div className="border-t border-zinc-800 pt-3"><p className="text-xs text-zinc-500">3. Escolher o que o cliente pode ver</p><Link className={primary} href={`/dashboard/cases/${caseId}`}>Abrir arquivos do processo</Link></div>
      </Panel>
      <Panel title="Histórico do caso"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-zinc-400">Mensagens do portal mostram quando o cliente abriu a conversa; e-mail e WhatsApp dependem do recibo do provedor.</p><Action run={async () => messages.reload()}>Atualizar recibos</Action></div><State loading={messages.loading} error={messages.error} empty={!messages.data?.items.length} />{messages.data?.items.map(row => <article key={row.id} className="border-b border-zinc-800 pb-3"><p className="text-xs text-zinc-400">{row.direction === "inbound" ? "Cliente" : "Escritório"} · {display(row.channel)} · {dateText(row.created_at)} · {row.channel === "portal" && row.direction === "outbound" ? row.read_at ? `Lida em ${dateText(row.read_at)}` : "Ainda não lida" : display(row.status)}</p><p className="mt-1 break-words whitespace-pre-wrap text-sm">{row.body}</p>{row.error_code && <p className="text-xs text-amber-300">{row.error_code}</p>}</article>)}</Panel>
      <Panel title="Checklist e documentos compartilhados"><p className="text-xs text-zinc-400">O cliente só pode baixar documentos explicitamente compartilhados. Anotações internas continuam privadas.</p>
        <form className="space-y-3" onSubmit={async event => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); try { await api.post(`/engagement/cases/${caseId}/checklist`, { title: data.get("title"), document_id: data.get("document") || null }); form.reset(); checklist.reload(); } catch (err) { setError(errorText(err)); } }}><Field label="Descrição do item"><input className={control} name="title" required minLength={2} maxLength={200} /></Field><Field label="Documento compartilhado (opcional)"><select className={control} name="document"><option value="">Solicitação sem arquivo</option>{documents.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><button className={primary}>Adicionar ao portal</button></form>
        <State error={checklist.error || documents.error} />{checklist.data?.items.map(row => <p key={row.id} className="text-xs">{row.title} · {row.document_id ? "Documento compartilhado" : "Aguardando documento"}</p>)}
      </Panel>
    </>}
  </Page>;
}
