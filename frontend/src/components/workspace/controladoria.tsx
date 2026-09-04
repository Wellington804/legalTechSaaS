"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { Action, Field, Page, Panel, State, button, control, dateText, errorText, primary, useResource } from "./shared";
import type { List, Row } from "./records";

type SourceKind = "datajud" | "escavador" | "djen" | "domicilio" | "tribunal_api";
type Subscription = { id: string; case_id: string; source_kind: SourceKind; provider_subscription_id: string | null; provider_cursor: string | null; tribunal: string; process_number: string; status: "active" | "paused" | "disabled"; last_checked_at: string | null; last_success_at: string | null; last_error_code: string | null };
type ProviderStatus = { source_kind: SourceKind; label: string; configured: boolean; homologation_required: boolean; detail: string };
type JudicialEvent = { id: string; case_id: string; title: string; source_kind: "manual" | SourceKind; source_url: string; source_content: string | null; source_metadata: Record<string, unknown>; occurred_at: string | null; retrieved_at: string; triage_status: "pending" | "reviewed" | "discarded"; triage_note: string | null };
type DeadlineRule = { id: string; rule_key: string; version: number; rite: string; act_type: string; tribunal: string; days: number; counting_method: "business_days" | "calendar_days"; timezone_name: string; legal_sources: Array<{ title: string; url: string; reference: string }> };
type Deadline = { id: string; case_id: string; title: string; suggested_due_at: string; suggested_basis: string; status: "suggested" | "first_approved" | "approved" | "rejected"; rule_id: string | null; rule_version: number | null; calculation: Record<string, unknown> | null; calculation_revision: number; first_approved_by_user_id: string | null; first_approved_at: string | null; second_approved_by_user_id: string | null; review_note: string | null; source_stale_at: string | null; source_stale_event_id: string | null; event: JudicialEvent };
type WorkflowItem = { id: string; position: number; title: string; instructions: string | null; is_required: boolean; status: "pending" | "completed" | "skipped"; revision: number; resolution_note: string | null };
type WorkflowRun = { id: string; case_id: string; template_name: string; template_version: number; status: "open" | "completed" | "cancelled"; revision: number; items: WorkflowItem[] };
type WorkflowTemplate = { id: string; name: string; case_type: string | null; version: number; description: string | null };
type Items<T> = { items: T[]; limit: number };
type FromNumberResult = { case_id: string; case_title: string; case_created: boolean; subscription_created: boolean; subscription: Subscription };

const subscriptionStatus = { active: "Acompanhamento ativo", paused: "Acompanhamento pausado", disabled: "Acompanhamento desativado" };
const providerLabels: Record<SourceKind, string> = { datajud: "DataJud", escavador: "Escavador", djen: "DJEN", domicilio: "Domicílio Judicial", tribunal_api: "Tribunal integrado" };

function subscriptionStatusText(item: Subscription) {
  if (item.source_kind === "escavador" && item.status === "active" && !item.provider_subscription_id) return "Acompanhamento em ativação";
  return subscriptionStatus[item.status];
}

export function CaseMonitoring({ caseId, processNumber, court }: { caseId: string; processNumber?: string | null; court?: string | null }) {
  const subscriptions = useResource<Items<Subscription>>(`/controladoria/subscriptions?case_id=${encodeURIComponent(caseId)}`);
  const events = useResource<Items<JudicialEvent>>(`/controladoria/events?case_id=${encodeURIComponent(caseId)}&limit=5`);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const current = subscriptions.data?.items[0]; const latest = events.data?.items[0];
  return <Panel title="Acompanhamento processual">
    <p className="text-sm text-zinc-400">O tribunal é identificado pelo número CNJ. Novas movimentações entram para conferência; intimações e prazos continuam dependendo da fonte oficial.</p>
    <p className="text-sm">{processNumber || "Número CNJ não informado"} · {court || "Tribunal não informado"}</p>
    <State loading={subscriptions.loading || events.loading} error={subscriptions.error || events.error || error} />
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    {!current ? <Action className={primary} run={async () => { setError(""); try { await api.post("/controladoria/subscriptions", { case_id: caseId, source_kind: "djen" }); subscriptions.reload(); } catch (reason) { setError(errorText(reason)); } }}>Ativar acompanhamento pelo DJEN</Action>
      : <div className="space-y-3"><p className="text-sm font-medium">{subscriptionStatusText(current)} · {providerLabels[current.source_kind]} · {current.tribunal.toUpperCase()}</p><p className="text-xs text-zinc-400">Última consulta: {dateText(current.last_success_at || current.last_checked_at)}{current.last_error_code ? " · a última consulta precisa de atenção" : ""}</p><div className="flex flex-wrap gap-2">{current.status === "active" && <Action className={primary} run={() => api.post(`/controladoria/subscriptions/${current.id}/refresh`, {})} onDone={() => setNotice("Consulta iniciada. Atualize esta área em alguns instantes para ver novas movimentações.")}>Consultar agora</Action>}{current.status === "active" ? <Action run={() => api.put(`/controladoria/subscriptions/${current.id}`, { status: "paused" })} onDone={subscriptions.reload}>Pausar</Action> : <Action className={primary} run={() => api.put(`/controladoria/subscriptions/${current.id}`, { status: "active" })} onDone={subscriptions.reload}>Retomar</Action>}</div></div>}
    {latest && <article className="rounded-lg border border-zinc-800 p-3"><p className="text-xs text-zinc-400">Movimentação mais recente · {dateText(latest.occurred_at || latest.retrieved_at)}</p><p className="mt-1 text-sm">{latest.title}</p><p className="mt-1 text-xs text-amber-300">Pendente de conferência humana; nenhum prazo foi criado automaticamente.</p></article>}
  </Panel>;
}

export function Controladoria() {
  const subscriptions = useResource<Items<Subscription>>("/controladoria/subscriptions");
  const providers = useResource<ProviderStatus[]>("/controladoria/providers");
  const events = useResource<Items<JudicialEvent>>("/controladoria/events?triage_status=pending");
  const reviewedEvents = useResource<Items<JudicialEvent>>("/controladoria/events?triage_status=reviewed");
  const deadlines = useResource<Items<Deadline>>("/controladoria/deadlines?limit=100");
  const deadlineRules = useResource<Items<DeadlineRule>>("/controladoria/deadline-rules?status=active");
  const workflowTemplates = useResource<Items<WorkflowTemplate>>("/controladoria/workflow-templates");
  const workflows = useResource<Items<WorkflowRun>>("/controladoria/workflows");
  const cases = useResource<List>("/workspace/cases");
  const clients = useResource<List>("/workspace/clients");
  const [creating, setCreating] = useState<"existing" | "number" | null>(null);
  const [createError, setCreateError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState("");
  const pendingDeadlines = deadlines.data?.items.filter(item => item.status === "suggested" || item.status === "first_approved") || [];
  const pendingEvents = events.data?.items.length ?? 0;

  async function createSubscription(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true); setCreateError("");
    try {
      if (creating === "number") {
        const result = await api.post<FromNumberResult>("/controladoria/subscriptions/from-number", {
          client_id: values.get("client_id"), process_number: values.get("process_number"),
          title: values.get("title") || null, source_kind: values.get("source_kind"),
        });
        const state = subscriptionStatus[result.subscription.status].toLocaleLowerCase("pt-BR");
        setRefreshNotice(result.case_created
          ? `O processo “${result.case_title}” foi cadastrado com ${state}.`
          : `O processo “${result.case_title}” já estava cadastrado e está com ${state}.`);
        cases.reload();
      } else {
        await api.post("/controladoria/subscriptions", { case_id: values.get("case_id"), source_kind: values.get("source_kind") });
        setRefreshNotice("Acompanhamento iniciado. As novas movimentações entrarão na fila de revisão.");
      }
      form.reset(); setCreating(null); subscriptions.reload();
    } catch (error) { setCreateError(errorText(error)); } finally { setBusy(false); }
  }

  return <Page title="Controladoria judicial" subtitle="Revise movimentações, confira prazos sugeridos e organize as próximas providências.">
    <section aria-labelledby="controladoria-next" className="rounded-2xl border border-blue-800/60 bg-blue-950/40 p-5 md:p-6">
      <h2 id="controladoria-next" className="text-lg font-semibold text-blue-100">Pendências de hoje</h2>
      <p className="mt-2 text-sm text-blue-100">{pendingEvents} movimentaç{pendingEvents === 1 ? "ão" : "ões"} e {pendingDeadlines.length} prazo{pendingDeadlines.length === 1 ? "" : "s"} aguardando conferência.</p>
      <button type="button" className={`${primary} mt-4`} onClick={() => document.getElementById(pendingEvents ? "eventos-pendentes" : pendingDeadlines.length ? "prazos-pendentes" : "acompanhamentos")?.scrollIntoView({ behavior: "smooth" })}>{pendingEvents ? "Revisar movimentações" : pendingDeadlines.length ? "Revisar prazos" : "Acompanhar um processo"}</button>
    </section>

    <Panel title="Movimentações para revisar" description="Confirme o conteúdo na fonte oficial antes de tomar qualquer providência."><div id="eventos-pendentes" /><State loading={events.loading} error={events.error} />{!events.loading && !events.error && !events.data?.items.length && <p className="text-sm text-zinc-400">Nenhuma movimentação aguarda revisão.</p>}<div className="divide-y divide-zinc-800">{events.data?.items.map(item => <EventTriage key={item.id} event={item} onDone={() => { events.reload(); reviewedEvents.reload(); }} />)}</div></Panel>

    <Panel title="Prazos aguardando aprovação" description="A tarefa só é criada depois de duas conferências por pessoas diferentes."><div id="prazos-pendentes" /><State loading={deadlines.loading} error={deadlines.error} />{!deadlines.loading && !deadlines.error && !pendingDeadlines.length && <p className="text-sm text-zinc-400">Nenhum prazo aguarda aprovação.</p>}<div className="divide-y divide-zinc-800">{pendingDeadlines.map(item => <DeadlineDecision key={item.id} deadline={item} onDone={deadlines.reload} />)}</div></Panel>

    <Panel title="Processos acompanhados" description="Novas movimentações entram nesta página para revisão; o acompanhamento não substitui a consulta ao tribunal.">
      <div id="acompanhamentos" />
      {!creating && <button type="button" className={button} onClick={() => setCreating("existing")}>Acompanhar processo</button>}
      {creating && <form onSubmit={createSubscription} className="max-w-2xl space-y-4"><fieldset disabled={busy} className="space-y-4">
        <div className="flex w-full gap-1 rounded-lg bg-zinc-900 p-1 sm:w-fit" role="group" aria-label="Origem do processo">
          <button type="button" aria-pressed={creating === "existing"} className={`${creating === "existing" ? "bg-blue-600 text-white" : "text-zinc-300 hover:bg-zinc-800"} min-h-10 flex-1 rounded-md px-3 text-sm sm:flex-none`} onClick={() => { setCreating("existing"); setCreateError(""); }}>Já cadastrado</button>
          <button type="button" aria-pressed={creating === "number"} className={`${creating === "number" ? "bg-blue-600 text-white" : "text-zinc-300 hover:bg-zinc-800"} min-h-10 flex-1 rounded-md px-3 text-sm sm:flex-none`} onClick={() => { setCreating("number"); setCreateError(""); }}>Novo número</button>
        </div>
        {creating === "existing" ? <Field label="Processo"><select name="case_id" className={control} required defaultValue=""><option value="">Selecione o processo…</option>{cases.data?.items.map((item: Row) => <option key={item.id} value={item.id}>{item.title || "Processo sem título"}</option>)}</select></Field> : <>
          <div className="grid gap-3 sm:grid-cols-2"><Field label="Cliente"><select name="client_id" className={control} required defaultValue=""><option value="">Selecione o cliente…</option>{clients.data?.items.map((item: Row) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Número CNJ"><input name="process_number" className={control} required inputMode="numeric" minLength={20} maxLength={64} placeholder="0000000-00.0000.0.00.0000" /></Field></div>
          <Field label="Nome do processo (opcional)"><input name="title" className={control} minLength={2} maxLength={300} placeholder="Ex.: Cumprimento de sentença — Cliente" /></Field>
          <p className="text-xs text-zinc-400">Se o número ainda não existir no escritório, o processo será cadastrado para o cliente escolhido e ficará sob sua responsabilidade.</p>
        </>}
        <details className="border-t border-zinc-800 pt-2"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-blue-300">Escolher fonte de consulta</summary><div className="mt-2 max-w-md">{providers.data && <Field label="Fonte"><select name="source_kind" className={control} required defaultValue="djen">{providers.data.map(provider => <option key={provider.source_kind} value={provider.source_kind} disabled={!provider.configured}>{providerLabels[provider.source_kind]}{provider.configured ? "" : " · indisponível"}</option>)}</select></Field>}</div></details>
        <State error={createError || cases.error || clients.error || (providers.error ? "As fontes de consulta estão indisponíveis no momento." : "")} />
        <div className="flex flex-wrap gap-2"><button disabled={busy || providers.loading || !providers.data?.length || Boolean(providers.error)} className={primary}>{busy ? "Salvando…" : providers.loading ? "Carregando…" : "Iniciar acompanhamento"}</button><button type="button" className={button} onClick={() => { setCreating(null); setCreateError(""); }}>Cancelar</button></div>
      </fieldset></form>}
      <State loading={subscriptions.loading} error={subscriptions.error} />
      {refreshNotice && <p role="status" className="text-sm text-emerald-300">{refreshNotice}</p>}
      {!subscriptions.loading && !subscriptions.error && !subscriptions.data?.items.length && <p className="text-sm text-zinc-400">Nenhum processo em acompanhamento. Use o botão acima para começar.</p>}
      <div className="divide-y divide-zinc-800">{subscriptions.data?.items.map(item => <article key={item.id} className="py-3"><p className="text-sm font-medium">{item.process_number || "Número do processo não informado"} · {item.tribunal.toUpperCase()}</p><p className="mt-1 text-xs text-zinc-400">{subscriptionStatusText(item)} · {providerLabels[item.source_kind]} · última conferência: {dateText(item.last_success_at || item.last_checked_at)}</p>{item.last_error_code && <p className="mt-1 text-xs text-amber-300">A última consulta precisa de atenção. Confira a fonte oficial.</p>}<div className="mt-2 flex flex-wrap gap-2">{item.status === "active" && <Action className={primary} run={() => api.post(`/controladoria/subscriptions/${item.id}/refresh`, {})} onDone={() => setRefreshNotice("Consulta iniciada. Novos resultados entrarão na fila de revisão.")}>Consultar agora</Action>}{item.status === "active" && <Action className={button} run={() => api.put(`/controladoria/subscriptions/${item.id}`, { status: "paused" })} onDone={subscriptions.reload}>Pausar acompanhamento</Action>}{item.status !== "active" && <Action className={primary} run={() => api.put(`/controladoria/subscriptions/${item.id}`, { status: "active" })} onDone={subscriptions.reload}>{item.status === "disabled" ? "Reativar acompanhamento" : "Retomar acompanhamento"}</Action>}{item.status !== "disabled" && <Action className={button} run={() => api.put(`/controladoria/subscriptions/${item.id}`, { status: "disabled" })} onDone={subscriptions.reload}>Desativar</Action>}</div></article>)}</div>
    </Panel>

    <details className="rounded-xl border border-zinc-800 bg-zinc-900/25 p-4 shadow-sm md:p-5"><summary className="min-h-11 cursor-pointer content-center text-base font-semibold text-zinc-100">Calcular prazo a partir de uma movimentação</summary><div className="mt-4 space-y-4 border-t border-zinc-800 pt-4"><p className="text-sm text-zinc-400">Escolha uma movimentação já revisada, a regra aplicável e a data inicial conferida.</p><State loading={reviewedEvents.loading || deadlineRules.loading} error={reviewedEvents.error || deadlineRules.error} />{reviewedEvents.data?.items.length && deadlineRules.data?.items.length ? <DeadlineSuggestion events={reviewedEvents.data.items} rules={deadlineRules.data.items} onDone={deadlines.reload} /> : !reviewedEvents.loading && !deadlineRules.loading && <p className="text-sm text-zinc-400">Primeiro revise uma movimentação. Também é necessário haver uma regra de prazo aprovada.</p>}</div></details>
    <details className="rounded-xl border border-zinc-800 bg-zinc-900/25 p-4 shadow-sm md:p-5"><summary className="min-h-11 cursor-pointer content-center text-base font-semibold text-zinc-100">Roteiros de providências</summary><div className="mt-4 space-y-4 border-t border-zinc-800 pt-4"><p className="text-sm text-zinc-400">Use um roteiro para não esquecer conferências importantes. Concluir uma etapa não envia peças nem altera prazos.</p><State loading={workflowTemplates.loading || cases.loading} error={workflowTemplates.error || cases.error} />{workflowTemplates.data?.items.length ? <WorkflowStart templates={workflowTemplates.data.items} cases={cases.data?.items || []} onDone={workflows.reload} /> : !workflowTemplates.loading && <p className="text-sm text-zinc-400">Nenhum roteiro disponível.</p>}<State loading={workflows.loading} error={workflows.error} />{!workflows.loading && !workflows.error && !workflows.data?.items.length && <p className="text-sm text-zinc-400">Nenhum roteiro em andamento.</p>}<div className="divide-y divide-zinc-800">{workflows.data?.items.map(run => <WorkflowChecklist key={run.id} run={run} onDone={workflows.reload} />)}</div></div></details>
  </Page>;
}

function DeadlineSuggestion({ events, rules, onDone }: { events: JudicialEvent[]; rules: DeadlineRule[]; onDone: () => void }) {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [eventId, setEventId] = useState(""); const [title, setTitle] = useState("");
  return <form className="mt-3 max-w-xl space-y-3" onSubmit={async submit => { submit.preventDefault(); const form = submit.currentTarget; const values = new FormData(form); setBusy(true); setError(""); try { await api.post("/controladoria/deadlines/calculate", { event_id: values.get("event_id"), rule_id: values.get("rule_id"), title: values.get("title"), triggered_at: new Date(String(values.get("triggered_at"))).toISOString(), assigned_user_id: null }); form.reset(); setEventId(""); setTitle(""); onDone(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }}><fieldset disabled={busy} className="space-y-3"><Field label="Movimentação revisada"><select className={control} name="event_id" required value={eventId} onChange={change => { const selected = events.find(item => item.id === change.target.value); setEventId(change.target.value); setTitle(typeof selected?.source_metadata.suggested_action === "string" ? selected.source_metadata.suggested_action : ""); }}><option value="">Selecione…</option>{events.map(event => <option key={event.id} value={event.id}>{event.title}</option>)}</select></Field><Field label="Regra de contagem aprovada"><select className={control} name="rule_id" required defaultValue=""><option value="">Selecione…</option>{rules.map(rule => <option key={rule.id} value={rule.id}>{rule.rite} · {rule.act_type} · {rule.tribunal.toUpperCase()} · {rule.days} {rule.counting_method === "business_days" ? "dias úteis" : "dias corridos"}</option>)}</select></Field><Field label="Providência"><input className={control} name="title" minLength={2} maxLength={300} required value={title} onChange={change => setTitle(change.target.value)} placeholder="Ex.: Protocolar manifestação" /></Field><Field label="Data inicial conferida"><input className={control} name="triggered_at" type="datetime-local" required /></Field><p className="text-xs text-amber-300">O resultado ainda exige duas aprovações humanas distintas. Confira publicação, regra, feriados e suspensões.</p><State error={error} /><button className={primary}>{busy ? "Calculando…" : "Calcular e enviar para conferência"}</button></fieldset></form>;
}

function EventTriage({ event, onDone }: { event: JudicialEvent; onDone: () => void }) {
  const [discarding, setDiscarding] = useState(false);
  const [note, setNote] = useState("");
  return <article className="py-4"><p className="text-sm font-medium">{event.title}</p><p className="mt-1 text-xs text-zinc-400">{event.source_kind === "manual" ? "Evento registrado pelo escritório" : `Movimentação recebida via ${providerLabels[event.source_kind]}`} · {dateText(event.occurred_at || event.retrieved_at)}</p>{typeof event.source_metadata.suggested_action === "string" && <p className="mt-2 text-sm text-blue-200">Providência sugerida: {event.source_metadata.suggested_action}</p>}<EventEvidence event={event} /><p className="text-xs text-amber-300">A confirmação significa apenas que você revisou o evento. Confira a publicação e o processo na fonte oficial.</p>{discarding && <Field label="Motivo do descarte"><textarea className={control} value={note} onChange={value => setNote(value.target.value)} rows={3} minLength={3} maxLength={5000} required /></Field>}<div className="mt-3 flex flex-wrap gap-2">{!discarding ? <><Action className={primary} run={() => api.post(`/controladoria/events/${event.id}/triage`, { status: "reviewed" })} onDone={onDone}>Confirmar revisão</Action><button type="button" className={button} onClick={() => setDiscarding(true)}>Descartar evento</button></> : <><Action className={primary} run={() => { if (note.trim().length < 3) return Promise.reject(new Error("Informe o motivo do descarte.")); return api.post(`/controladoria/events/${event.id}/triage`, { status: "discarded", note }); }} onDone={onDone}>Confirmar descarte</Action><button type="button" className={button} onClick={() => { setDiscarding(false); setNote(""); }}>Cancelar</button></>}</div></article>;
}

function DeadlineDecision({ deadline, onDone }: { deadline: Deadline; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const decide = (decision: "approved" | "rejected") => {
    if (note.trim().length < 3) return Promise.reject(new Error("Registre a conferência antes de decidir."));
    return api.post(`/controladoria/deadlines/${deadline.id}/decision`, { decision, note, expected_calculation_revision: deadline.calculation_revision });
  };
  const calculation = deadline.calculation as { term_start?: string; days?: number; counting_method?: string; timezone?: string; excluded_dates?: Array<{ date: string; reasons: Array<{ name: string }> }>; rule?: { key?: string; version?: number; legal_sources?: Array<{ title: string; url: string; reference: string }> } } | null;
  const firstStage = deadline.status === "suggested";
  return <article className="py-4"><p className="text-sm font-medium">{deadline.title}</p><p className="mt-1 text-sm text-zinc-300">Data sugerida: {dateText(deadline.suggested_due_at)}</p>{deadline.source_stale_at ? <p role="alert" className="mt-1 text-sm text-red-300">A fonte judicial mudou depois deste cálculo. Rejeite esta sugestão e revise a nova movimentação.</p> : <p className="mt-1 text-xs text-blue-200">{firstStage ? "Aguardando primeira aprovação" : "A primeira aprovação foi registrada; falta a conferência de outra pessoa."}</p>}<p className="mt-2 whitespace-pre-wrap text-xs text-zinc-400">Fundamento registrado: {deadline.suggested_basis}</p>{calculation && <details className="mt-2 rounded-lg border border-zinc-800 p-3 text-xs text-zinc-300"><summary className="min-h-11 cursor-pointer content-center">Como a data foi calculada</summary><p>Data inicial: {calculation.term_start} · {calculation.days} {calculation.counting_method === "business_days" ? "dias úteis" : "dias corridos"}</p>{Boolean(calculation.excluded_dates?.length) && <ul className="mt-2 list-disc space-y-1 pl-5">{calculation.excluded_dates?.map(item => <li key={item.date}>{item.date}: {item.reasons.map(reason => reason.name).join(", ")}</li>)}</ul>}{calculation.rule?.legal_sources?.map(source => <a key={`${source.url}-${source.reference}`} className="mt-2 block text-blue-300" href={source.url} target="_blank" rel="noreferrer">{source.title} · {source.reference}</a>)}</details>}<EventEvidence event={deadline.event} /><p className="mt-2 text-xs text-amber-300">{firstStage ? "Esta aprovação não cria tarefa. Outra pessoa autorizada deverá conferir novamente." : "A segunda aprovação cria a tarefa. Quem fez a primeira conferência não pode fazer a segunda."}</p>{!open ? <button type="button" className={`${button} mt-3`} onClick={() => setOpen(true)}>Revisar prazo</button> : <div className="mt-3 space-y-3"><Field label="Registro da conferência"><textarea className={control} value={note} onChange={event => setNote(event.target.value)} rows={3} minLength={3} maxLength={5000} required placeholder="Ex.: Conferi publicação, regra, feriados e suspensão no tribunal." /></Field><div className="flex flex-wrap gap-2">{!deadline.source_stale_at && <Action className={primary} run={() => decide("approved")} onDone={onDone}>{firstStage ? "Registrar primeira aprovação" : "Registrar segunda aprovação e criar tarefa"}</Action>}<Action run={() => decide("rejected")} onDone={onDone}>Rejeitar sugestão</Action><button type="button" className={button} onClick={() => { setOpen(false); setNote(""); }}>Cancelar</button></div></div>}</article>;
}

function EventEvidence({ event }: { event: JudicialEvent }) {
  return <section aria-label="Fonte da movimentação" className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-300"><p className="font-medium text-zinc-200">Conteúdo recebido</p><p className="mt-1 text-zinc-400">Consultado em {dateText(event.retrieved_at)}. Confirme no tribunal antes de agir.</p><p className="mt-2 whitespace-pre-wrap">{event.source_content || "A fonte não forneceu texto adicional."}</p><a className="mt-2 inline-flex min-h-11 items-center text-blue-300" href={event.source_url} target="_blank" rel="noreferrer">Abrir fonte original</a></section>;
}

function WorkflowStart({ templates, cases, onDone }: { templates: WorkflowTemplate[]; cases: Row[]; onDone: () => void }) {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  return <form className="max-w-xl space-y-3" onSubmit={async event => { event.preventDefault(); const values = new FormData(event.currentTarget); setBusy(true); setError(""); try { await api.post("/controladoria/workflows", { case_id: values.get("case_id"), template_id: values.get("template_id") }); event.currentTarget.reset(); onDone(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }}><fieldset disabled={busy} className="space-y-3"><Field label="Processo"><select className={control} name="case_id" required defaultValue=""><option value="">Selecione…</option>{cases.map(item => <option key={item.id} value={item.id}>{item.title || "Processo sem título"}</option>)}</select></Field><Field label="Roteiro"><select className={control} name="template_id" required defaultValue=""><option value="">Selecione…</option>{templates.map(template => <option key={template.id} value={template.id}>{template.name}{template.case_type ? ` · ${template.case_type}` : ""}</option>)}</select></Field><State error={error} /><button className={primary}>{busy ? "Iniciando…" : "Iniciar roteiro"}</button></fieldset></form>;
}

function WorkflowChecklist({ run, onDone }: { run: WorkflowRun; onDone: () => void }) {
  return <article className="py-4"><p className="text-sm font-medium">{run.template_name}</p><p className="mt-1 text-xs text-zinc-400">Roteiro {run.status === "open" ? "em andamento" : run.status === "completed" ? "concluído" : "cancelado"}</p><ol className="mt-3 space-y-2">{run.items.map(item => <li key={item.id} className="rounded-lg border border-zinc-800 p-3"><p className="text-sm">{item.position}. {item.title} {item.is_required && <span className="text-amber-300">(obrigatório)</span>}</p>{item.instructions && <p className="mt-1 whitespace-pre-wrap text-xs text-zinc-400">{item.instructions}</p>}<p className="mt-1 text-xs text-zinc-400">{item.status === "pending" ? "Pendente" : item.status === "completed" ? "Concluído" : "Ignorado"}{item.resolution_note ? ` · ${item.resolution_note}` : ""}</p>{run.status === "open" && item.status === "pending" && <Action className={`${button} mt-2`} run={() => api.post(`/controladoria/workflows/${run.id}/items/${item.id}`, { status: "completed", resolution_note: null, expected_revision: item.revision })} onDone={onDone}>Concluir etapa</Action>}</li>)}</ol>{run.status === "open" && <Action className={`${primary} mt-3`} run={() => api.post(`/controladoria/workflows/${run.id}/complete`, { expected_revision: run.revision })} onDone={onDone}>Encerrar roteiro</Action>}</article>;
}
