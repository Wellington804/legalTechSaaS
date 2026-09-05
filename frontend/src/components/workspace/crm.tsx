"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { useUser } from "@/context/user-context";
import { Records, type List, type Row } from "./records";
import { Action, DraftNotice, Field, Page, Panel, State, button, control, dateText, errorText, money, primary, scrollWorkspaceToTop, useDraftGuard, useResource } from "./shared";

type Stage = "new" | "qualified" | "proposal" | "won" | "lost";
type Source = "manual" | "intake" | "referral" | "website" | "whatsapp" | "email" | "other";
type Opportunity = {
  id: string; title: string; stage: Stage; source: Source; estimated_value: string | number | null;
  next_action: string | null; next_action_at: string | null; notes: string | null; client_id: string | null;
  case_id: string | null; intake_id: string | null; owner_user_id: string | null; revision: number;
  archived_at: string | null; created_at: string; updated_at: string;
};
type OpportunityList = { items: Opportunity[]; limit: number };

const stages: { id: Stage; label: string }[] = [
  { id: "new", label: "Novo contato" }, { id: "qualified", label: "Qualificada" },
  { id: "proposal", label: "Proposta" }, { id: "won", label: "Ganha" }, { id: "lost", label: "Perdida" },
];
const sources: { id: Source; label: string }[] = [
  { id: "manual", label: "Cadastro manual" }, { id: "intake", label: "Atendimento recebido" },
  { id: "referral", label: "Indicação" }, { id: "website", label: "Site" },
  { id: "whatsapp", label: "WhatsApp" }, { id: "email", label: "E-mail" }, { id: "other", label: "Outro" },
];
const nextStage: Partial<Record<Stage, Stage>> = { new: "qualified", qualified: "proposal", proposal: "won" };

function localDateTime(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function value(data: FormData, key: string) {
  const result = String(data.get(key) || "").trim();
  return result || null;
}

function OpportunityForm({ opportunity, clients, cases, members, intakes, onDone, onCancel }: {
  opportunity?: Opportunity; clients: Row[]; cases: Row[]; members: Row[]; intakes: Row[];
  onDone: () => void; onCancel: () => void;
}) {
  const { user } = useUser();
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const requestId = useRef("");
  const draft = useDraftGuard(`crm:opportunity:${opportunity?.id || "new"}`);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget); const actionAt = value(data, "next_action_at");
    const payload = {
      title: value(data, "title"), stage: value(data, "stage"), source: value(data, "source"),
      estimated_value: value(data, "estimated_value"), next_action: value(data, "next_action"),
      next_action_at: actionAt ? new Date(actionAt).toISOString() : null, notes: value(data, "notes"),
      client_id: value(data, "client_id"), case_id: value(data, "case_id"), intake_id: value(data, "intake_id"),
      owner_user_id: value(data, "owner_user_id"),
    };
    try {
      if (opportunity) await api.put(`/crm/opportunities/${opportunity.id}`, { ...payload, expected_revision: opportunity.revision });
      else {
        requestId.current ||= crypto.randomUUID();
        await api.post("/crm/opportunities", { ...payload, request_id: requestId.current });
      }
      draft.setDirty(false); onDone();
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  return <form ref={draft.formRef} onSubmit={submit} onChange={() => draft.setDirty(true)} className="space-y-4">
    <fieldset disabled={busy} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Oportunidade"><input className={control} name="title" required minLength={2} maxLength={200} defaultValue={opportunity?.title || ""} autoFocus /></Field>
        <Field label="Responsável"><select className={control} name="owner_user_id" defaultValue={opportunity?.owner_user_id || user.id || ""}><option value="">Sem responsável</option>{members.filter(member => ["admin", "partner", "lawyer"].includes(member.role)).map(member => <option key={member.id} value={member.id}>{member.full_name || member.email}</option>)}</select></Field>
        <Field label="Etapa"><select className={control} name="stage" defaultValue={opportunity?.stage || "new"}>{stages.map(stage => <option key={stage.id} value={stage.id}>{stage.label}</option>)}</select></Field>
        <Field label="Origem"><select className={control} name="source" defaultValue={opportunity?.source || "manual"}>{sources.map(source => <option key={source.id} value={source.id}>{source.label}</option>)}</select></Field>
        <Field label="Valor estimado"><input className={control} name="estimated_value" type="number" inputMode="decimal" min="0" max="999999999999.99" step="0.01" defaultValue={opportunity?.estimated_value ?? ""} placeholder="0,00" /></Field>
        <Field label="Data da próxima ação"><input className={control} name="next_action_at" type="datetime-local" defaultValue={localDateTime(opportunity?.next_action_at || null)} /></Field>
        <Field label="Cliente"><select className={control} name="client_id" defaultValue={opportunity?.client_id || ""}><option value="">Sem cliente vinculado</option>{clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}</select></Field>
        <Field label="Processo"><select className={control} name="case_id" defaultValue={opportunity?.case_id || ""}><option value="">Sem processo vinculado</option>{cases.map(caseRecord => <option key={caseRecord.id} value={caseRecord.id}>{caseRecord.title}</option>)}</select></Field>
        <Field label="Atendimento de origem"><select className={control} name="intake_id" defaultValue={opportunity?.intake_id || ""}><option value="">Sem atendimento vinculado</option>{intakes.map(intake => <option key={intake.id} value={intake.id}>{intake.name}{intake.subject ? ` · ${intake.subject}` : ""}</option>)}</select></Field>
        <Field label="Próxima ação"><input className={control} name="next_action" maxLength={500} defaultValue={opportunity?.next_action || ""} placeholder="Ex.: enviar proposta de honorários" /></Field>
      </div>
      <Field label="Notas"><textarea className={`${control} min-h-24`} name="notes" maxLength={5000} defaultValue={opportunity?.notes || ""} /></Field>
      <p className="text-xs text-zinc-400">Ao escolher um processo, o cliente correspondente será vinculado automaticamente.</p>
      <DraftNotice dirty={draft.dirty} /><State error={error} />
      <div className="flex flex-wrap gap-2"><button className={primary}>{busy ? "Salvando…" : opportunity ? "Salvar oportunidade" : "Criar oportunidade"}</button><button type="button" className={button} onClick={() => { if (draft.discard()) onCancel(); }}>Cancelar</button></div>
    </fieldset>
  </form>;
}

function Pipeline() {
  const { user } = useUser();
  const canWrite = ["admin", "partner", "lawyer"].includes(user.permissionRole || "");
  // ponytail: bounded list matches the workspace contract; add cursor pagination when an office exceeds 200 active opportunities.
  const opportunities = useResource<OpportunityList>("/crm/opportunities?limit=200");
  const clients = useResource<List>("/workspace/clients?limit=200");
  const cases = useResource<List>("/workspace/cases?limit=200");
  const members = useResource<List>("/workspace/members?limit=200");
  const [editing, setEditing] = useState<Opportunity | null>(null); const [creating, setCreating] = useState(false); const [query, setQuery] = useState("");
  const intakes = useResource<List>(canWrite && (creating || Boolean(editing)) ? "/operations/intakes?limit=200" : null);
  const relationsLoading = clients.loading || cases.loading || members.loading || intakes.loading;
  const relationsError = clients.error || cases.error || members.error || intakes.error;
  const clientName = (id: string | null) => clients.data?.items.find(item => item.id === id)?.name;
  const caseTitle = (id: string | null) => cases.data?.items.find(item => item.id === id)?.title;
  const ownerName = (id: string | null) => members.data?.items.find(item => item.id === id)?.full_name;
  const visible = opportunities.data?.items.filter(item => [item.title, clientName(item.client_id), caseTitle(item.case_id), ownerName(item.owner_user_id), item.next_action].some(text => String(text || "").toLocaleLowerCase().includes(query.toLocaleLowerCase()))) || [];
  const closeForm = () => { setCreating(false); setEditing(null); };
  const reload = () => { closeForm(); opportunities.reload(); };
  return <div className="space-y-5">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div className="min-w-0 flex-1"><Field label="Filtrar oportunidades"><input className={control} type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Assunto, cliente, processo ou responsável" /></Field></div>{canWrite ? <button className={primary} onClick={() => { setEditing(null); setCreating(true); scrollWorkspaceToTop(); }}>Nova oportunidade</button> : <p className="text-sm text-zinc-400">Visualização sem permissão de edição.</p>}</div>
    {(creating || editing) && <Panel title={editing ? "Editar oportunidade" : "Nova oportunidade"} description="Registre somente informações confirmadas no atendimento.">
      <State loading={relationsLoading} error={relationsError} />
      {!relationsLoading && !relationsError && <OpportunityForm key={editing?.id || "new"} opportunity={editing || undefined} clients={clients.data?.items || []} cases={cases.data?.items || []} members={members.data?.items || []} intakes={intakes.data?.items || []} onDone={reload} onCancel={closeForm} />}
    </Panel>}
    <State loading={opportunities.loading} error={opportunities.error} empty={Boolean(opportunities.data) && !opportunities.data?.items.length} emptyText="Nenhuma oportunidade ativa. Crie a primeira quando houver um atendimento comercial real." />
    {opportunities.error && <button type="button" className={button} onClick={opportunities.reload}>Tentar carregar as oportunidades novamente</button>}
    {!opportunities.loading && !opportunities.error && opportunities.data?.items.length ? <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-5" aria-label="Funil de oportunidades">
      {stages.map(stage => { const items = visible.filter(item => item.stage === stage.id); return <section key={stage.id} className="min-w-0 rounded-xl border border-zinc-800 bg-zinc-900/25 p-3" aria-labelledby={`crm-stage-${stage.id}`}>
        <div className="mb-3 flex items-center justify-between gap-2"><h2 id={`crm-stage-${stage.id}`} className="text-sm font-semibold text-zinc-100">{stage.label}</h2><span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-300">{items.length}</span></div>
        <div className="space-y-3">{items.map(item => <article key={item.id} className="min-w-0 rounded-lg border border-zinc-800 bg-zinc-950 p-3 shadow-sm">
          <h3 className="break-words text-sm font-semibold text-zinc-100">{item.title}</h3>
          <p className="mt-1 text-xs text-zinc-400">{sources.find(source => source.id === item.source)?.label}{item.estimated_value != null ? ` · ${money(item.estimated_value)}` : " · valor não informado"}</p>
          {(clientName(item.client_id) || caseTitle(item.case_id)) && <p className="mt-2 break-words text-xs text-zinc-300">{[clientName(item.client_id), caseTitle(item.case_id)].filter(Boolean).join(" · ")}</p>}
          {item.next_action ? <p className="mt-2 break-words text-xs text-blue-300">Próxima: {item.next_action}{item.next_action_at ? ` · ${dateText(item.next_action_at)}` : ""}</p> : <p className="mt-2 text-xs text-amber-300">Sem próxima ação definida</p>}
          {ownerName(item.owner_user_id) && <p className="mt-2 text-xs text-zinc-400">Responsável: {ownerName(item.owner_user_id)}</p>}
          {item.case_id && <Link className="mt-2 inline-flex min-h-11 items-center text-xs text-blue-300" href={`/dashboard/cases/${item.case_id}`}>Abrir processo</Link>}
          {canWrite && <div className="mt-3 flex flex-wrap gap-2"><button className={button} onClick={() => { setCreating(false); setEditing(item); scrollWorkspaceToTop(); }}>Editar</button>{nextStage[item.stage] && <Action run={() => api.put(`/crm/opportunities/${item.id}`, { stage: nextStage[item.stage], expected_revision: item.revision })} onDone={opportunities.reload}>Avançar</Action>}<Action run={async () => { if (!window.confirm("Arquivar esta oportunidade? Ela sairá do funil, mas continuará registrada.")) return; await api.post(`/crm/opportunities/${item.id}/archive`, { expected_revision: item.revision }); }} onDone={opportunities.reload}>Arquivar</Action></div>}
        </article>)}{!items.length && <p className="text-xs text-zinc-400">Nenhuma oportunidade nesta etapa.</p>}</div>
      </section>; })}
    </div> : null}
    {opportunities.data && opportunities.data.items.length >= opportunities.data.limit && <p className="text-xs text-amber-300">Exibindo 200 oportunidades priorizadas pela próxima ação.</p>}
  </div>;
}

export function CRM() {
  const [tab, setTab] = useState<"pipeline" | "clients">("pipeline");
  const [clientsVisited, setClientsVisited] = useState(false);
  return <Page title="Clientes e CRM" subtitle="Acompanhe oportunidades reais sem duplicar o cadastro de clientes do escritório.">
    <div aria-label="Clientes e oportunidades" className="flex max-w-full gap-1 overflow-x-auto rounded-lg bg-zinc-900 p-1">
      <button type="button" aria-pressed={tab === "pipeline"} className={`${tab === "pipeline" ? "bg-blue-600" : "hover:bg-zinc-800"} min-h-11 shrink-0 rounded-md px-4 text-sm text-white`} onClick={() => setTab("pipeline")}>Oportunidades</button>
      <button type="button" aria-pressed={tab === "clients"} className={`${tab === "clients" ? "bg-blue-600" : "hover:bg-zinc-800"} min-h-11 shrink-0 rounded-md px-4 text-sm text-white`} onClick={() => { setClientsVisited(true); setTab("clients"); }}>Clientes</button>
    </div>
    <div hidden={tab !== "pipeline"}><Pipeline /></div>
    {clientsVisited && <div hidden={tab !== "clients"}><Records kind="clients" embedded /></div>}
  </Page>;
}
