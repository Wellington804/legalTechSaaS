"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { List, Row } from "./records";
import { Action, DraftNotice, Field, Panel, State, button, control, dateText, errorText, primary, useAccountDraft, useDraftGuard, useResource } from "./shared";
import { FileCenter } from "./file-center";

type Reminder = { id: string; task_id: string; task_title: string; case_id: string | null; remind_at: string; status: string; push_status: string; acknowledged_at: string | null };
const pushLabels: Record<string, string> = { not_requested: "Sem push solicitado", pending: "Push na fila", accepted: "Aceito pelo provedor; recebimento não confirmado", failed: "Falha no push", unknown: "Recebimento do push desconhecido", unavailable: "Push indisponível" };
export function RoutineAttention() {
  const resource = useResource<{ cases_without_next_action: { id: string; title: string }[]; reminders: Reminder[]; limit: number }>("/routines/attention");
  return <Panel title="O que precisa de atenção">
    <State loading={resource.loading} error={resource.error} />
    <p className="text-xs text-zinc-400">Confira a agenda hoje. Lembretes usam datas revisadas por você e não calculam prazos judiciais. <button type="button" className="min-h-11 underline text-blue-300" onClick={resource.reload}>Atualizar</button></p>
    <h3 className="text-sm font-medium">Lembretes vencidos</h3>
    {resource.data?.reminders.map(item => <article key={item.id} className="space-y-2 border-b border-zinc-800 pb-3"><p className="text-sm">{item.task_title} · {dateText(item.remind_at)}</p><p className="text-xs text-zinc-400">Vencido · {pushLabels[item.push_status] || item.push_status}</p><div className="flex flex-wrap gap-2">{item.case_id && <Link className={button} href={`/dashboard/cases/${item.case_id}`}>Consultar caso</Link>}{!item.acknowledged_at && <Action run={() => api.post(`/routines/reminders/${item.id}/acknowledge`, {})} onDone={resource.reload}>Confirmar consulta</Action>}</div></article>)}
    {resource.data && !resource.data.reminders.length && <p className="text-xs text-zinc-400">Nenhum lembrete vencido para conferir.</p>}
    <h3 className="text-sm font-medium">Próxima ação por caso</h3>
    {resource.data?.cases_without_next_action.map(row => <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2"><p className="text-sm min-w-0 flex-1">{row.title}</p><Link href={`/dashboard/cases/${row.id}`} className={button}>Definir próxima ação</Link></div>)}
    {resource.data && !resource.data.cases_without_next_action.length && <p className="text-xs text-zinc-400">Nenhum caso sem ação na consulta atual.</p>}
    {resource.data && (resource.data.reminders.length >= resource.data.limit || resource.data.cases_without_next_action.length >= resource.data.limit) && <p className="text-xs text-amber-300">Lista limitada. Consulte também a agenda e os casos.</p>}
  </Panel>;
}

export function TaskReminder({ task, onClose }: { task: Row; onClose: () => void }) {
  const resource = useResource<{ item: Reminder | null }>(`/routines/tasks/${task.id}/reminder`);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  const allowed = task.due_at && task.manually_reviewed && ["pending", "in_progress"].includes(task.status);
  return <Panel title={`Meu lembrete: ${task.title}`}>
    <State loading={resource.loading} error={resource.error || error} />
    <p className="text-xs text-zinc-400">Somente para você. Fica registrado na Central mesmo sem push. Alterar a data ou situação da tarefa cancela o lembrete anterior; configure-o novamente após salvar.</p>
    {resource.data?.item && <div className="space-y-2"><p className="text-sm">{dateText(resource.data.item.remind_at)} · {resource.data.item.status === "scheduled" ? "Agendado" : resource.data.item.status === "due" ? "Horário atingido" : "Cancelado"}</p><p className="text-xs text-zinc-400">{pushLabels[resource.data.item.push_status] || resource.data.item.push_status}</p><Action run={() => api.delete(`/routines/tasks/${task.id}/reminder`)} onDone={resource.reload}>Cancelar lembrete</Action></div>}
    {!allowed ? <p className="text-sm text-amber-300">Salve uma tarefa ativa com data e horário conferidos antes de configurar o lembrete.</p> : <form className="space-y-3" onSubmit={async e => {
      e.preventDefault(); const value = String(new FormData(e.currentTarget).get("remind_at")); setBusy(true); setError(""); setNotice("");
      try { await api.put(`/routines/tasks/${task.id}/reminder`, { remind_at: new Date(value).toISOString(), expected_revision: task.revision }); resource.reload(); setNotice("Lembrete salvo para você. O push depende da ativação deste dispositivo e do provedor."); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
    }}><Field label="Lembrar em (horário local)"><input name="remind_at" type="datetime-local" className={control} required disabled={busy} /></Field><p className="text-xs text-zinc-400">Escolha um horário futuro, até a data da tarefa: {dateText(task.due_at)}.</p><button className={primary} disabled={busy}>{busy ? "Salvando…" : "Salvar meu lembrete"}</button></form>}
    {notice && <p role="status" className="text-sm text-green-300">{notice}</p>}<button className={button} type="button" onClick={onClose}>Fechar lembrete</button>
  </Panel>;
}

export function CaseRoutines({ caseId }: { caseId: string }) {
  const presets = useResource<{ items: { key: string; title: string; items: string[] }[] }>("/routines/checklists");
  const outcomes = useResource<List>(`/routines/cases/${caseId}/outcomes`);
  const tasks = useResource<List>(`/workspace/tasks?case_id=${caseId}&open_only=true`);
  const [preset, setPreset] = useState(""); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const checklistId = useRef<string | null>(null); const [outcomeId] = useAccountDraft<{ current: string | null }>(`outcome:${caseId}:request`, { current: null }); const draft = useDraftGuard(`outcome:${caseId}`);
  const selected = presets.data?.items.find(item => item.key === preset);
  const pending = tasks.data?.items.filter(task => ["pending", "in_progress"].includes(task.status)).sort((a, b) => String(a.due_at || "z").localeCompare(String(b.due_at || "z"))) || [];
  return <div className="space-y-4">
    <section aria-labelledby="diligence-mode" className="rounded-2xl border border-blue-800 bg-blue-950/20 p-4 md:p-5"><h2 id="diligence-mode" className="text-lg font-semibold text-blue-100">Modo diligência</h2><p className="mt-1 text-sm text-zinc-300">Consulta rápida para uso no celular. O que você registrar fica vinculado a este processo.</p>{pending[0] && <div className="mt-4 rounded-xl bg-zinc-950/50 p-3"><p className="text-xs text-zinc-400">Próxima providência</p><p className="mt-1 text-sm font-medium">{pending[0].title}</p><p className="mt-1 text-xs text-zinc-400">{dateText(pending[0].due_at)} · {pending[0].location || "Local não informado"}</p></div>}<div className="mt-4 flex flex-wrap gap-2"><button type="button" className={primary} onClick={() => document.getElementById("diligence-outcome")?.scrollIntoView({ behavior: "smooth" })}>Registrar resultado</button><button type="button" className={button} onClick={() => document.getElementById("diligence-files")?.scrollIntoView({ behavior: "smooth" })}>Anexar foto ou arquivo</button>{pending[0]?.location && <a className={button} target="_blank" rel="noreferrer" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(String(pending[0].location))}`}>Abrir local no mapa</a>}</div></section>
    <Panel title="Próxima ação no caso"><State loading={tasks.loading} error={tasks.error} empty={!pending.length} />
      {pending[0] && <article className="space-y-1"><p className="text-sm font-medium">{pending[0].title} · {dateText(pending[0].due_at)}</p><p className="text-xs text-zinc-400">{pending[0].location || "Local não informado"} · {pending[0].contact || "Contato não informado"}{!pending[0].manually_reviewed && " · Data pendente de conferência"}</p>{pending[0].notes && <p className="text-sm whitespace-pre-wrap">{pending[0].notes}</p>}</article>}
      {pending.length > 1 && <details><summary className="min-h-11 content-center cursor-pointer text-sm text-zinc-400">Ver mais {pending.length - 1} compromisso{pending.length > 2 ? "s" : ""}</summary><div className="divide-y divide-zinc-800">{pending.slice(1).map(task => <article key={task.id} className="space-y-1 py-3"><p className="text-sm">{task.title} · {dateText(task.due_at)}</p><p className="text-xs text-zinc-400">{task.location || "Local não informado"} · {task.contact || "Contato não informado"}{!task.manually_reviewed && " · Data pendente de conferência"}</p></article>)}</div></details>}
      <p className="text-xs text-zinc-400">Confira a data na Agenda antes de concluir ou criar um lembrete.</p>
    </Panel>
    <Panel title="Checklist de atendimento">
      <p className="text-xs text-zinc-400">Cria tarefas reais, sem datas inventadas. Revise a pertinência e os prazos na agenda; não é um roteiro jurídico obrigatório.</p><State error={presets.error || error} />
      <Field label="Checklist operacional"><select className={control} value={preset} onChange={e => { setPreset(e.target.value); checklistId.current = null; }}><option value="">Selecione…</option>{presets.data?.items.map(item => <option key={item.key} value={item.key}>{item.title}</option>)}</select></Field>
      {selected && <><ul className="space-y-2 list-disc pl-5 text-sm">{selected.items.map(item => <li key={item}>{item}</li>)}</ul><Action run={async () => { checklistId.current ||= crypto.randomUUID(); const result = await api.post<{ task_ids: string[]; created: boolean }>(`/routines/cases/${caseId}/checklists`, { key: preset, request_id: checklistId.current }); setNotice(`${result.task_ids.length} tarefas vinculadas ao caso. Confira e defina as datas na Agenda.`); tasks.reload(); }}>Adicionar checklist ao caso</Action></>}
      {notice && <p role="status" className="text-sm text-green-300">{notice}</p>}
    </Panel>
    <div id="diligence-outcome" className="scroll-mt-20"><Panel title="Registrar resultado da diligência">
      <p className="text-xs text-zinc-400">Nota privada vinculada ao caso, com versão preservada. Não é enviada automaticamente ao cliente nem à IA.</p>
      <form ref={draft.formRef} onChange={() => { draft.setDirty(true); outcomeId.current = null; }} className="space-y-3" onSubmit={async e => {
        e.preventDefault(); const form = e.currentTarget; const values = new FormData(form); setBusy(true); setError(""); outcomeId.current ||= crypto.randomUUID();
        try { await api.post(`/routines/cases/${caseId}/outcomes`, { request_id: outcomeId.current, title: values.get("title"), content_text: values.get("content_text") }); form.reset(); outcomeId.current = null; draft.setDirty(false); outcomes.reload(); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
      }}><fieldset disabled={busy} className="min-w-0 space-y-3"><Field label="Título do resultado"><input name="title" required minLength={2} maxLength={200} className={control} /></Field><Field label="Resultado e próxima providência"><textarea name="content_text" required maxLength={5000} rows={5} className={control} /></Field><DraftNotice dirty={draft.dirty} /><State error={error} /><button className={primary}>{busy ? "Salvando…" : "Salvar resultado no caso"}</button></fieldset></form>
    </Panel></div>
    <div id="diligence-files" className="scroll-mt-20"><Panel title="Comprovantes e arquivos da diligência"><p className="text-xs text-zinc-400">Fotografe ou anexe documentos. O envio passa pela mesma verificação de segurança da Central de Arquivos.</p><FileCenter caseId={caseId} embedded captureOnMobile /></Panel></div>
    <Panel title="Resultados registrados" collapsibleOnMobile><State loading={outcomes.loading} error={outcomes.error} empty={!outcomes.data?.items.length} />{outcomes.data?.items.map(item => <article key={item.id} className="space-y-2 border-b border-zinc-800 pb-3"><p className="text-sm font-medium">{item.title}</p><p className="text-xs text-zinc-400">{dateText(item.created_at)}</p><p className="text-sm whitespace-pre-wrap">{item.content_text}</p></article>)}</Panel>
  </div>;
}
