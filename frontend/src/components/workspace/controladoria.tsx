"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { Action, Field, Page, Panel, State, button, control, dateText, errorText, primary, useResource } from "./shared";
import type { List, Row } from "./records";

type Subscription = { id: string; case_id: string; source_kind: "datajud" | "escavador"; tribunal: string; process_number: string; status: "active" | "paused" | "disabled"; last_checked_at: string | null; last_success_at: string | null; last_error_code: string | null };
type JudicialEvent = { id: string; case_id: string; title: string; source_kind: "manual" | "datajud" | "escavador"; source_url: string; source_content: string | null; source_metadata: Record<string, unknown>; occurred_at: string | null; retrieved_at: string; triage_status: "pending" | "reviewed" | "discarded"; triage_note: string | null };
type Deadline = { id: string; case_id: string; title: string; suggested_due_at: string; suggested_basis: string; status: "suggested" | "approved" | "rejected"; review_note: string | null; event: JudicialEvent };
type WorkflowItem = { id: string; position: number; title: string; instructions: string | null; is_required: boolean; status: "pending" | "completed" | "skipped"; revision: number; resolution_note: string | null };
type WorkflowRun = { id: string; case_id: string; template_name: string; template_version: number; status: "open" | "completed" | "cancelled"; revision: number; items: WorkflowItem[] };
type WorkflowTemplate = { id: string; name: string; case_type: string | null; version: number; description: string | null };
type Items<T> = { items: T[]; limit: number };

const subscriptionStatus = { active: "Acompanhamento ativo", paused: "Acompanhamento pausado", disabled: "Acompanhamento desativado" };

export function CaseMonitoring({ caseId, processNumber, court }: { caseId: string; processNumber?: string | null; court?: string | null }) {
  const subscriptions = useResource<Items<Subscription>>(`/controladoria/subscriptions?case_id=${encodeURIComponent(caseId)}`);
  const events = useResource<Items<JudicialEvent>>(`/controladoria/events?case_id=${encodeURIComponent(caseId)}&limit=5`);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const current = subscriptions.data?.items[0]; const latest = events.data?.items[0];
  return <Panel title="Acompanhamento pelo DataJud">
    <p className="text-sm text-zinc-400">O tribunal é identificado pelo número CNJ. Novas movimentações entram para conferência; intimações e prazos continuam dependendo da fonte oficial.</p>
    <p className="text-sm">{processNumber || "Número CNJ não informado"} · {court || "Tribunal não informado"}</p>
    <State loading={subscriptions.loading || events.loading} error={subscriptions.error || events.error || error} />
    {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}
    {!current ? <Action className={primary} run={async () => { setError(""); try { await api.post("/controladoria/subscriptions", { case_id: caseId }); subscriptions.reload(); } catch (reason) { setError(errorText(reason)); } }}>Ativar acompanhamento</Action>
      : <div className="space-y-3"><p className="text-sm font-medium">{subscriptionStatus[current.status]} · {current.tribunal.toUpperCase()}</p><p className="text-xs text-zinc-400">Última consulta: {dateText(current.last_success_at || current.last_checked_at)}{current.last_error_code ? " · a última consulta precisa de atenção" : ""}</p><div className="flex flex-wrap gap-2">{current.status === "active" && <Action className={primary} run={() => api.post(`/controladoria/subscriptions/${current.id}/refresh`, {})} onDone={() => setNotice("Consulta iniciada. Atualize esta área em alguns instantes para ver novas movimentações.")}>Consultar agora</Action>}{current.status === "active" ? <Action run={() => api.put(`/controladoria/subscriptions/${current.id}`, { status: "paused" })} onDone={subscriptions.reload}>Pausar</Action> : <Action className={primary} run={() => api.put(`/controladoria/subscriptions/${current.id}`, { status: "active" })} onDone={subscriptions.reload}>Retomar</Action>}</div></div>}
    {latest && <article className="rounded-lg border border-zinc-800 p-3"><p className="text-xs text-zinc-400">Movimentação mais recente · {dateText(latest.occurred_at || latest.retrieved_at)}</p><p className="mt-1 text-sm">{latest.title}</p><p className="mt-1 text-xs text-amber-300">Pendente de conferência humana; nenhum prazo foi criado automaticamente.</p></article>}
  </Panel>;
}

export function Controladoria() {
  const subscriptions = useResource<Items<Subscription>>("/controladoria/subscriptions");
  const events = useResource<Items<JudicialEvent>>("/controladoria/events?triage_status=pending");
  const reviewedEvents = useResource<Items<JudicialEvent>>("/controladoria/events?triage_status=reviewed");
  const deadlines = useResource<Items<Deadline>>("/controladoria/deadlines?status=suggested");
  const workflowTemplates = useResource<Items<WorkflowTemplate>>("/controladoria/workflow-templates");
  const workflows = useResource<Items<WorkflowRun>>("/controladoria/workflows");
  const cases = useResource<List>("/workspace/cases");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshNotice, setRefreshNotice] = useState("");

  async function createSubscription(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setBusy(true); setCreateError("");
    try {
      await api.post("/controladoria/subscriptions", { case_id: values.get("case_id") });
      event.currentTarget.reset(); setCreating(false); subscriptions.reload();
    } catch (error) { setCreateError(errorText(error)); } finally { setBusy(false); }
  }

  return <Page title="Controladoria judicial" subtitle="Acompanhe movimentações e revise cada evento e prazo antes de qualquer providência. O sistema não confirma intimações nem calcula prazos automaticamente.">
    <section aria-labelledby="controladoria-next" className="rounded-2xl bg-blue-500/10 p-5 md:p-6"><h2 id="controladoria-next" className="text-lg font-semibold text-blue-100">Próxima conferência</h2><p className="mt-2 text-sm text-zinc-200">Há {events.data?.items.length ?? 0} evento{(events.data?.items.length ?? 0) === 1 ? "" : "s"} e {deadlines.data?.items.length ?? 0} prazo{(deadlines.data?.items.length ?? 0) === 1 ? "" : "s"} aguardando sua revisão.</p><button type="button" className={`${primary} mt-4`} onClick={() => document.getElementById("eventos-pendentes")?.scrollIntoView({ behavior: "smooth" })}>Revisar eventos pendentes</button></section>

    <Panel title="Acompanhamento processual">
      <p className="text-sm text-zinc-400">Escolha um processo com número CNJ. O LexFlow identifica o tribunal e registra movimentações para sua triagem; ele não substitui a fonte oficial.</p>
      {!creating && <button type="button" className={button} onClick={() => setCreating(true)}>Adicionar acompanhamento</button>}
      {creating && <form onSubmit={createSubscription} className="mt-4 max-w-xl space-y-3"><fieldset disabled={busy} className="space-y-3"><Field label="Processo"><select name="case_id" className={control} required defaultValue=""><option value="">Selecione o processo…</option>{cases.data?.items.map((item: Row) => <option key={item.id} value={item.id}>{item.title || "Processo sem título"}</option>)}</select></Field><p className="text-xs text-amber-300">Confira o número CNJ no processo antes de salvar.</p><State error={createError || cases.error} /><div className="flex flex-wrap gap-2"><button className={primary}>{busy ? "Salvando…" : "Iniciar acompanhamento"}</button><button type="button" className={button} onClick={() => { setCreating(false); setCreateError(""); }}>Cancelar</button></div></fieldset></form>}
      <State loading={subscriptions.loading} error={subscriptions.error} />
      {refreshNotice && <p role="status" className="text-sm text-emerald-300">{refreshNotice}</p>}
      {!subscriptions.loading && !subscriptions.error && !subscriptions.data?.items.length && <p className="text-sm text-zinc-400">Nenhum processo está sendo acompanhado ainda.</p>}
      <div className="divide-y divide-zinc-800">{subscriptions.data?.items.map(item => <article key={item.id} className="py-3"><p className="text-sm font-medium">{item.process_number || "Número do processo não informado"} · {item.tribunal.toUpperCase()}</p><p className="mt-1 text-xs text-zinc-400">{subscriptionStatus[item.status]} · última conferência: {dateText(item.last_success_at || item.last_checked_at)}</p>{item.last_error_code && <p className="mt-1 text-xs text-amber-300">A última consulta precisa de atenção. Confira a fonte oficial.</p>}<div className="mt-2 flex flex-wrap gap-2">{item.status === "active" && <Action className={primary} run={() => api.post(`/controladoria/subscriptions/${item.id}/refresh`, {})} onDone={() => setRefreshNotice("Consulta iniciada. Novos resultados entrarão na fila de revisão.")}>Consultar agora</Action>}{item.status === "active" && <Action className={button} run={() => api.put(`/controladoria/subscriptions/${item.id}`, { status: "paused" })} onDone={subscriptions.reload}>Pausar acompanhamento</Action>}{item.status !== "active" && <Action className={primary} run={() => api.put(`/controladoria/subscriptions/${item.id}`, { status: "active" })} onDone={subscriptions.reload}>{item.status === "disabled" ? "Reativar acompanhamento" : "Retomar acompanhamento"}</Action>}{item.status !== "disabled" && <Action className={button} run={() => api.put(`/controladoria/subscriptions/${item.id}`, { status: "disabled" })} onDone={subscriptions.reload}>Desativar</Action>}</div></article>)}</div>
    </Panel>

    <Panel title="Eventos para triagem"><div id="eventos-pendentes" /><State loading={events.loading} error={events.error} />{!events.loading && !events.error && !events.data?.items.length && <p className="text-sm text-zinc-400">Não há eventos aguardando triagem.</p>}<div className="divide-y divide-zinc-800">{events.data?.items.map(item => <EventTriage key={item.id} event={item} onDone={() => { events.reload(); reviewedEvents.reload(); }} />)}</div></Panel>
    <Panel title="Registrar data para segunda conferência"><p className="text-sm text-zinc-400">Use somente um evento já revisado. A data ficará como sugestão e só entrará na agenda depois de uma aprovação humana separada.</p><State loading={reviewedEvents.loading} error={reviewedEvents.error} />{reviewedEvents.data?.items.length ? <DeadlineSuggestion events={reviewedEvents.data.items} onDone={deadlines.reload} /> : !reviewedEvents.loading && <p className="text-sm text-zinc-400">Revise um evento antes de registrar uma data.</p>}</Panel>
    <Panel title="Prazos sugeridos para conferência"><State loading={deadlines.loading} error={deadlines.error} />{!deadlines.loading && !deadlines.error && !deadlines.data?.items.length && <p className="text-sm text-zinc-400">Não há prazos aguardando decisão.</p>}<div className="divide-y divide-zinc-800">{deadlines.data?.items.map(item => <DeadlineDecision key={item.id} deadline={item} onDone={deadlines.reload} />)}</div></Panel>
    <Panel title="Etapas e conferências do processo"><p className="text-sm text-zinc-400">Use roteiros para não esquecer conferências importantes. Concluir uma etapa não envia peças nem altera prazos.</p><State loading={workflowTemplates.loading || cases.loading} error={workflowTemplates.error || cases.error} />{workflowTemplates.data?.items.length ? <WorkflowStart templates={workflowTemplates.data.items} cases={cases.data?.items || []} onDone={workflows.reload} /> : !workflowTemplates.loading && <p className="text-sm text-zinc-400">Não há modelos de roteiro disponíveis.</p>}<State loading={workflows.loading} error={workflows.error} />{!workflows.loading && !workflows.error && !workflows.data?.items.length && <p className="text-sm text-zinc-400">Nenhum roteiro iniciado nos processos acessíveis.</p>}<div className="divide-y divide-zinc-800">{workflows.data?.items.map(run => <WorkflowChecklist key={run.id} run={run} onDone={workflows.reload} />)}</div></Panel>
  </Page>;
}

function DeadlineSuggestion({ events, onDone }: { events: JudicialEvent[]; onDone: () => void }) {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  return <form className="mt-3 max-w-xl space-y-3" onSubmit={async submit => { submit.preventDefault(); const form = submit.currentTarget; const values = new FormData(form); setBusy(true); setError(""); try { await api.post("/controladoria/deadlines", { event_id: values.get("event_id"), title: values.get("title"), suggested_due_at: new Date(String(values.get("suggested_due_at"))).toISOString(), suggested_basis: values.get("suggested_basis"), assigned_user_id: null }); form.reset(); onDone(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }}><fieldset disabled={busy} className="space-y-3"><Field label="Evento revisado"><select className={control} name="event_id" required defaultValue=""><option value="">Selecione…</option>{events.map(event => <option key={event.id} value={event.id}>{event.title}</option>)}</select></Field><Field label="Providência"><input className={control} name="title" minLength={2} maxLength={300} required placeholder="Ex.: Protocolar manifestação" /></Field><Field label="Data e hora a conferir"><input className={control} name="suggested_due_at" type="datetime-local" required /></Field><Field label="Como essa data foi obtida"><textarea className={control} name="suggested_basis" minLength={5} maxLength={5000} rows={3} required placeholder="Registre a fonte e a forma de contagem; não use apenas uma resposta da IA." /></Field><State error={error} /><button className={primary}>{busy ? "Registrando…" : "Registrar para aprovação"}</button></fieldset></form>;
}

function EventTriage({ event, onDone }: { event: JudicialEvent; onDone: () => void }) {
  const [discarding, setDiscarding] = useState(false);
  const [note, setNote] = useState("");
  return <article className="py-4"><p className="text-sm font-medium">{event.title}</p><p className="mt-1 text-xs text-zinc-400">{event.source_kind === "manual" ? "Evento registrado pelo escritório" : "Movimentação recebida pelo acompanhamento processual"} · {dateText(event.occurred_at || event.retrieved_at)}</p><EventEvidence event={event} /><p className="text-xs text-amber-300">A confirmação significa apenas que você revisou o evento. Confira a publicação e o processo na fonte oficial.</p>{discarding && <Field label="Motivo do descarte"><textarea className={control} value={note} onChange={value => setNote(value.target.value)} rows={3} minLength={3} maxLength={5000} required /></Field>}<div className="mt-3 flex flex-wrap gap-2">{!discarding ? <><Action className={primary} run={() => api.post(`/controladoria/events/${event.id}/triage`, { status: "reviewed" })} onDone={onDone}>Confirmar revisão</Action><button type="button" className={button} onClick={() => setDiscarding(true)}>Descartar evento</button></> : <><Action className={primary} run={() => { if (note.trim().length < 3) return Promise.reject(new Error("Informe o motivo do descarte.")); return api.post(`/controladoria/events/${event.id}/triage`, { status: "discarded", note }); }} onDone={onDone}>Confirmar descarte</Action><button type="button" className={button} onClick={() => { setDiscarding(false); setNote(""); }}>Cancelar</button></>}</div></article>;
}

function DeadlineDecision({ deadline, onDone }: { deadline: Deadline; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const decide = (decision: "approved" | "rejected") => {
    if (note.trim().length < 3) return Promise.reject(new Error("Registre a conferência antes de decidir."));
    return api.post(`/controladoria/deadlines/${deadline.id}/decision`, { decision, note });
  };
  return <article className="py-4"><p className="text-sm font-medium">{deadline.title}</p><p className="mt-1 text-sm text-zinc-300">Data sugerida: {dateText(deadline.suggested_due_at)}</p><p className="mt-2 whitespace-pre-wrap text-xs text-zinc-400">Base informada: {deadline.suggested_basis}</p><EventEvidence event={deadline.event} /><p className="mt-2 text-xs text-amber-300">Aprovar cria uma tarefa na agenda. Só prossiga depois de conferir a origem, a contagem e a data na fonte oficial.</p>{!open ? <button type="button" className={`${button} mt-3`} onClick={() => setOpen(true)}>Revisar prazo</button> : <div className="mt-3 space-y-3"><Field label="Registro da conferência"><textarea className={control} value={note} onChange={event => setNote(event.target.value)} rows={3} minLength={3} maxLength={5000} required placeholder="Ex.: Conferido no processo e na publicação oficial." /></Field><div className="flex flex-wrap gap-2"><Action className={primary} run={() => decide("approved")} onDone={onDone}>Aprovar e criar tarefa</Action><Action run={() => decide("rejected")} onDone={onDone}>Rejeitar sugestão</Action><button type="button" className={button} onClick={() => { setOpen(false); setNote(""); }}>Cancelar</button></div></div>}</article>;
}

function EventEvidence({ event }: { event: JudicialEvent }) {
  const metadata = Object.entries(event.source_metadata || {});
  return <section aria-label="Evidência do evento" className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-300"><p className="font-medium text-zinc-200">Evidência registrada</p><p className="mt-1">Consulta registrada em {dateText(event.retrieved_at)}.</p>{event.source_kind === "manual" ? <a className="mt-1 inline-flex min-h-11 items-center text-blue-300" href={event.source_url} target="_blank" rel="noreferrer">Abrir fonte informada</a> : <p className="mt-1 text-zinc-400">O resultado foi preservado no histórico; confirme sempre no tribunal antes de agir.</p>}<p className="mt-2 whitespace-pre-wrap">{event.source_content || "A fonte não forneceu conteúdo textual adicional."}</p>{metadata.length > 0 && <details className="mt-2 border-t border-zinc-800 pt-2"><summary className="min-h-11 cursor-pointer content-center text-zinc-400">Detalhes do registro</summary><dl className="grid gap-1">{metadata.map(([key, value]) => <div key={key} className="grid grid-cols-[minmax(0,10rem)_1fr] gap-2"><dt className="font-medium text-zinc-400">{key}</dt><dd className="break-words">{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl></details>}</section>;
}

function WorkflowStart({ templates, cases, onDone }: { templates: WorkflowTemplate[]; cases: Row[]; onDone: () => void }) {
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  return <form className="max-w-xl space-y-3" onSubmit={async event => { event.preventDefault(); const values = new FormData(event.currentTarget); setBusy(true); setError(""); try { await api.post("/controladoria/workflows", { case_id: values.get("case_id"), template_id: values.get("template_id") }); event.currentTarget.reset(); onDone(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }}><fieldset disabled={busy} className="space-y-3"><Field label="Processo"><select className={control} name="case_id" required defaultValue=""><option value="">Selecione…</option>{cases.map(item => <option key={item.id} value={item.id}>{item.title || "Processo sem título"}</option>)}</select></Field><Field label="Roteiro"><select className={control} name="template_id" required defaultValue=""><option value="">Selecione…</option>{templates.map(template => <option key={template.id} value={template.id}>{template.name} · versão {template.version}{template.case_type ? ` · ${template.case_type}` : ""}</option>)}</select></Field><State error={error} /><button className={primary}>{busy ? "Iniciando…" : "Iniciar roteiro"}</button></fieldset></form>;
}

function WorkflowChecklist({ run, onDone }: { run: WorkflowRun; onDone: () => void }) {
  return <article className="py-4"><p className="text-sm font-medium">{run.template_name} · versão {run.template_version}</p><p className="mt-1 text-xs text-zinc-400">Roteiro {run.status === "open" ? "em andamento" : run.status === "completed" ? "concluído" : "cancelado"}</p><ol className="mt-3 space-y-2">{run.items.map(item => <li key={item.id} className="rounded-lg border border-zinc-800 p-3"><p className="text-sm">{item.position}. {item.title} {item.is_required && <span className="text-amber-300">(obrigatório)</span>}</p>{item.instructions && <p className="mt-1 whitespace-pre-wrap text-xs text-zinc-400">{item.instructions}</p>}<p className="mt-1 text-xs text-zinc-400">{item.status === "pending" ? "Pendente" : item.status === "completed" ? "Concluído" : "Ignorado"}{item.resolution_note ? ` · ${item.resolution_note}` : ""}</p>{run.status === "open" && item.status === "pending" && <Action className={`${button} mt-2`} run={() => api.post(`/controladoria/workflows/${run.id}/items/${item.id}`, { status: "completed", resolution_note: null, expected_revision: item.revision })} onDone={onDone}>Concluir etapa</Action>}</li>)}</ol>{run.status === "open" && <Action className={`${primary} mt-3`} run={() => api.post(`/controladoria/workflows/${run.id}/complete`, { expected_revision: run.revision })} onDone={onDone}>Encerrar roteiro</Action>}</article>;
}
