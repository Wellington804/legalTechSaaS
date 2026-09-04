"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { Action, Field, Page, Panel, State, button, control, dateText, errorText, primary, useResource } from "./shared";
import { display, type List, type Row } from "./records";
import { formatBrazilianPhone } from "@/lib/phone";

type WhatsAppStatus = { status: string; connected: boolean; number?: string; last_checked_at?: string; verification_unavailable?: boolean };
type InboundAddress = { configured: boolean; address?: string; provider_ready: boolean };
type InboxItem = Row & { channel: "email" | "whatsapp"; sender: string; subject?: string; body: string; body_truncated: boolean; has_attachments: boolean; status: string; received_at: string; revision: number };

function verificationText(value?: string) {
  if (!value) return "Ainda não verificado";
  const date = new Date(value); if (Number.isNaN(date.valueOf())) return "Ainda não verificado";
  const today = new Date(); const sameDay = date.toDateString() === today.toDateString();
  return `${sameDay ? "hoje" : date.toLocaleDateString("pt-BR")}, ${date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

function InboxCard({ item, cases, onDone }: { item: InboxItem; cases: Row[]; onDone: (notice: string) => void }) {
  const [caseId, setCaseId] = useState(""); const [reason, setReason] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function link(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try { await api.post(`/engagement/inbox/${item.id}/link`, { case_id: caseId, expected_revision: item.revision, reason }); onDone("Mensagem vinculada ao processo após revisão."); }
    catch (cause) { setError(errorText(cause)); } finally { setBusy(false); }
  }
  async function dismiss() {
    if (reason.trim().length < 3) { setError("Informe o motivo da revisão antes de descartar."); return; }
    setBusy(true); setError("");
    try { await api.post(`/engagement/inbox/${item.id}/dismiss`, { expected_revision: item.revision, reason }); onDone("Mensagem descartada com motivo registrado."); }
    catch (cause) { setError(errorText(cause)); } finally { setBusy(false); }
  }
  const headingId = `inbox-${item.id}`;
  return <article aria-labelledby={headingId} className="space-y-3 py-5 first:pt-1">
    <div><h3 id={headingId} className="text-sm font-semibold text-zinc-100">{item.sender}</h3><p className="mt-1 text-xs text-zinc-400">{display(item.channel)} · {dateText(item.received_at)}</p>{item.subject && <p className="mt-2 text-sm font-medium">{item.subject}</p>}<p className="mt-2 max-w-[72ch] whitespace-pre-wrap break-words text-sm leading-relaxed">{item.body}</p>{item.body_truncated && <p className="mt-2 text-xs text-amber-300">A mensagem foi resumida para exibição. Confira o conteúdo original antes de vinculá-la.</p>}{item.has_attachments && <p className="mt-1 text-xs text-amber-300">Esta mensagem possui anexo. Confira-o antes de vincular ao processo.</p>}</div>
    <form onSubmit={link} className="grid gap-3 md:grid-cols-2"><Field label="Vincular ao processo"><select className={control} value={caseId} onChange={event => setCaseId(event.target.value)} required><option value="">Selecione após conferir…</option>{cases.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><Field label="Nota da revisão"><input className={control} value={reason} onChange={event => setReason(event.target.value)} required minLength={3} maxLength={500} placeholder="Por que esta mensagem pertence a este processo?" /></Field><div className="flex flex-wrap gap-2 md:col-span-2"><button className={primary} disabled={busy}>{busy ? "Revisando…" : "Vincular ao processo"}</button><button type="button" className={button} disabled={busy} onClick={() => void dismiss()}>Descartar</button></div></form>
    {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
  </article>;
}

function OmnichannelInbox({ cases, onNotice }: { cases: Row[]; onNotice: (value: string) => void }) {
  const inbox = useResource<{ items: InboxItem[] }>("/engagement/inbox?status_filter=open");
  const address = useResource<InboundAddress>("/engagement/inbox/email-address");
  async function configure(rotate = false) {
    if (rotate && !window.confirm("Trocar o endereço de entrada? O endereço anterior deixará de receber mensagens.")) return;
    await api.post("/engagement/inbox/email-address", { rotate }); address.reload(); onNotice(rotate ? "Endereço de entrada trocado." : "Caixa de e-mail ativada.");
  }
  return <Panel title="Caixa de entrada" description="Revise as mensagens que o sistema não conseguiu associar com segurança a um único processo.">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-zinc-400">{inbox.data?.items.length || 0} mensagem{inbox.data?.items.length === 1 ? "" : "s"} aguardando revisão</p><details><summary className={button}>Receber por e-mail</summary><div className="mt-3 max-w-xl space-y-3"><State loading={address.loading} error={address.error ? "Não foi possível consultar o recebimento de e-mail agora." : ""} />{address.data?.address && <Field label="Endereço do escritório"><input className={control} readOnly value={address.data.address} onFocus={event => event.currentTarget.select()} /></Field>}<div className="flex flex-wrap gap-2">{address.data?.configured ? <><Action run={async () => { await navigator.clipboard.writeText(address.data?.address || ""); onNotice("Endereço de entrada copiado."); }}>Copiar endereço</Action>{address.data.provider_ready && <Action run={() => configure(true)}>Trocar endereço</Action>}<Action run={async () => { if (!window.confirm("Desativar o recebimento de e-mail deste escritório?")) return; await api.delete("/engagement/inbox/email-address"); address.reload(); onNotice("Recebimento de e-mail desativado."); }}>Desativar</Action></> : address.data?.provider_ready ? <Action className={primary} run={() => configure(false)}>Ativar recebimento</Action> : null}</div>{address.data && !address.data.provider_ready && <p className="text-sm text-amber-300">O recebimento por e-mail está temporariamente indisponível. As mensagens já registradas continuam acessíveis.</p>}</div></details></div>
    <State loading={inbox.loading} error={inbox.error ? "Não foi possível carregar a caixa de entrada agora." : ""} empty={inbox.data?.items.length === 0} emptyText="Nenhuma mensagem precisa de revisão." />
    <div className="divide-y divide-zinc-800">{inbox.data?.items.map(item => <InboxCard key={item.id} item={item} cases={cases} onDone={notice => { inbox.reload(); onNotice(notice); }} />)}</div>
  </Panel>;
}

export function Communications() {
  const { user } = useUser(); const cases = useResource<List>("/workspace/cases"); const [caseId, setCaseId] = useState("");
  const messages = useResource<List>(caseId ? `/engagement/cases/${caseId}/messages` : null);
  const documents = useResource<List>(caseId ? `/workspace/documents?case_id=${caseId}` : null);
  const checklist = useResource<List>(caseId ? `/engagement/cases/${caseId}/checklist` : null);
  const invites = useResource<List>(caseId ? `/engagement/cases/${caseId}/portal-invites` : null);
  const admin = isOfficeAdminRole(user.role);
  const channels = useResource<{ whatsapp: WhatsAppStatus }>("/engagement/channels");
  const [whatsapp, setWhatsapp] = useState<WhatsAppStatus | null>(null);
  const [connectionUnavailable, setConnectionUnavailable] = useState(false);
  const [connectionBusy, setConnectionBusy] = useState(false);
  const [connectionError, setConnectionError] = useState("");
  const [error, setError] = useState(""); const [portalError, setPortalError] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false); const [link, setLink] = useState("");
  const [accessDays, setAccessDays] = useState("7");
  const [qrCode, setQrCode] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());

  useEffect(() => {
    if (channels.data?.whatsapp) {
      setWhatsapp(channels.data.whatsapp);
      setConnectionUnavailable(Boolean(channels.data.whatsapp.verification_unavailable));
    } else if (!channels.loading && channels.error) setConnectionUnavailable(true);
  }, [channels.data, channels.error, channels.loading]);

  useEffect(() => {
    if (whatsapp?.connected) { setQrCode(""); return; }
    if (whatsapp?.status !== "pending") return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const latest = (await api.get<{ whatsapp: WhatsAppStatus }>("/engagement/channels")).whatsapp;
        if (cancelled) return;
        setWhatsapp(current => current?.status === latest.status && current.connected === latest.connected && current.number === latest.number && current.last_checked_at === latest.last_checked_at && current.verification_unavailable === latest.verification_unavailable ? current : latest);
        setConnectionUnavailable(Boolean(latest.verification_unavailable));
        if (latest.connected) { setQrCode(""); return; }
        if (latest.status === "pending" && admin) {
          try {
            const result = await api.get<{ qr_code?: string }>("/engagement/whatsapp/qr");
            if (!cancelled && result.qr_code) setQrCode(current => current === result.qr_code ? current : result.qr_code || "");
          } catch { if (!cancelled && !qrCode) setConnectionUnavailable(true); }
        }
      } catch { if (!cancelled) setConnectionUnavailable(true); }
    };
    void refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [admin, qrCode, whatsapp?.connected, whatsapp?.status]);

  const connectionStage = whatsapp?.connected ? "connected" : qrCode ? "qr_ready" : connectionUnavailable ? "unavailable" : whatsapp?.status === "pending" ? "generating" : "disconnected";
  const statusText = channels.loading && !whatsapp ? "Verificando conexão" : connectionStage === "connected" ? "Conectado" : connectionStage === "qr_ready" ? "QR Code pronto" : connectionStage === "generating" ? "Gerando QR Code" : connectionStage === "unavailable" ? "Temporariamente indisponível" : "Desconectado";

  async function connect(kind: "connect" | "reconnect" | "refresh") {
    setConnectionBusy(true); setConnectionError(""); setConnectionUnavailable(false);
    try {
      const result = kind === "refresh"
        ? await api.get<{ qr_code?: string }>("/engagement/whatsapp/qr")
        : await api.post<{ whatsapp?: WhatsAppStatus; qr_code?: string }>(`/engagement/whatsapp/${kind}`, {});
      if (kind !== "refresh") {
        const started = result as { whatsapp?: WhatsAppStatus; qr_code?: string };
        setWhatsapp(started.whatsapp || { status: "pending", connected: false });
      }
      if (result.qr_code) setQrCode(result.qr_code);
      setMessage(result.qr_code ? "QR Code pronto para leitura." : "Conexão iniciada. O QR Code aparecerá aqui.");
    } catch {
      setConnectionUnavailable(true);
      setConnectionError(kind === "refresh" ? "Não foi possível atualizar o QR Code. Tente novamente." : "Não foi possível iniciar a conexão. Tente novamente em instantes.");
    } finally { setConnectionBusy(false); }
  }

  async function disconnect() {
    if (!window.confirm("Desconectar o WhatsApp deste escritório? Será necessário ler um novo QR Code para conectar novamente.")) return;
    setConnectionBusy(true); setConnectionError("");
    try { await api.delete("/engagement/whatsapp/connection"); setWhatsapp({ status: "disconnected", connected: false }); setQrCode(""); setConnectionUnavailable(false); setMessage("WhatsApp desconectado."); }
    catch { setConnectionError("Não foi possível desconectar o WhatsApp agora."); }
    finally { setConnectionBusy(false); }
  }

  return <Page title="Comunicações" subtitle="Centralize conversas, mensagens recebidas e acesso do cliente em cada processo.">
    {message && <p role="status" className="rounded-lg bg-emerald-950/40 px-4 py-3 text-sm text-emerald-300">{message}</p>}
    <Panel title="WhatsApp do escritório" description="Uma conexão por escritório, preservada enquanto você navega pelo sistema.">
      <div className="grid items-start gap-5 md:grid-cols-[minmax(0,1fr)_auto]">
        <div><div className="flex flex-wrap items-center gap-2"><p className="font-semibold text-zinc-100">{statusText}</p><span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${connectionStage === "connected" ? "bg-emerald-400" : connectionStage === "qr_ready" || connectionStage === "generating" ? "bg-blue-400" : connectionStage === "unavailable" ? "bg-amber-400" : "bg-zinc-500"}`} /></div>
          {whatsapp?.connected ? <dl className="mt-2 grid gap-1 text-sm text-zinc-400"><div className="flex flex-wrap gap-x-2"><dt>Número:</dt><dd className="text-zinc-200">{formatBrazilianPhone(whatsapp.number || "") || "Número conectado"}</dd></div><div className="flex flex-wrap gap-x-2"><dt>Conferido:</dt><dd className="text-zinc-200">{verificationText(whatsapp.last_checked_at)}</dd></div></dl>
            : <p className="mt-2 max-w-xl text-sm text-zinc-400">{connectionStage === "qr_ready" ? "Abra o WhatsApp no celular e leia o código para concluir." : connectionStage === "generating" ? "Aguarde enquanto preparamos o código de conexão." : connectionStage === "unavailable" ? "A última informação confirmada foi mantida. Tente novamente em instantes." : "Conecte o número usado pelo escritório para enviar e receber mensagens."}</p>}
          {(whatsapp?.verification_unavailable || connectionError) && <p role="status" className="mt-2 text-sm text-amber-300">{connectionError || "Não foi possível atualizar o estado agora. A última informação confirmada foi mantida."}</p>}
        </div>
        {admin && connectionStage !== "connected" && <button type="button" className={primary} disabled={connectionBusy || channels.loading} onClick={() => void connect(connectionStage === "qr_ready" || connectionStage === "generating" ? "refresh" : "connect")}>{connectionBusy ? "Aguarde…" : connectionStage === "qr_ready" || connectionStage === "generating" ? "Atualizar QR Code" : connectionStage === "unavailable" ? "Tentar novamente" : "Conectar WhatsApp"}</button>}
      </div>
      {qrCode && !whatsapp?.connected && <div className="max-w-sm border-t border-zinc-800 pt-5"><p className="mb-3 text-sm font-medium">Leia com o WhatsApp do escritório</p><Image src={qrCode} width={256} height={256} unoptimized alt="QR Code para conectar o WhatsApp do escritório" className="rounded-lg bg-white p-2" /></div>}
      {admin && whatsapp?.connected && <details><summary className="min-h-11 cursor-pointer content-center text-sm text-zinc-400">Gerenciar conexão</summary><div className="mt-2 flex flex-wrap gap-2"><button type="button" className={button} disabled={connectionBusy} onClick={() => void connect("reconnect")}>Reconectar</button><button type="button" className={button} disabled={connectionBusy} onClick={() => void disconnect()}>Desconectar</button></div></details>}
      {!whatsapp && !channels.loading && channels.error && <p role="alert" className="text-sm text-amber-300">Não foi possível verificar o WhatsApp agora.</p>}
    </Panel>
    {admin && <OmnichannelInbox cases={cases.data?.items || []} onNotice={setMessage} />}
    <Panel title="Conversas por processo" description="Escolha um processo para conversar com o cliente e consultar o histórico.">
      <Field label="Processo"><select className={control} value={caseId} onChange={event => { setCaseId(event.target.value); setLink(""); setError(""); setPortalError(""); setRequestId(crypto.randomUUID()); }}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><State loading={cases.loading} error={cases.error ? "Não foi possível carregar os processos agora." : ""} />
      {caseId && <><div aria-label="Histórico da conversa" className="max-h-[28rem] space-y-4 overflow-y-auto border-y border-zinc-800 py-4"><State loading={messages.loading} error={messages.error ? "Não foi possível carregar a conversa." : ""} empty={messages.data?.items.length === 0} emptyText="Nenhuma mensagem neste processo." />{messages.data?.items.map(row => <article key={row.id} className={`max-w-[85%] rounded-xl px-4 py-3 ${row.direction === "outbound" ? "ml-auto bg-blue-950/40" : "bg-zinc-900"}`}><p className={`text-xs ${row.direction === "outbound" ? "text-blue-200" : "text-zinc-400"}`}>{row.direction === "inbound" ? "Cliente" : "Escritório"} · {display(row.channel)} · {dateText(row.created_at)}</p><p className="mt-1 whitespace-pre-wrap break-words text-sm">{row.body}</p>{row.error_code && <p className="mt-1 text-xs text-amber-300">Não foi possível enviar por este canal. Tente novamente ou escolha outro canal.</p>}</article>)}</div>
        <form className="grid gap-3 sm:grid-cols-[10rem_minmax(0,1fr)]" onSubmit={async event => {
          event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setError(""); setBusy(true);
          try { const result = await api.post<Row>(`/engagement/cases/${caseId}/messages`, { body: data.get("body"), channel: data.get("channel"), request_id: requestId }); form.reset(); setRequestId(crypto.randomUUID()); setMessage(`Mensagem registrada. Situação: ${display(result.status)}.`); messages.reload(); } catch { setError("Não foi possível enviar a mensagem. Tente novamente ou escolha outro canal."); } finally { setBusy(false); }
        }}><Field label="Enviar por"><select className={control} name="channel"><option value="portal">Portal</option><option value="email">E-mail</option><option value="whatsapp">WhatsApp</option></select></Field><Field label="Mensagem"><textarea className={control} rows={3} name="body" required maxLength={8000} onChange={() => { if (error) { setRequestId(crypto.randomUUID()); setError(""); } }} /></Field><div className="sm:col-start-2"><button className={primary} disabled={busy}>{busy ? "Enviando…" : "Enviar mensagem"}</button></div></form><State error={error} />
        <div className="flex justify-end"><Action run={async () => messages.reload()}>Atualizar conversa</Action></div></>}
    </Panel>
    {caseId && <>
      <Panel title="Acesso do cliente" description="Crie um acesso temporário ao portal deste processo." collapsibleOnMobile><div className="grid gap-4 md:grid-cols-[12rem_minmax(0,1fr)]"><Field label="Tempo de acesso"><select className={control} value={accessDays} onChange={event => setAccessDays(event.target.value)}><option value="7">7 dias</option><option value="14">14 dias</option><option value="30">30 dias</option></select></Field><div><p className="mb-3 text-sm text-zinc-400">O link é pessoal e de uso único. Confirme o destinatário por outro canal.</p><Action className={primary} run={async () => { const result = await api.post<{ invite_link: string }>(`/engagement/cases/${caseId}/portal-invites`, { access_days: Number(accessDays) }); setLink(result.invite_link); invites.reload(); }}>Criar link seguro</Action></div></div>
        {link && <div className="space-y-2 rounded-lg bg-blue-950/20 p-3"><Field label="Link pronto. Nenhum envio foi feito automaticamente."><input className={control} readOnly value={link} onFocus={event => event.target.select()} /></Field><button type="button" className={primary} onClick={async () => { await navigator.clipboard.writeText(link); setMessage("Link do portal copiado."); }}>Copiar link</button></div>}
        {invites.data?.items.map(row => <div key={row.id} className="flex flex-wrap items-center gap-2 text-xs text-zinc-400"><span>{row.revoked_at ? "Revogado" : row.redeemed_at ? "Utilizado" : "Aguardando uso"} · limite do acesso {dateText(row.expires_at)}</span>{!row.revoked_at && <Action run={() => api.delete(`/engagement/portal-invites/${row.id}`)} onDone={invites.reload}>Revogar acesso</Action>}</div>)}
        <Link className={button} href={`/dashboard/cases/${caseId}`}>Escolher arquivos visíveis no portal</Link>
      </Panel>
      <Panel title="Pedidos e arquivos do cliente" description="Organize o que o cliente precisa enviar ou consultar." collapsibleOnMobile><p className="text-sm text-zinc-400">Somente arquivos compartilhados ficam visíveis. Anotações internas continuam privadas.</p>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={async event => { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setPortalError(""); try { await api.post(`/engagement/cases/${caseId}/checklist`, { title: data.get("title"), document_id: data.get("document") || null }); form.reset(); checklist.reload(); } catch { setPortalError("Não foi possível adicionar este item ao portal."); } }}><Field label="O que o cliente precisa fazer"><input className={control} name="title" required minLength={2} maxLength={200} /></Field><Field label="Arquivo compartilhado (opcional)"><select className={control} name="document"><option value="">Pedido sem arquivo</option>{documents.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field><div><button className={primary}>Adicionar ao portal</button></div></form>
        <State error={portalError || (checklist.error || documents.error ? "Não foi possível carregar os pedidos e arquivos do cliente." : "")} />{checklist.data?.items.map(row => <p key={row.id} className="text-sm">{row.title} · {row.document_id ? "Arquivo compartilhado" : "Aguardando envio"}</p>)}
      </Panel>
    </>}
  </Page>;
}
