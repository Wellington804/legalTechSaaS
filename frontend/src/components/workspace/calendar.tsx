"use client";

import { CalendarDays, ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api-client";
import { definitions, display, RecordForm, Records, type List, type Row } from "./records";
import { Action, Field, Page, State, button, control, dateText, download, errorText, primary, useResource } from "./shared";
import { CalendarConnections } from "./calendar-connections";

type View = "day" | "three" | "week" | "month" | "list";
const startOfDay = (date: Date) => { const value = new Date(date); value.setHours(0, 0, 0, 0); return value; };
const addDays = (date: Date, amount: number) => { const value = new Date(date); value.setDate(value.getDate() + amount); return value; };
const startOfWeek = (date: Date) => { const value = startOfDay(date); value.setDate(value.getDate() - ((value.getDay() + 6) % 7)); return value; };
const label = (date: Date, options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("pt-BR", options).format(date);

function taskStyle(task: Row) {
  if (task.status === "completed") return "border-emerald-700 bg-emerald-950/35 text-emerald-100";
  if (task.due_at && new Date(task.due_at) < new Date()) return "border-red-700 bg-red-950/35 text-red-100";
  if (task.kind === "deadline" && !task.manually_reviewed) return "border-amber-700 bg-amber-950/35 text-amber-100";
  if (task.kind === "hearing") return "border-violet-700 bg-violet-950/35 text-violet-100";
  return "border-blue-700 bg-blue-950/35 text-blue-100";
}

export function Agenda() {
  const [view, setView] = useState<View>("week"); const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [responsible, setResponsible] = useState(""); const [caseId, setCaseId] = useState(""); const [kind, setKind] = useState(""); const [selected, setSelected] = useState<Row | null>(null);
  const [feedUrl, setFeedUrl] = useState(""); const [feedError, setFeedError] = useState("");
  const feed = useResource<{ enabled: boolean; created_at: string | null }>("/integrations/calendar-feed");
  useEffect(() => { if (window.matchMedia("(max-width: 639px)").matches) setView("three"); }, []);
  const range = useMemo(() => {
    if (view === "month") { const start = startOfWeek(new Date(anchor.getFullYear(), anchor.getMonth(), 1)); return { start, end: addDays(start, 42), step: 30 }; }
    if (view === "week") { const start = startOfWeek(anchor); return { start, end: addDays(start, 7), step: 7 }; }
    if (view === "three") { const start = startOfDay(anchor); return { start, end: addDays(start, 3), step: 3 }; }
    if (view === "day") { const start = startOfDay(anchor); return { start, end: addDays(start, 1), step: 1 }; }
    const start = startOfDay(anchor); return { start, end: addDays(start, 30), step: 30 };
  }, [anchor, view]);
  const params = new URLSearchParams({ date_from: range.start.toISOString(), date_to: range.end.toISOString(), limit: "200" });
  if (responsible) params.set("assigned_user_id", responsible); if (caseId) params.set("case_id", caseId); if (kind) params.set("kind", kind);
  const tasks = useResource<List>(`/workspace/tasks?${params}`); const members = useResource<List>("/workspace/members"); const cases = useResource<List>("/workspace/cases?limit=200");
  const days = Array.from({ length: Math.round((range.end.getTime() - range.start.getTime()) / 86400000) }, (_, index) => addDays(range.start, index));
  const tasksFor = (day: Date) => tasks.data?.items.filter(task => task.due_at && new Date(task.due_at).toDateString() === day.toDateString()) || [];
  const move = (direction: number) => setAnchor(current => view === "month" ? new Date(current.getFullYear(), current.getMonth() + direction, 1) : addDays(current, range.step * direction));
  const webcalUrl = feedUrl ? feedUrl.replace(/^https?:/i, "webcal:") : "";
  const filterCount = [responsible, caseId, kind].filter(Boolean).length;
  return <Page title="Agenda e prazos" subtitle="Consulte compromissos e prazos já conferidos pelo escritório.">
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/25 p-4 shadow-sm md:p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><p className="text-sm text-zinc-400">Período exibido</p><h2 className="mt-1 text-xl font-semibold capitalize">{label(anchor, { month: "long", year: "numeric" })}</h2></div><div className="flex flex-wrap gap-2"><button type="button" className={button} onClick={() => setAnchor(startOfDay(new Date()))}>Hoje</button><button type="button" className={button} onClick={() => move(-1)} aria-label="Período anterior"><ChevronLeft size={17} /></button><button type="button" className={button} onClick={() => move(1)} aria-label="Próximo período"><ChevronRight size={17} /></button></div></div>
      <div className="mt-4 flex max-w-full gap-1 overflow-x-auto rounded-lg bg-zinc-900 p-1">{(["day", "three", "week", "month", "list"] as View[]).map(item => <button type="button" key={item} aria-pressed={view === item} className={`${view === item ? "bg-blue-600 text-white" : "text-zinc-300 hover:bg-zinc-800"} min-h-10 shrink-0 rounded-md px-3 text-sm ${item === "three" ? "sm:hidden" : item === "month" ? "max-sm:hidden" : ""}`} onClick={() => setView(item)}>{({ day: "Dia", three: "3 dias", week: "Semana", month: "Mês", list: "Lista" } as const)[item]}</button>)}</div>
      <details className="mt-4 border-y border-zinc-800 py-1"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-blue-300">Filtros{filterCount ? ` · ${filterCount} em uso` : ""}</summary><div className="grid gap-3 border-t border-zinc-800 py-4 sm:grid-cols-3"><Field label="Advogado"><select className={control} value={responsible} onChange={event => setResponsible(event.target.value)}><option value="">Todos</option>{members.data?.items.map(item => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></Field><Field label="Processo"><select className={control} value={caseId} onChange={event => setCaseId(event.target.value)}><option value="">Todos</option>{cases.data?.items.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></Field><Field label="Tipo"><select className={control} value={kind} onChange={event => setKind(event.target.value)}><option value="">Todos</option><option value="task">Compromisso</option><option value="deadline">Prazo</option><option value="hearing">Audiência</option></select></Field>{filterCount > 0 && <button type="button" className={button} onClick={() => { setResponsible(""); setCaseId(""); setKind(""); }}>Limpar filtros</button>}</div></details>
      <State loading={tasks.loading} error={tasks.error || members.error || cases.error} />
      {!tasks.loading && view === "list" && <div className="mt-4 space-y-2">{tasks.data?.items.map(task => <button type="button" key={task.id} className={`w-full rounded-lg border p-3 text-left ${taskStyle(task)}`} onClick={() => setSelected(task)}><span className="font-medium">{task.title}</span><span className="mt-1 block text-xs">{dateText(task.due_at)} · {display(task.kind)}</span></button>)}{!tasks.data?.items.length && <p className="text-sm text-zinc-400">Nenhum compromisso neste período.</p>}</div>}
      {!tasks.loading && view !== "list" && <div className={`mt-4 grid gap-2 ${view === "month" ? "grid-cols-2 lg:grid-cols-7" : view === "week" ? "grid-cols-1 md:grid-cols-7" : "grid-cols-1 sm:grid-cols-3"}`}>{days.map(day => <article key={day.toISOString()} className={`min-h-32 rounded-lg border p-2 ${day.toDateString() === new Date().toDateString() ? "border-blue-600" : "border-zinc-800"}`}><h3 className="mb-2 text-xs font-semibold capitalize text-zinc-400">{label(day, { weekday: "short", day: "2-digit", month: "short" })}</h3><div className="space-y-1">{tasksFor(day).map(task => <button type="button" key={task.id} onClick={() => setSelected(task)} className={`w-full rounded-md border px-2 py-2 text-left text-xs ${taskStyle(task)}`}><span className="block truncate font-medium">{task.title}</span>{task.due_at && <span>{label(new Date(task.due_at), { hour: "2-digit", minute: "2-digit" })}</span>}</button>)}</div></article>)}</div>}
    </section>
    {selected && <div role="dialog" aria-modal="true" aria-labelledby="agenda-edit-title" className="fixed inset-0 z-50 flex items-end bg-black/70 sm:items-center sm:justify-center sm:p-4"><div className="max-h-[92dvh] w-full overflow-y-auto rounded-t-2xl border border-zinc-700 bg-zinc-950 p-4 sm:max-w-3xl sm:rounded-2xl"><div className="mb-4 flex items-center justify-between"><div><h2 id="agenda-edit-title" className="font-semibold">Editar compromisso</h2><p className="text-sm text-zinc-400">Confira a data antes de salvar.</p></div><button className={button} onClick={() => setSelected(null)} aria-label="Fechar"><X size={18} /></button></div><RecordForm definition={definitions.tasks} record={selected} onDone={() => { setSelected(null); tasks.reload(); }} /></div></div>}
    <section className="space-y-4"><div className="flex items-center gap-2"><CalendarDays aria-hidden="true" size={19} /><h2 className="text-lg font-semibold">Criar ou editar compromissos</h2></div><Records kind="tasks" embedded /></section>
    <details className="rounded-xl border border-zinc-800 bg-zinc-900/25 p-4 shadow-sm md:p-5"><summary className="min-h-11 cursor-pointer content-center text-base font-semibold text-zinc-100">Usar esta agenda em outros calendários</summary><div className="mt-4 space-y-4 border-t border-zinc-800 pt-4">
      <p className="text-sm text-zinc-300">Conecte Google Agenda ou Outlook para editar nos dois lados. No Calendário Apple, use a assinatura somente leitura.</p>
      <button type="button" className={button} onClick={() => download("/integrations/calendar.ics", "lexflow-agenda.ics")}><Download aria-hidden="true" size={16} /> Exportar agenda</button>
      <CalendarConnections tasks={tasks.data?.items || []} />
      <details className="border-t border-zinc-800 pt-2"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-blue-300">Assinatura somente leitura</summary><div className="mt-3 space-y-3">
        <p className="text-sm text-zinc-300">Crie um endereço privado para consultar os compromissos no calendário do celular. Quem tiver esse endereço poderá ver sua agenda.</p>
        <State loading={feed.loading} error={feed.error || feedError} />
        {feed.data?.enabled && !feedUrl && <p className="text-sm text-emerald-300">Assinatura ativa desde {dateText(feed.data.created_at)}. Por segurança, o endereço não é exibido novamente.</p>}
        {feedUrl && <div className="space-y-3 rounded-lg border border-blue-800 bg-blue-950/20 p-3"><Field label="Copie este endereço agora"><input className={control} readOnly value={feedUrl} onFocus={event => event.target.select()} /></Field><div className="flex flex-wrap gap-2"><button className={primary} type="button" onClick={() => navigator.clipboard.writeText(feedUrl)}>Copiar endereço</button><a className={button} href={webcalUrl}>Assinar no Calendário Apple</a></div><ol className="list-decimal space-y-1 pl-5 text-xs text-blue-100"><li>No iPhone, iPad ou Mac, toque em “Assinar no Calendário Apple” e confirme.</li><li>No Google Agenda, abra pelo computador e use “Outros calendários → Do URL”.</li><li>No Outlook, escolha adicionar calendário e assinar pela Web.</li></ol></div>}
        <div className="flex flex-wrap gap-2"><Action className={primary} run={async () => { setFeedError(""); try { const result = await api.post<{ feed_url: string }>("/integrations/calendar-feed", {}); setFeedUrl(result.feed_url); feed.reload(); } catch (reason) { setFeedError(errorText(reason)); } }}>{feed.data?.enabled ? "Gerar novo endereço" : "Criar endereço privado"}</Action>{feed.data?.enabled && <Action run={() => api.delete("/integrations/calendar-feed")} onDone={() => { setFeedUrl(""); feed.reload(); }}>Desativar assinatura</Action>}</div>
        <p className="text-xs text-zinc-500">O endereço é somente leitura e a atualização pode levar algumas horas.</p>
      </div></details>
    </div></details>
  </Page>;
}
