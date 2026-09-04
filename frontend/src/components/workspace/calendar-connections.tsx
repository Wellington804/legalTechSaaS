"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Action, State, button, errorText, primary, useResource } from "./shared";

type Provider = "google" | "microsoft";
type Connection = {
  id: string;
  provider: Provider;
  provider_account_label: string | null;
  selected_calendar_label: string | null;
  last_sync_at: string | null;
  last_error: string | null;
  status: "active" | "reauthorization_required" | "revoked";
  revision: number;
};
type ProviderCalendar = { id: string; name: string; primary: boolean; can_write: boolean };
type TaskChoice = { id: string; title?: string; due_at?: string | null };
type TaskLink = { task_id: string; status: "active" | "tombstoned" | "conflict" };
type SyncConflict = { id: string; task_id: string; reason: "both_changed" | "remote_deleted"; created_at: string };

const providerName = (provider: Provider) => provider === "google" ? "Google Agenda" : "Microsoft Outlook";

function ConnectionCard({ provider, connection, tasks }: { provider: Provider; connection?: Connection; tasks: TaskChoice[] }) {
  const calendars = useResource<{ items: ProviderCalendar[] }>(connection?.status === "active" ? `/integrations/calendar-oauth/${provider}/calendars` : null);
  const links = useResource<{ items: TaskLink[] }>(connection?.status === "active" ? `/integrations/calendar-oauth/${provider}/tasks` : null);
  const [calendarId, setCalendarId] = useState("");
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [error, setError] = useState("");
  const connect = async () => {
    setError("");
    try {
      const result = await api.post<{ authorization_url: string }>(`/integrations/calendar-oauth/${provider}/connect`, { redirect_path: "/dashboard/tasks" });
      window.location.assign(result.authorization_url);
    } catch (reason) { setError(errorText(reason)); }
  };
  if (!connection) return <article className="rounded-lg border border-zinc-800 p-3"><h3 className="font-medium">{providerName(provider)}</h3><p className="mt-1 text-sm text-zinc-400">Autorize a leitura e escrita da agenda escolhida. O LexFlow descarta eventos sem vínculo e nunca recebe a senha da conta.</p><button className={`${primary} mt-3`} type="button" onClick={connect}>Conectar {providerName(provider)}</button><State error={error} /></article>;
  return <article className="space-y-3 rounded-lg border border-zinc-800 p-3">
    <div><h3 className="font-medium">{providerName(provider)}</h3><p className="text-sm text-zinc-400">{connection.provider_account_label || "Conta autorizada"} · {connection.status === "active" ? "ativa" : "requer nova autorização"}</p></div>
    <State loading={calendars.loading} error={calendars.error || connection.last_error || error} />
    {connection.status === "reauthorization_required" && <button className={primary} type="button" onClick={connect}>Reconectar</button>}
    {connection.status === "active" && <>
      <label className="grid gap-1 text-sm"><span>Agenda de destino</span><select className="min-h-11 rounded-lg border border-zinc-700 bg-zinc-950 px-3" value={calendarId} onChange={event => setCalendarId(event.target.value)}><option value="">{connection.selected_calendar_label || "Selecione…"}</option>{calendars.data?.items.filter(item => item.can_write).map(item => <option key={item.id} value={item.id}>{item.name}{item.primary ? " (principal)" : ""}</option>)}</select></label>
      <Action className={button} run={async () => { if (!calendarId) return; await api.put(`/integrations/calendar-oauth/${provider}/calendar`, { calendar_id: calendarId, expected_revision: connection.revision }); window.location.reload(); }}>Usar esta agenda</Action>
      {connection.selected_calendar_label && <details><summary className="min-h-11 cursor-pointer content-center text-sm font-medium">Escolher compromissos do LexFlow</summary><div className="mt-2 max-h-52 space-y-1 overflow-y-auto">{tasks.filter(task => task.due_at && !links.data?.items.some(link => link.task_id === task.id)).map(task => <label key={task.id} className="flex min-h-10 items-center gap-2 rounded px-2 hover:bg-zinc-900"><input type="checkbox" checked={selectedTasks.includes(task.id)} onChange={event => setSelectedTasks(current => event.target.checked ? [...current, task.id] : current.filter(id => id !== task.id))} /><span className="text-sm">{task.title || "Compromisso"}</span></label>)}</div><Action className={`${primary} mt-2`} run={async () => { if (!selectedTasks.length) return; await api.post(`/integrations/calendar-oauth/${provider}/tasks`, { task_ids: selectedTasks }); }} onDone={() => { setSelectedTasks([]); links.reload(); }}>Sincronizar selecionados</Action>{Boolean(links.data?.items.length) && <div className="mt-3 space-y-1 border-t border-zinc-800 pt-2"><p className="text-xs font-medium text-zinc-400">Compromissos sincronizados</p>{links.data?.items.map(link => <div key={link.task_id} className="flex min-h-10 items-center justify-between gap-2"><span className="truncate text-sm">{tasks.find(task => task.id === link.task_id)?.title || "Compromisso"} · {link.status === "conflict" ? "revisão pendente" : "ativo"}</span><Action className={button} run={() => api.delete(`/integrations/calendar-oauth/${provider}/tasks/${link.task_id}`)} onDone={links.reload}>Remover</Action></div>)}</div>}</details>}
      <div className="flex flex-wrap gap-2"><Action className={button} run={() => api.post(`/integrations/calendar-oauth/${provider}/sync`, {})}>Reconciliar agora</Action><Action className={button} run={() => api.delete(`/integrations/calendar-oauth/${provider}`)} onDone={() => window.location.reload()}>Desconectar</Action></div>
    </>}
  </article>;
}

export function CalendarConnections({ tasks }: { tasks: TaskChoice[] }) {
  const connections = useResource<{ items: Connection[] }>("/integrations/calendar-oauth/status");
  const conflicts = useResource<{ items: SyncConflict[] }>("/integrations/calendar-oauth/conflicts/pending");
  return <section className="space-y-3 border-t border-zinc-800 pt-4"><div><h3 className="font-medium">Sincronização bidirecional</h3><p className="mt-1 text-sm text-zinc-400">Só os compromissos escolhidos são enviados. Edições simultâneas viram conflito para revisão; exclusões externas nunca apagam prazo jurídico automaticamente.</p></div><State loading={connections.loading} error={connections.error} /><div className="grid gap-3 lg:grid-cols-2">{(["google", "microsoft"] as Provider[]).map(provider => <ConnectionCard key={provider} provider={provider} connection={connections.data?.items.find(item => item.provider === provider)} tasks={tasks} />)}</div>{Boolean(conflicts.data?.items.length) && <div className="space-y-2 rounded-lg border border-amber-800 bg-amber-950/15 p-3"><h3 className="font-medium text-amber-200">Revisão de alterações externas</h3>{conflicts.data?.items.map(conflict => <article key={conflict.id} className="border-t border-amber-900/60 pt-2"><p className="text-sm">{tasks.find(task => task.id === conflict.task_id)?.title || "Compromisso"}: {conflict.reason === "remote_deleted" ? "foi excluído na agenda externa" : "mudou no LexFlow e na agenda externa"}.</p><div className="mt-2 flex flex-wrap gap-2"><Action className={primary} run={() => api.post(`/integrations/calendar-oauth/conflicts/${conflict.id}/resolve`, { resolution: "keep_local" })} onDone={conflicts.reload}>Manter LexFlow</Action><Action className={button} run={() => api.post(`/integrations/calendar-oauth/conflicts/${conflict.id}/resolve`, { resolution: "accept_remote" })} onDone={conflicts.reload}>Aceitar agenda externa</Action></div></article>)}</div>}<p className="text-xs text-zinc-500">No iPhone ou iPad, mantenha a mesma conta Google ou Microsoft adicionada em Ajustes → Apps → Calendário → Contas. Não é necessário informar senha do iCloud nem configurar CalDAV no LexFlow.</p></section>;
}
