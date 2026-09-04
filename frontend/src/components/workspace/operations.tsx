"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api-client";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import type { List, Row } from "./records";
import { Action, Field, Page, Panel, State, button, control, dateText, download, errorText, money, primary, useResource } from "./shared";
import { ProviderCosts } from "./provider-costs";

type Intake = Row & {
  name: string;
  email: string | null;
  phone: string | null;
  subject: string | null;
  message: string | null;
  status: "new" | "converted" | "archived";
  revision: number;
  created_at: string;
};
type FeeContract = {
  id: string;
  client_id: string;
  case_id: string | null;
  title: string;
  status: "draft" | "active" | "closed" | "void";
  revision: number;
};
type Invoice = {
  id: string;
  description: string;
  total_amount: string;
  status: "draft" | "issued" | "partially_paid" | "paid" | "void" | "overdue";
  revision: number;
  created_at?: string;
};
type TimeEntry = { id: string; description: string; duration_minutes: number; amount: string; status: "draft" | "approved" | "invoiced" | "void"; occurred_at: string };
type Provider = { id: string; purpose: "signature" | "payment"; provider: string; account_reference: string; enabled: boolean; api_token_configured: boolean; revision: number };
type IntakeConfig = { id: string; enabled: boolean; form_title: string; notice_version: string; consent_version: string; notice_url: string | null; allowed_origin: string | null; revision: number };
type JudicialSource = { source_kind: string; label: string; configured: boolean; homologation_required: boolean; detail: string };
type Envelope = {
  id: string;
  document_id: string;
  provider: string;
  status: "pending" | "signed" | "declined" | "expired";
  dispatch_status: "not_dispatched" | "submitted" | "unknown" | "failed";
  signed_file_available: boolean;
  signed_filename: string | null;
  signed_file_hash: string | null;
  signature_authentication: "email" | "icp_brasil" | null;
  signed_validation_status: "valid_integrity" | "invalid" | "unavailable" | null;
  signed_certificate_trust: "trusted" | "unverified" | "invalid" | "unavailable" | null;
  signed_signature_count: number | null;
  created_at: string;
};
type Installment = { due_on: string; amount: string };

const today = () => new Date().toLocaleDateString("en-CA");
const sum = (items: Installment[]) => items.reduce((total, item) => total + (Number(item.amount) || 0), 0).toFixed(2);
const signatureProviderName = (provider: string) => provider === "clicksign-sandbox" ? "Clicksign · testes" : provider === "clicksign" ? "Clicksign" : provider === "autentique" ? "Autentique" : "Serviço de assinatura";

function IntakeConversion({ intake, clients, members, onDone, onCancel }: {
  intake: Intake;
  clients: Row[];
  members: Row[];
  onDone: () => void;
  onCancel: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await api.post(`/operations/intakes/${intake.id}/convert`, {
        expected_revision: intake.revision,
        existing_client_id: data.get("client_id") || null,
        case_title: data.get("case_title"),
        responsible_user_id: data.get("responsible_user_id"),
        restricted: data.get("restricted") === "on",
      });
      onDone();
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="mt-4 space-y-3 rounded-lg border border-zinc-800 p-3">
    <p className="text-sm text-zinc-300">Confirme quem atenderá e como o caso aparecerá no escritório.</p>
    <fieldset disabled={busy} className="grid min-w-0 gap-3 sm:grid-cols-2">
      <Field label="Cliente existente (opcional)"><select className={control} name="client_id" defaultValue=""><option value="">Criar cliente com estes dados</option>{clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}</select></Field>
      <Field label="Advogado responsável"><select className={control} name="responsible_user_id" required defaultValue=""><option value="">Selecione…</option>{members.filter(member => ["admin", "partner", "lawyer"].includes(member.role)).map(member => <option key={member.id} value={member.id}>{member.full_name}</option>)}</select></Field>
      <Field label="Nome do novo caso"><input className={control} name="case_title" required minLength={2} maxLength={300} defaultValue={intake.subject || `Atendimento de ${intake.name}`} /></Field>
      <Field label="Acesso ao caso"><span className="flex min-h-11 items-center gap-2 rounded-lg border border-zinc-700 px-3"><input type="checkbox" name="restricted" className="h-4 w-4" /> Somente responsável e equipe autorizada</span></Field>
    </fieldset>
    <State error={error} />
    <div className="flex flex-wrap gap-2"><button className={primary} disabled={busy}>{busy ? "Convertendo…" : "Criar cliente e caso"}</button><button type="button" className={button} onClick={onCancel}>Cancelar</button></div>
  </form>;
}

function Intakes() {
  const intakes = useResource<{ items: Intake[]; limit: number }>("/operations/intakes");
  const clients = useResource<List>("/workspace/clients?limit=200");
  const members = useResource<List>("/workspace/members?limit=200");
  const [selected, setSelected] = useState<string | null>(null);
  return <Panel title="Novos atendimentos">
    <p className="text-sm text-zinc-400">Transforme uma solicitação recebida em cliente e caso, sem redigitar os dados.</p>
    <State loading={intakes.loading || clients.loading || members.loading} error={intakes.error || clients.error || members.error} empty={Boolean(intakes.data) && !intakes.data?.items.length} emptyText="Nenhuma solicitação recebida." />
    <div className="divide-y divide-zinc-800">{intakes.data?.items.map(intake => <article key={intake.id} className="py-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row">
        <div className="min-w-0"><p className="font-medium text-zinc-100">{intake.name}</p><p className="mt-1 text-sm text-zinc-400">{[intake.email, intake.phone, intake.subject].filter(Boolean).join(" · ") || "Contato sem assunto informado"}</p><p className="mt-1 text-xs text-zinc-500">Recebido em {dateText(intake.created_at)}</p>{intake.message && <details className="mt-2"><summary className="min-h-11 cursor-pointer content-center text-sm text-blue-300">Ler mensagem</summary><p className="whitespace-pre-wrap text-sm text-zinc-300">{intake.message}</p></details>}</div>
        {intake.status === "new" ? <button type="button" className={primary} onClick={() => setSelected(intake.id)}>Iniciar atendimento</button> : <span className="self-start rounded-full bg-emerald-950 px-3 py-1 text-xs text-emerald-300">Cliente e caso criados</span>}
      </div>
      {selected === intake.id && <IntakeConversion intake={intake} clients={clients.data?.items || []} members={members.data?.items || []} onCancel={() => setSelected(null)} onDone={() => { setSelected(null); intakes.reload(); clients.reload(); }} />}
    </article>)}</div>
  </Panel>;
}

function publicToken() {
  return Array.from(crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, "0")).join("");
}

function IntakeConfiguration() {
  const [config, setConfig] = useState<IntakeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [link, setLink] = useState("");

  useEffect(() => {
    api.get<IntakeConfig>("/operations/intake-config").then(setConfig).catch(reason => {
      if (!(reason instanceof ApiError && reason.status === 404)) setError(errorText(reason));
    }).finally(() => setLoading(false));
  }, []);

  function payload(form?: HTMLFormElement, token?: string) {
    const values = form ? new FormData(form) : null;
    const origin = window.location.origin.startsWith("https://") ? window.location.origin : null;
    return {
      public_token: token || null,
      enabled: values ? values.get("enabled") === "on" : config?.enabled ?? true,
      form_title: String(values?.get("form_title") || config?.form_title || "Fale com o escritório"),
      notice_version: String(values?.get("notice_version") || config?.notice_version || ""),
      consent_version: String(values?.get("consent_version") || config?.consent_version || ""),
      notice_url: String(values?.get("notice_url") || config?.notice_url || "") || null,
      allowed_origin: config?.allowed_origin || origin,
      expected_revision: config?.revision || null,
    };
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const token = config ? undefined : publicToken();
    try {
      const result = await api.put<IntakeConfig>("/operations/intake-config", payload(event.currentTarget, token));
      setConfig(result);
      if (token) setLink(`${window.location.origin}/atendimento#token=${token}`);
      setNotice(token ? "Formulário criado. Copie o link agora; por segurança ele não será exibido novamente." : "Configuração salva.");
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }

  async function rotate() {
    if (!config || !window.confirm("Gerar um novo link? O link anterior deixará de funcionar imediatamente.")) return;
    const token = publicToken(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.put<IntakeConfig>("/operations/intake-config", payload(undefined, token));
      setConfig(result); setLink(`${window.location.origin}/atendimento#token=${token}`);
      setNotice("Novo link gerado. Copie-o agora e compartilhe apenas com quem deve iniciar um atendimento.");
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }

  async function copyLink() {
    try { await navigator.clipboard.writeText(link); setNotice("Link copiado."); }
    catch { setError("Não foi possível copiar automaticamente. Selecione o link e copie manualmente."); }
  }

  return <Panel title="Formulário público de atendimento" description="Defina como novos clientes podem iniciar um atendimento." collapsibleOnMobile>
    <p className="text-sm text-zinc-400">O link é privado e deve ser compartilhado apenas nos canais oficiais do escritório.</p>
    <State loading={loading} error={error} />
    {!loading && <form key={config?.revision || "new"} onSubmit={save} className="space-y-3"><fieldset disabled={busy} className="grid min-w-0 gap-3 sm:grid-cols-2">
      <Field label="Título do formulário"><input className={control} name="form_title" required minLength={2} maxLength={120} defaultValue={config?.form_title || "Fale com o escritório"} /></Field>
      <Field label="Página do aviso de privacidade"><input className={control} name="notice_url" type="url" inputMode="url" placeholder="https://seusite.com/privacidade" required defaultValue={config?.notice_url || ""} /></Field>
      <Field label="Identificação do aviso"><input className={control} name="notice_version" required maxLength={64} placeholder="Ex.: privacidade 2026" defaultValue={config?.notice_version || ""} /></Field>
      <Field label="Identificação do consentimento"><input className={control} name="consent_version" required maxLength={64} placeholder="Ex.: atendimento 2026" defaultValue={config?.consent_version || ""} /></Field>
      <label className="flex min-h-11 items-center gap-3 text-sm text-zinc-300"><input name="enabled" type="checkbox" className="h-4 w-4" defaultChecked={config?.enabled ?? true} /> Aceitar novos atendimentos por este link</label>
    </fieldset><p className="text-xs text-zinc-400">As identificações registram qual texto o cliente aceitou em cada atendimento.</p><button className={primary} disabled={busy}>{busy ? "Salvando…" : config ? "Salvar configuração" : "Criar formulário e link"}</button></form>}
    {config && <div className="flex flex-wrap items-center gap-3"><span className={`rounded-full px-3 py-1 text-xs ${config.enabled ? "bg-emerald-950 text-emerald-300" : "bg-zinc-800 text-zinc-300"}`}>{config.enabled ? "Recebimento ativo" : "Recebimento pausado"}</span><button type="button" className={button} disabled={busy} onClick={rotate}>Gerar novo link</button></div>}
    {link && <div className="space-y-2 rounded-lg border border-amber-800 bg-amber-950/10 p-3"><p className="text-sm text-amber-200">Este link dá acesso ao formulário. Não publique em locais indevidos.</p><input className={control} aria-label="Link público de atendimento" readOnly value={link} onFocus={event => event.currentTarget.select()} /><button type="button" className={button} onClick={copyLink}>Copiar link</button></div>}
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
  </Panel>;
}

function InvoiceFlow({ contract, onContractChange, onInvoiceChange }: { contract: FeeContract; onContractChange: (value: FeeContract) => void; onInvoiceChange: () => void }) {
  const [items, setItems] = useState<Installment[]>([{ due_on: today(), amount: "" }]);
  const [description, setDescription] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const total = sum(items);

  async function activate() {
    setBusy(true); setError("");
    try { onContractChange(await api.put<FeeContract>(`/operations/fee-contracts/${contract.id}`, { expected_revision: contract.revision, status: "active" })); }
    catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }
  async function createInvoice() {
    setBusy(true); setError("");
    try {
      setInvoice(await api.post<Invoice>("/operations/invoices", { fee_contract_id: contract.id, description, total_amount: total, installments: items }));
      onInvoiceChange();
      setReviewing(false);
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }
  async function issue() {
    if (!invoice) return;
    setBusy(true); setError("");
    try { setInvoice(await api.post<Invoice>(`/operations/invoices/${invoice.id}/issue`, { expected_revision: invoice.revision })); onInvoiceChange(); }
    catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }

  return <div className="space-y-4 rounded-lg border border-zinc-800 p-4">
    <div><p className="text-sm font-medium text-zinc-100">{contract.title}</p><p className="text-xs text-zinc-400">{contract.status === "draft" ? "Rascunho: revise antes de ativar." : "Contrato ativo e pronto para faturamento."}</p></div>
    {contract.status === "draft" && <button type="button" className={primary} disabled={busy} onClick={activate}>{busy ? "Ativando…" : "Revisei e quero ativar"}</button>}
    {contract.status === "active" && !invoice && <form className="space-y-3" onSubmit={event => { event.preventDefault(); setReviewing(true); }}>
      <Field label="Descrição da cobrança"><input className={control} value={description} onChange={event => setDescription(event.target.value)} required minLength={2} maxLength={500} /></Field>
      <div className="space-y-3"><p className="text-sm font-medium text-zinc-300">Parcelas</p>{items.map((item, index) => <div key={index} className="grid gap-2 rounded-lg border border-zinc-800 p-3 sm:grid-cols-[1fr_1fr_auto]">
        <Field label={`Vencimento da parcela ${index + 1}`}><input className={control} type="date" min="2000-01-01" max="2100-12-31" required value={item.due_on} onChange={event => setItems(current => current.map((row, itemIndex) => itemIndex === index ? { ...row, due_on: event.target.value } : row))} /></Field>
        <Field label={`Valor da parcela ${index + 1}`}><input className={control} type="number" min="0.01" max="999999999999.99" step="0.01" required value={item.amount} onChange={event => setItems(current => current.map((row, itemIndex) => itemIndex === index ? { ...row, amount: event.target.value } : row))} /></Field>
        {items.length > 1 && <button type="button" className={`${button} self-end`} onClick={() => setItems(current => current.filter((_, itemIndex) => itemIndex !== index))}>Remover</button>}
      </div>)}</div>
      <div className="flex flex-wrap items-center justify-between gap-3"><button type="button" className={button} onClick={() => setItems(current => [...current, { due_on: today(), amount: "" }])}>Adicionar parcela</button><p className="font-medium">Total: {money(total)}</p></div>
      <button className={primary}>Revisar fatura</button>
    </form>}
    {reviewing && !invoice && <section aria-label="Revisão da fatura" className="space-y-3 rounded-lg border border-amber-800 bg-amber-950/10 p-4"><h3 className="font-medium text-amber-200">Confira antes de criar</h3><p className="text-sm">{description} · {items.length} parcela{items.length === 1 ? "" : "s"} · {money(total)}</p><ul className="text-sm text-amber-100">{items.map((item, index) => <li key={index}>Parcela {index + 1}: {dateText(item.due_on)} · {money(item.amount)}</li>)}</ul><div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy || Number(total) <= 0} onClick={createInvoice}>{busy ? "Criando…" : "Confirmar criação"}</button><button type="button" className={button} onClick={() => setReviewing(false)}>Voltar e corrigir</button></div></section>}
    {invoice && <section aria-label="Fatura criada" className="space-y-3"><p className="text-sm font-medium text-emerald-300">Fatura criada: {money(invoice.total_amount)}</p><p className="text-xs text-zinc-400">{invoice.status === "draft" ? "Rascunho. A emissão só acontece após sua confirmação." : "Fatura emitida. O pagamento ainda depende do serviço escolhido ou da conferência financeira."}</p>{invoice.status === "draft" && <button type="button" className={primary} disabled={busy} onClick={issue}>{busy ? "Emitindo…" : "Emitir fatura revisada"}</button>}</section>}
    <State error={error} />
  </div>;
}

function Fees() {
  const clients = useResource<List>("/workspace/clients?limit=200");
  const cases = useResource<List>("/workspace/cases?limit=200");
  const contracts = useResource<{ items: FeeContract[]; limit: number }>("/operations/fee-contracts?limit=200");
  const invoices = useResource<{ items: Invoice[]; limit: number }>("/operations/invoices?limit=200");
  const entries = useResource<{ items: TimeEntry[]; limit: number }>("/operations/time-entries?limit=200");
  const [clientId, setClientId] = useState("");
  const [contract, setContract] = useState<FeeContract | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const clientCases = cases.data?.items.filter(item => item.client_id === clientId) || [];
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      setContract(await api.post<FeeContract>("/operations/fee-contracts", { client_id: data.get("client_id"), case_id: data.get("case_id") || null, document_id: null, title: data.get("title"), currency: "BRL", terms_version: "modelo-escritorio-1" }));
      contracts.reload();
    }
    catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }
  return <Panel title="Contrato de honorários e fatura" collapsibleOnMobile>
    <p className="text-sm text-zinc-400">Crie o contrato em rascunho, revise, ative e somente depois prepare as parcelas.</p>
    <State loading={clients.loading || cases.loading || contracts.loading || invoices.loading || entries.loading} error={clients.error || cases.error || contracts.error || invoices.error || entries.error || error} />
    {!contract && <form onSubmit={submit} className="space-y-3"><fieldset disabled={busy} className="grid min-w-0 gap-3 sm:grid-cols-2">
      <Field label="Cliente"><select name="client_id" className={control} required value={clientId} onChange={event => setClientId(event.target.value)}><option value="">Selecione…</option>{clients.data?.items.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}</select></Field>
      <Field label="Caso relacionado (opcional)"><select key={clientId} name="case_id" className={control} defaultValue=""><option value="">Sem caso específico</option>{clientCases.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></Field>
      <Field label="Nome do contrato"><input name="title" className={control} required minLength={2} maxLength={200} placeholder="Ex.: Honorários do caso trabalhista" /></Field>
    </fieldset><button className={primary} disabled={busy}>{busy ? "Criando rascunho…" : "Criar contrato para revisar"}</button></form>}
    {contract && <><InvoiceFlow contract={contract} onContractChange={value => { setContract(value); contracts.reload(); }} onInvoiceChange={invoices.reload} /><button type="button" className={button} onClick={() => setContract(null)}>Fechar fluxo</button></>}
    <details className="border-t border-zinc-800 pt-3" open><summary className="min-h-11 cursor-pointer content-center font-medium text-zinc-100">Contratos salvos ({contracts.data?.items.length || 0})</summary><div className="mt-2 divide-y divide-zinc-800">{contracts.data?.items.map(item => <article key={item.id} className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-center"><div><p className="text-sm font-medium">{item.title}</p><p className="text-xs text-zinc-400">{item.status === "draft" ? "Rascunho" : item.status === "active" ? "Ativo" : item.status === "closed" ? "Encerrado" : "Cancelado"}</p></div>{["draft", "active"].includes(item.status) && <button type="button" className={button} onClick={() => setContract(item)}>Retomar</button>}</article>)}</div>{contracts.data && !contracts.data.items.length && <p className="mt-2 text-sm text-zinc-400">Nenhum contrato cadastrado.</p>}</details>
    <details className="border-t border-zinc-800 pt-3"><summary className="min-h-11 cursor-pointer content-center font-medium text-zinc-100">Faturas salvas ({invoices.data?.items.length || 0})</summary><div className="mt-2 divide-y divide-zinc-800">{invoices.data?.items.map(item => <article key={item.id} className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-center"><div><p className="text-sm font-medium">{item.description}</p><p className="text-xs text-zinc-400">{money(item.total_amount)} · {item.status === "draft" ? "Rascunho" : item.status === "issued" ? "Emitida" : item.status === "partially_paid" ? "Parcialmente paga" : item.status === "paid" ? "Paga" : item.status === "overdue" ? "Vencida" : "Cancelada"}{item.created_at ? ` · ${dateText(item.created_at)}` : ""}</p></div>{item.status === "draft" && <Action run={() => api.post(`/operations/invoices/${item.id}/issue`, { expected_revision: item.revision })} onDone={invoices.reload}>Emitir fatura revisada</Action>}</article>)}</div>{invoices.data && !invoices.data.items.length && <p className="mt-2 text-sm text-zinc-400">Nenhuma fatura cadastrada.</p>}</details>
    <details className="border-t border-zinc-800 pt-3"><summary className="min-h-11 cursor-pointer content-center font-medium text-zinc-100">Horas registradas ({entries.data?.items.length || 0})</summary><div className="mt-2 divide-y divide-zinc-800">{entries.data?.items.map(item => <article key={item.id} className="py-3"><div className="flex flex-wrap justify-between gap-2"><p className="text-sm font-medium">{item.description}</p><p className="text-sm">{money(item.amount)}</p></div><p className="text-xs text-zinc-400">{item.duration_minutes} min · {item.status === "draft" ? "Rascunho" : item.status === "approved" ? "Aprovado" : item.status === "invoiced" ? "Faturado" : "Cancelado"} · {dateText(item.occurred_at)}</p></article>)}</div>{entries.data && !entries.data.items.length && <p className="mt-2 text-sm text-zinc-400">Nenhum apontamento de horas.</p>}</details>
  </Panel>;
}

function SignatureConfiguration() {
  const providers = useResource<{ items: Provider[] }>("/operations/provider-credentials");
  const [environment, setEnvironment] = useState<"clicksign-sandbox" | "clicksign" | "autentique">("clicksign-sandbox");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const configured = providers.data?.items.find(item => item.purpose === "signature" && item.provider === environment);
  useEffect(() => {
    setWebhookUrl(`${window.location.origin}/api/v1/operations/webhooks/signatures/${environment}`);
  }, [environment]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setError(""); setNotice("");
    try {
      await api.put(`/operations/provider-credentials/signature/${environment}`, {
        account_reference: data.get("account_reference"),
        api_token: data.get("api_token") || null,
        webhook_secret: data.get("webhook_secret"),
        enabled: data.get("enabled") === "on",
        expected_revision: configured?.account_reference === data.get("account_reference") ? configured.revision : null,
      });
      setNotice("Integração salva. Faça um envio de teste no ambiente selecionado.");
      providers.reload();
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }
  return <Panel title="Assinatura eletrônica" description="Conecte o serviço usado pelo escritório para enviar documentos." collapsibleOnMobile>
    <p className="text-sm text-zinc-400">Somente administradores podem alterar estes dados. As credenciais ficam protegidas por escritório.</p>
    <State loading={providers.loading} error={providers.error || error} />
    <form key={`${environment}:${configured?.revision || "new"}`} onSubmit={save} className="space-y-3">
      <fieldset disabled={busy} className="grid min-w-0 gap-3 sm:grid-cols-2">
        <Field label="Serviço e ambiente"><select className={control} value={environment} onChange={event => setEnvironment(event.target.value as typeof environment)}><option value="clicksign-sandbox">Clicksign · testes</option><option value="clicksign">Clicksign · produção</option><option value="autentique">Autentique</option></select></Field>
        <Field label={environment === "autentique" ? "Identificação da organização" : "Identificação da conta"}><input className={control} name="account_reference" required minLength={2} maxLength={128} defaultValue={configured?.account_reference || ""} autoComplete="off" /></Field>
        <Field label={configured?.api_token_configured ? "Token de acesso (vazio mantém o atual)" : "Token de acesso"}><input className={control} name="api_token" type="password" minLength={16} required={!configured?.api_token_configured} autoComplete="new-password" /></Field>
        <Field label="Segredo de confirmação"><input className={control} name="webhook_secret" type="password" minLength={16} required autoComplete="new-password" /></Field>
        <label className="flex min-h-11 items-center gap-3 text-sm text-zinc-300"><input name="enabled" type="checkbox" className="h-4 w-4" defaultChecked={configured?.enabled ?? true} /> Integração ativa</label>
      </fieldset>
      <button className={primary} disabled={busy}>{busy ? "Salvando…" : "Salvar integração"}</button>
    </form>
    <details className="border-t border-zinc-800 pt-3"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-zinc-300">Configuração avançada</summary><div className="mt-2 space-y-1.5"><p className="text-sm text-zinc-400">Cadastre este endereço no serviço de assinatura para receber as confirmações.</p><div className="flex min-w-0 flex-col gap-2 sm:flex-row"><input className={control} aria-label="Endereço de confirmação do serviço" readOnly value={webhookUrl} onFocus={event => event.target.select()} /><button className={button} type="button" onClick={() => navigator.clipboard.writeText(webhookUrl)} disabled={!webhookUrl}>Copiar endereço</button></div></div></details>
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
  </Panel>;
}

function Signatures() {
  const documents = useResource<List>("/workspace/documents?limit=200");
  const providers = useResource<{ items: { provider: string; account_reference: string }[] }>("/operations/signature-providers");
  const envelopes = useResource<{ items: Envelope[] }>("/operations/signature-envelopes?limit=50");
  const [envelope, setEnvelope] = useState<Envelope | null>(null);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); const document = documents.data?.items.find(item => item.id === data.get("document_id"));
    if (!document) return;
    const [provider, account_reference] = String(data.get("provider_account") || "").split("\u001f");
    if (!provider || !account_reference) return;
    setBusy(true); setError("");
    try {
      setEnvelope(await api.post<Envelope>("/operations/signature-envelopes", {
        request_key: requestKey,
        document_id: document.id,
        document_version: document.current_version,
        provider,
        account_reference,
        signer_name: data.get("signer_name"),
        signer_email: data.get("signer_email"),
        signer_cpf: data.get("signer_cpf"),
        authentication: data.get("authentication"),
        expires_at: null,
      }));
      envelopes.reload();
    }
    catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); envelopes.reload(); }
  }
  return <Panel title="Enviar para assinatura" description="Acompanhe a solicitação até o documento assinado ficar disponível." collapsibleOnMobile>
    <p className="text-sm text-zinc-400">O arquivo original é preservado. Na opção ICP-Brasil, certificado A1/A3 e PIN são usados somente no ambiente seguro do serviço de assinatura e nunca passam pelo LexFlow.</p>
    <State loading={documents.loading || providers.loading || envelopes.loading} error={documents.error || providers.error || envelopes.error || error} empty={Boolean(documents.data) && !documents.data?.items.length} emptyText="Crie ou envie um documento antes de solicitar assinatura." />
    {!providers.loading && providers.data && !providers.data.items.length && <p className="rounded-lg bg-amber-950/25 p-3 text-sm text-amber-300">Nenhum serviço de assinatura está disponível. Peça a um administrador para ativá-lo em Configurações de serviços.</p>}
    {!envelope && Boolean(documents.data?.items.length) && Boolean(providers.data?.items.length) && <form onSubmit={submit} onChange={() => { if (error) { setRequestKey(crypto.randomUUID()); setError(""); } }} className="grid gap-3 sm:grid-cols-2">
      <Field label="Documento"><select className={control} name="document_id" required defaultValue=""><option value="">Selecione…</option>{documents.data?.items.map(item => <option key={item.id} value={item.id}>{item.title} · versão {item.current_version}</option>)}</select></Field>
      <Field label="Serviço de assinatura"><select className={control} name="provider_account" required defaultValue=""><option value="">Selecione…</option>{providers.data?.items.map(item => <option key={`${item.provider}:${item.account_reference}`} value={`${item.provider}\u001f${item.account_reference}`}>{signatureProviderName(item.provider)}</option>)}</select></Field>
      <Field label="Nome completo do signatário"><input className={control} name="signer_name" required minLength={3} maxLength={200} autoComplete="name" /></Field>
      <Field label="E-mail do signatário"><input className={control} name="signer_email" type="email" required maxLength={320} autoComplete="email" /></Field>
      <Field label="CPF do signatário"><input className={control} name="signer_cpf" inputMode="numeric" required minLength={11} maxLength={18} placeholder="000.000.000-00" autoComplete="off" /></Field>
      <Field label="Confirmação de identidade"><select className={control} name="authentication" defaultValue="icp_brasil"><option value="icp_brasil">Certificado ICP-Brasil A1/A3</option><option value="email">Confirmação por e-mail</option></select></Field>
      <div className="self-end sm:col-span-2"><button className={primary} disabled={busy}>{busy ? "Enviando ao serviço…" : "Enviar PDF para assinatura"}</button></div>
    </form>}
    {envelope && <div role="status" className="space-y-3 rounded-lg bg-amber-950/20 p-4"><div><p className="font-medium text-amber-200">Solicitação enviada a {signatureProviderName(envelope.provider)}</p><p className="mt-1 text-sm text-amber-100">O signatário receberá o link por e-mail. O documento original continuará preservado.</p><p className="mt-2 text-xs text-amber-200">Envio: {envelope.dispatch_status === "submitted" ? "encaminhado ao serviço" : envelope.dispatch_status === "failed" ? "falhou" : "aguardando confirmação"}</p></div><button type="button" className={button} onClick={() => { setEnvelope(null); setRequestKey(crypto.randomUUID()); }}>Nova solicitação</button></div>}
    <details className="border-t border-zinc-800 pt-3" open><summary className="min-h-11 cursor-pointer content-center font-medium text-zinc-100">Solicitações recentes ({envelopes.data?.items.length || 0})</summary><div className="mt-2 divide-y divide-zinc-800">{envelopes.data?.items.map(item => <article key={item.id} className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-center"><div><p className="text-sm font-medium">{documents.data?.items.find(document => document.id === item.document_id)?.title || "Documento"}</p><p className="text-xs text-zinc-400">{signatureProviderName(item.provider)} · {item.status === "signed" ? "Assinado" : item.status === "declined" ? "Recusado" : item.status === "expired" ? "Expirado" : item.dispatch_status === "submitted" ? "Aguardando assinatura" : item.dispatch_status === "failed" ? "Falha no envio" : "Aguardando confirmação do envio"} · {dateText(item.created_at)}</p>{item.signed_validation_status === "valid_integrity" && <p className="mt-1 text-xs text-emerald-300">Arquivo assinado conferido · {item.signed_signature_count || 0} assinatura{item.signed_signature_count === 1 ? "" : "s"}{item.signed_certificate_trust === "trusted" ? " · certificado reconhecido" : " · confirme a validade do certificado antes de usar"}</p>}{item.signed_validation_status === "invalid" && <p className="mt-1 text-xs text-red-300">O arquivo recebido não passou na conferência e não foi liberado como assinado.</p>}{item.signed_validation_status === "unavailable" && <p className="mt-1 text-xs text-amber-300">A conferência está temporariamente indisponível; o arquivo ainda não foi liberado.</p>}</div>{item.signed_file_available && <button type="button" className={button} onClick={() => download(`/operations/signature-envelopes/${item.id}/download`, item.signed_filename || `documento-assinado-${item.provider}.pdf`)}>Baixar PDF assinado</button>}</article>)}</div>{envelopes.data && !envelopes.data.items.length && <p className="mt-2 text-sm text-zinc-400">Nenhuma assinatura solicitada.</p>}</details>
  </Panel>;
}

function JudicialSourcesConfiguration() {
  const sources = useResource<JudicialSource[]>("/controladoria/providers");
  return <Panel title="Consultas processuais" description="Veja quais fontes podem ser usadas pelo escritório." collapsibleOnMobile>
    <State loading={sources.loading} error={sources.error ? "Não foi possível consultar os serviços agora." : ""} />
    <div className="divide-y divide-zinc-800">{sources.data?.map(source => <article key={source.source_kind} className="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-start"><div><p className="text-sm font-medium text-zinc-100">{source.label}</p><p className="mt-1 max-w-[65ch] text-xs text-zinc-400">{source.detail}</p></div><span className={`self-start rounded-full px-2.5 py-1 text-xs font-medium ${source.configured ? "bg-emerald-950 text-emerald-300" : "bg-zinc-800 text-zinc-300"}`}>{source.configured ? "Disponível" : source.homologation_required ? "Aguardando liberação" : "Não configurada"}</span></article>)}</div>
    {sources.data && !sources.data.length && <p className="text-sm text-zinc-400">Nenhuma fonte de consulta cadastrada.</p>}
  </Panel>;
}

export function Operations() {
  const { user } = useUser();
  if (user.role !== "ASSOCIADO" && !isOfficeAdminRole(user.role)) return <Page title="Atendimento e cobranças" subtitle="Esta área é restrita a advogados e administradores do escritório."><State error="Seu perfil não possui acesso a esta área." /></Page>;
  return <Page title="Atendimento e honorários" subtitle="Acompanhe novos contatos, contratos, cobranças e assinaturas em um só fluxo.">
    <Intakes />
    {isOfficeAdminRole(user.role) && <Fees />}
    <Signatures />
  </Page>;
}

export function OperationsSettings() {
  const { user } = useUser();
  if (!isOfficeAdminRole(user.role)) return <Page title="Configurações de serviços" subtitle="Esta área é restrita aos administradores do escritório."><State error="Seu perfil não possui acesso a estas configurações." /></Page>;
  return <Page title="Configurações de serviços" subtitle="Gerencie formulário de atendimento, assinatura e consultas externas sem misturar configuração com o trabalho diário.">
    <JudicialSourcesConfiguration />
    <IntakeConfiguration />
    <SignatureConfiguration />
    <ProviderCosts />
  </Page>;
}
