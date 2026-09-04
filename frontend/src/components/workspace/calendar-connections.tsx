"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import { Action, State, button, dateText, errorText, primary, useResource } from "./shared";

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
type TaskLink = { task_id: string; status: "active" | "tombstoned" | "conflict" | "delete_pending" };
type ConflictSide = {
  hash: string;
  title: string | null;
  starts_at: string | null;
  location: string | null;
  notes: string | null;
  deleted: boolean;
  revision: number | null;
};
type SyncConflict = {
  id: string;
  task_id: string;
  reason: "both_changed" | "remote_deleted";
  local_revision: number;
  remote_hash: string;
  local: ConflictSide;
  remote: ConflictSide;
  created_at: string;
};

const providerName = (provider: Provider) => provider === "google" ? "Google Agenda" : "Microsoft Outlook";

function ConflictSnapshot({ title, side }: { title: string; side: ConflictSide }) {
  return <section className="min-w-0 rounded-lg border border-amber-900/60 bg-zinc-950/40 p-3" aria-label={title}>
    <h4 className="text-sm font-semibold text-zinc-200">{title}</h4>
    {side.deleted ? <p className="mt-2 text-sm text-amber-200">Evento excluído</p> : <dl className="mt-2 grid gap-2 text-sm">
      <div><dt className="text-xs text-zinc-500">Título</dt><dd className="break-words text-zinc-200">{side.title || "—"}</dd></div>
      <div><dt className="text-xs text-zinc-500">Data e hora</dt><dd className="text-zinc-200">{dateText(side.starts_at)}</dd></div>
      <div><dt className="text-xs text-zinc-500">Local</dt><dd className="break-words text-zinc-200">{side.location || "—"}</dd></div>
      <div><dt className="text-xs text-zinc-500">Observações</dt><dd className="max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-zinc-200">{side.notes || "—"}</dd></div>
    </dl>}
  </section>;
}

function ConflictActions({ conflict, onReload }: { conflict: SyncConflict; onReload: () => void }) {
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState("");
  const snapshotVersion = `${conflict.remote_hash}:${conflict.local.revision ?? conflict.local_revision}`;
  useEffect(() => { setStale(false); setError(""); }, [snapshotVersion]);
  const resolve = async (resolution: "accept_remote" | "keep_local") => {
    setBusy(true); setError("");
    try {
      await api.post(`/integrations/calendar-oauth/conflicts/${conflict.id}/resolve`, {
        resolution,
        expected_local_revision: conflict.local.revision ?? conflict.local_revision,
        expected_remote_hash: conflict.remote_hash,
      });
      onReload();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setStale(true);
        setError("A comparação mudou. Atualizando as duas versões antes de liberar uma nova decisão…");
        onReload();
      } else {
        setError(errorText(reason));
      }
    } finally { setBusy(false); }
  };
  return <div className="space-y-2"><div className="flex flex-wrap gap-2"><button type="button" disabled={busy || stale} className={primary} onClick={() => resolve("keep_local")}>{busy ? "Revalidando…" : "Manter LexFlow"}</button><button type="button" disabled={busy || stale} className={button} onClick={() => resolve("accept_remote")}>{busy ? "Revalidando…" : "Aceitar agenda externa"}</button></div>{error && <p role={stale ? "status" : "alert"} className={stale ? "text-xs text-amber-300" : "text-xs text-red-300"}>{error}</p>}</div>;
}

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
      {connection.selected_calendar_label && <details><summary className="min-h-11 cursor-pointer content-center text-sm font-medium">Escolher compromissos do LexFlow</summary><div className="mt-2 max-h-52 space-y-1 overflow-y-auto">{tasks.filter(task => task.due_at && !links.data?.items.some(link => link.task_id === task.id && link.status !== "tombstoned")).map(task => { const reactivating = links.data?.items.some(link => link.task_id === task.id && link.status === "tombstoned"); return <label key={task.id} className="flex min-h-10 items-center gap-2 rounded px-2 hover:bg-zinc-900"><input type="checkbox" checked={selectedTasks.includes(task.id)} onChange={event => setSelectedTasks(current => event.target.checked ? [...current, task.id] : current.filter(id => id !== task.id))} /><span className="text-sm">{task.title || "Compromisso"}{reactivating ? " · removido, selecione para reativar" : ""}</span></label>; })}</div><Action className={`${primary} mt-2`} run={async () => { if (!selectedTasks.length) return; await api.post(`/integrations/calendar-oauth/${provider}/tasks`, { task_ids: selectedTasks }); }} onDone={() => { setSelectedTasks([]); links.reload(); }}>Sincronizar selecionados</Action>{Boolean(links.data?.items.length) && <div className="mt-3 space-y-1 border-t border-zinc-800 pt-2"><p className="text-xs font-medium text-zinc-400">Compromissos vinculados</p>{links.data?.items.map(link => <div key={link.task_id} className="flex min-h-10 items-center justify-between gap-2"><span className="truncate text-sm">{tasks.find(task => task.id === link.task_id)?.title || "Compromisso"} · {link.status === "conflict" ? "revisão pendente" : link.status === "delete_pending" ? "remoção pendente" : link.status === "tombstoned" ? "removido" : "ativo"}</span>{link.status === "tombstoned" ? <Action className={button} run={() => api.post(`/integrations/calendar-oauth/${provider}/tasks`, { task_ids: [link.task_id] })} onDone={links.reload}>Reativar</Action> : link.status !== "delete_pending" && <Action className={button} run={() => api.delete(`/integrations/calendar-oauth/${provider}/tasks/${link.task_id}`)} onDone={links.reload}>Remover</Action>}</div>)}</div>}</details>}
      <div className="flex flex-wrap gap-2"><Action className={button} run={() => api.post(`/integrations/calendar-oauth/${provider}/sync`, {})}>Atualizar agora</Action><Action className={button} run={() => api.delete(`/integrations/calendar-oauth/${provider}`)} onDone={() => window.location.reload()}>Desconectar</Action></div>
    </>}
  </article>;
}

export function CalendarConnections({ tasks }: { tasks: TaskChoice[] }) {
  const connections = useResource<{ items: Connection[] }>("/integrations/calendar-oauth/status");
  const conflicts = useResource<{ items: SyncConflict[] }>("/integrations/calendar-oauth/conflicts/pending");
  return <section className="space-y-3 border-t border-zinc-800 pt-4">
    <div><h3 className="font-medium">Google Agenda e Microsoft Outlook</h3><p className="mt-1 text-sm text-zinc-400">Só os compromissos escolhidos são enviados. Se o mesmo item mudar nos dois lados, você decide qual versão manter. Uma exclusão externa nunca apaga um prazo jurídico automaticamente.</p></div>
    <aside className="rounded-lg border border-zinc-800 bg-zinc-950/30 p-3 text-xs leading-relaxed text-zinc-400"><span className="font-medium text-zinc-300">Dados enviados ao provedor:</span> título, data e hora, local, observações e os dados necessários para manter o vínculo. O LexFlow consulta apenas a agenda escolhida.</aside>
    <State loading={connections.loading} error={connections.error} />
    <div className="grid gap-3 lg:grid-cols-2">{(["google", "microsoft"] as Provider[]).map(provider => <ConnectionCard key={provider} provider={provider} connection={connections.data?.items.find(item => item.provider === provider)} tasks={tasks} />)}</div>
    {Boolean(conflicts.data?.items.length) && <div className="space-y-3 rounded-lg border border-amber-800 bg-amber-950/15 p-3">
      <h3 className="font-medium text-amber-200">Revisão de alterações externas</h3>
      {conflicts.data?.items.map(conflict => <article key={conflict.id} className="space-y-3 border-t border-amber-900/60 pt-3"><p className="text-sm text-amber-100">{tasks.find(task => task.id === conflict.task_id)?.title || "Compromisso"}: {conflict.reason === "remote_deleted" ? "foi excluído na agenda externa" : "mudou no LexFlow e na agenda externa"}. Compare os dois lados antes de decidir.</p><div className="grid gap-2 md:grid-cols-2"><ConflictSnapshot title="Versão no LexFlow" side={conflict.local} /><ConflictSnapshot title="Versão na agenda externa" side={conflict.remote} /></div><ConflictActions conflict={conflict} onReload={conflicts.reload} /></article>)}
    </div>}
    <p className="text-xs text-zinc-500">No iPhone ou iPad, mantenha a mesma conta Google ou Microsoft adicionada em Ajustes → Apps → Calendário → Contas. Não é necessário informar senha do iCloud.</p>
  </section>;
}
