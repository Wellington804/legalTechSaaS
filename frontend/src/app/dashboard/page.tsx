"use client";

import {
  BellRing,
  Bot,
  BriefcaseBusiness,
  CalendarCheck,
  CheckCircle2,
  FilePlus2,
  FileWarning,
  MessageSquareWarning,
  UserPlus,
  WalletCards,
} from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { OPEN_AI_EVENT } from "@/components/ai-assistant";
import { useUser } from "@/context/user-context";
import { api, ApiError } from "@/lib/api-client";
import {
  Field,
  Page,
  Panel,
  State,
  button,
  control,
  dateText,
  errorText,
  primary,
  useResource,
} from "@/components/workspace/shared";
import { display, type List, type Row } from "@/components/workspace/records";
import { RoutineAttention } from "@/components/workspace/routines";

type DailySource = "task" | "publication" | "judicial_event" | "communication" | "case_without_action";
type DailySeverity = "critical" | "today" | "attention" | "planning" | "upcoming";
type QuickEditor = { mode: "reschedule" | "create"; item: DailyItem; requestId: string };

interface DailyItem {
  id: string;
  source: DailySource;
  severity: DailySeverity;
  title: string;
  case_id: string | null;
  case_title: string | null;
  task_kind: string | null;
  status: string;
  relevant_at: string | null;
  revision: number | null;
  manually_reviewed: boolean | null;
  detail: string | null;
  href: string;
  actions: string[];
}

interface DailySummary {
  generated_at: string;
  timezone: string;
  cases: { total: number; active: number; waiting_action: number; restricted: number };
  tasks: { due_today: number; overdue: number; upcoming: number; hearings_upcoming: number };
  priorities: DailyItem[];
  attention: { pending_judicial_movements: number; communication_failures: number; document_failures: number; financial_drafts: number | null };
}

const caseLabels: Record<string, string> = { open: "Abertos", paused: "Suspensos", closed: "Encerrados", archived: "Arquivados" };
const severityStyle: Record<DailySeverity, string> = {
  critical: "border-red-700 bg-red-950/30",
  today: "border-amber-700 bg-amber-950/25",
  attention: "border-violet-700 bg-violet-950/20",
  planning: "border-blue-800 bg-blue-950/20",
  upcoming: "border-zinc-700 bg-zinc-900/40",
};
const severityLabel: Record<DailySeverity, string> = {
  critical: "Vencido",
  today: "Hoje",
  attention: "Atenção",
  planning: "Planejar",
  upcoming: "Próximo",
};

function mutationError(reason: unknown) {
  if (!(reason instanceof ApiError)) return errorText(reason);
  if (reason.status === 401) return "Sua sessão expirou. Entre novamente; os dados digitados permanecem nesta tela.";
  if (reason.status === 403) return "Você não tem permissão para alterar este registro.";
  if (reason.status === 409) return "Este registro mudou em outra sessão. A versão atual será carregada; confira antes de tentar novamente.";
  if (reason.status === 422) return reason.message;
  return reason.status >= 500 ? "O servidor não confirmou a operação. Nada será removido do painel; tente novamente." : reason.message;
}

function localDateTime(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function PriorityItem({
  item,
  busy,
  onComplete,
  onEdit,
}: {
  item: DailyItem;
  busy: boolean;
  onComplete: (item: DailyItem) => void;
  onEdit: (mode: QuickEditor["mode"], item: DailyItem) => void;
}) {
  return <article className={`min-w-0 rounded-xl border p-4 ${severityStyle[item.severity]}`}>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">{severityLabel[item.severity]}</p>
        <h3 className="mt-1 font-semibold text-zinc-100">{item.title}</h3>
        {item.case_title && <p className="mt-1 text-sm text-zinc-300">{item.case_title}</p>}
        <p className="mt-1 text-xs text-zinc-400">
          {item.task_kind ? display(item.task_kind) : display(item.source)}
          {item.relevant_at ? ` · ${dateText(item.relevant_at)}` : ""}
          {item.task_kind === "deadline" && !item.manually_reviewed ? " · Data ainda não revisada" : ""}
        </p>
      </div>
      <span className="shrink-0 rounded-full bg-zinc-950/60 px-2 py-1 text-xs text-zinc-300">{display(item.status)}</span>
    </div>
    <div className="mt-4 flex flex-wrap gap-2">
      {item.actions.includes("complete") && <button type="button" className={`${primary} gap-2`} disabled={busy} onClick={() => onComplete(item)}><CheckCircle2 aria-hidden="true" size={17} /> Concluir</button>}
      {item.actions.includes("reschedule") && <button type="button" className={button} disabled={busy} onClick={() => onEdit("reschedule", item)}>Reagendar</button>}
      {item.actions.includes("create_next_action") && <button type="button" className={primary} disabled={busy} onClick={() => onEdit("create", item)}>Cadastrar próxima ação</button>}
      <Link className={button} href={item.href}>Abrir contexto</Link>
    </div>
  </article>;
}

export default function DashboardPage() {
  const { user } = useUser();
  const summary = useResource<DailySummary>("/workspace/summary");
  const analytics = useResource<Row>("/workspace/analytics");
  const activity = useResource<List>("/workspace/activity");
  const [editor, setEditor] = useState<QuickEditor | null>(null);
  const members = useResource<List>(editor?.mode === "create" ? "/workspace/members" : null);
  const [busyId, setBusyId] = useState("");
  const [notice, setNotice] = useState("");
  const [mutationFailure, setMutationFailure] = useState("");

  const openEditor = (mode: QuickEditor["mode"], item: DailyItem) => {
    setMutationFailure(""); setNotice("");
    setEditor({ mode, item, requestId: crypto.randomUUID() });
  };
  const fail = (reason: unknown) => {
    setMutationFailure(mutationError(reason));
    if (reason instanceof ApiError && reason.status === 409) summary.reload();
  };
  const complete = async (item: DailyItem) => {
    if (item.revision == null) return;
    setBusyId(item.id); setMutationFailure(""); setNotice("");
    try {
      await api.put(`/workspace/tasks/${item.id}`, { status: "completed", expected_revision: item.revision });
      setNotice("Ação concluída e registrada no histórico."); summary.reload();
    } catch (reason) { fail(reason); } finally { setBusyId(""); }
  };
  const submitQuickAction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editor) return;
    const data = new FormData(event.currentTarget);
    const dueAt = new Date(String(data.get("due_at"))).toISOString();
    setBusyId(editor.item.id); setMutationFailure(""); setNotice("");
    try {
      if (editor.mode === "reschedule") {
        await api.put(`/workspace/tasks/${editor.item.id}`, {
          due_at: dueAt,
          manually_reviewed: true,
          expected_revision: editor.item.revision,
        });
        setNotice("Ação reagendada e registrada no histórico.");
      } else {
        await api.post("/workspace/tasks", {
          request_id: editor.requestId,
          case_id: editor.item.case_id,
          title: data.get("title"),
          kind: data.get("kind"),
          due_at: dueAt,
          assigned_user_id: data.get("assigned_user_id") || null,
          manually_reviewed: true,
        });
        setNotice("Próxima ação cadastrada e vinculada ao processo.");
      }
      setEditor(null); summary.reload();
    } catch (reason) { fail(reason); } finally { setBusyId(""); }
  };

  const priorities = summary.data?.priorities || [];
  const current = priorities[0];
  const attentionItems = priorities.slice(1).filter(item => !["planning", "upcoming"].includes(item.severity));
  const planningItems = priorities.slice(1).filter(item => ["planning", "upcoming"].includes(item.severity));
  const caseTotal = Object.values(analytics.data?.cases_by_status || {}).reduce((sum: number, value) => sum + Number(value), 0) || 1;

  return <Page title="Painel Diário" subtitle={`Olá, ${user.name}. Entenda o que exige atenção e comece a próxima ação.`}>
    <State loading={summary.loading} error={summary.error} />
    {(notice || mutationFailure) && <div aria-live="polite">{notice && <p role="status" className="rounded-lg border border-emerald-800 bg-emerald-950/25 p-3 text-sm text-emerald-200">{notice}</p>}{mutationFailure && <p role="alert" className="rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-200">{mutationFailure}</p>}</div>}

    {summary.data && <p className="text-xs text-zinc-500">Atualizado em {dateText(summary.data.generated_at)} · Fuso do escritório: {summary.data.timezone}</p>}

    {!summary.loading && !summary.error && <section aria-labelledby="daily-now" className="space-y-3">
      <div><p className="text-xs font-semibold uppercase tracking-wide text-blue-300">Agora</p><h2 id="daily-now" className="mt-1 text-xl font-semibold text-zinc-50">Sua próxima ação</h2></div>
      {current ? <PriorityItem item={current} busy={busyId === current.id} onComplete={complete} onEdit={openEditor} /> : <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-emerald-950/60 text-emerald-300"><CheckCircle2 aria-hidden="true" size={20} /></span><div><h3 className="font-semibold text-zinc-100">Agenda em dia</h3><p className="mt-1 text-sm text-zinc-300">Não há prioridade pendente. Revise a carteira para planejar o próximo passo.</p><Link href="/dashboard/tracker" className={`${button} mt-4`}>Revisar processos</Link></div></div></div>}
    </section>}

    {editor && <section role="dialog" aria-modal="false" aria-labelledby="quick-action-title" className="rounded-xl border border-blue-700 bg-zinc-950 p-4 shadow-xl md:p-5">
      <h2 id="quick-action-title" className="text-lg font-semibold">{editor.mode === "create" ? "Cadastrar próxima ação" : "Reagendar ação"}</h2>
      <p className="mt-1 text-sm text-zinc-400">{editor.item.case_title || editor.item.title} · confira a data antes de salvar.</p>
      <form className="mt-4 space-y-3" onSubmit={submitQuickAction}>
        <fieldset disabled={busyId === editor.item.id} className="space-y-3">
          {editor.mode === "create" && <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Próxima ação"><input autoFocus className={control} name="title" minLength={2} maxLength={300} required /></Field>
            <Field label="Tipo"><select className={control} name="kind" defaultValue="task"><option value="task">Compromisso</option><option value="deadline">Prazo</option><option value="hearing">Audiência</option></select></Field>
            <Field label="Responsável"><select key={Boolean(members.data).toString()} className={control} name="assigned_user_id" defaultValue={user.id}><option value="">Sem responsável</option>{members.data?.items.map(member => <option key={member.id} value={member.id}>{member.full_name}</option>)}</select></Field>
          </div>}
          <Field label="Data e horário local"><input autoFocus={editor.mode === "reschedule"} className={control} name="due_at" type="datetime-local" required defaultValue={editor.mode === "reschedule" ? localDateTime(editor.item.relevant_at) : ""} /></Field>
          <p className="text-xs text-zinc-400">O horário será enviado com o fuso do dispositivo e exibido no fuso configurado do escritório.</p>
          <State error={members.error || mutationFailure} />
          <div className="flex flex-wrap gap-2"><button className={primary}>{busyId === editor.item.id ? "Salvando…" : "Salvar"}</button><button type="button" className={button} onClick={() => { setEditor(null); setMutationFailure(""); }}>Cancelar</button></div>
        </fieldset>
      </form>
    </section>}

    {summary.data && <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[
      ["Para hoje", summary.data.tasks.due_today],
      ["Vencidos", summary.data.tasks.overdue],
      ["Audiências próximas", summary.data.tasks.hearings_upcoming],
      ["Processos sem ação", summary.data.cases.waiting_action],
    ].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4"><dt className="text-sm text-zinc-400">{label}</dt><dd className="mt-2 text-2xl font-semibold text-zinc-50">{value}</dd></div>)}</dl>}

    {summary.data && <section className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
      <Panel title="Hoje e atenção" description="Itens que precisam de decisão antes do planejamento."><div className="space-y-3">{attentionItems.map(item => <PriorityItem key={`${item.source}:${item.id}`} item={item} busy={busyId === item.id} onComplete={complete} onEdit={openEditor} />)}{!attentionItems.length && <p className="text-sm text-zinc-400">Nenhum outro item crítico agora.</p>}</div></Panel>
      <Panel title="Planejamento" description="Próximas ações e processos que ainda precisam de direção."><div className="space-y-3">{planningItems.map(item => <PriorityItem key={`${item.source}:${item.id}`} item={item} busy={busyId === item.id} onComplete={complete} onEdit={openEditor} />)}{!planningItems.length && <p className="text-sm text-zinc-400">Nenhum item adicional para planejar.</p>}</div></Panel>
    </section>}

    {summary.data && <Panel title="Sinais operacionais" description="Estados persistidos; não representam prazos jurídicos inferidos."><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Link href="/dashboard/controladoria" className="rounded-lg border border-zinc-800 p-4 hover:border-blue-700"><BellRing aria-hidden="true" size={19} /><p className="mt-2 text-sm text-zinc-400">Movimentações para revisar</p><strong className="text-xl">{summary.data.attention.pending_judicial_movements}</strong></Link>
      <Link href="/dashboard/library" className="rounded-lg border border-zinc-800 p-4 hover:border-blue-700"><FileWarning aria-hidden="true" size={19} /><p className="mt-2 text-sm text-zinc-400">Falhas em documentos</p><strong className="text-xl">{summary.data.attention.document_failures}</strong></Link>
      <Link href="/dashboard/communications" className="rounded-lg border border-zinc-800 p-4 hover:border-blue-700"><MessageSquareWarning aria-hidden="true" size={19} /><p className="mt-2 text-sm text-zinc-400">Comunicações a revisar</p><strong className="text-xl">{summary.data.attention.communication_failures}</strong></Link>
      {summary.data.attention.financial_drafts != null && <Link href="/dashboard/financeiro" className="rounded-lg border border-zinc-800 p-4 hover:border-blue-700"><WalletCards aria-hidden="true" size={19} /><p className="mt-2 text-sm text-zinc-400">Lançamentos em rascunho</p><strong className="text-xl">{summary.data.attention.financial_drafts}</strong></Link>}
    </div></Panel>}

    <section className="grid gap-4 lg:grid-cols-2">
      <Panel title="Carga dos próximos 7 dias" description="Informação secundária; não bloqueia o fluxo diário."><State loading={analytics.loading} error={analytics.error} />{analytics.data && <div className="space-y-3">{Object.entries(analytics.data.workload_next_7_days || {}).map(([day, raw]) => { const value = Number(raw); const max = Math.max(1, ...Object.values(analytics.data?.workload_next_7_days || {}).map(Number)); return <div key={day} className="grid grid-cols-[5rem_1fr_2rem] items-center gap-3 text-sm"><span className="text-zinc-400">{new Date(`${day}T12:00:00`).toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit" })}</span><span className="h-2 overflow-hidden rounded-full bg-zinc-800"><span className="block h-full rounded-full bg-blue-500" style={{ width: `${(value / max) * 100}%` }} /></span><strong>{value}</strong></div>; })}</div>}</Panel>
      <Panel title="Carteira por situação" description="Somente processos que você pode acessar."><State loading={analytics.loading} error={analytics.error} />{analytics.data && <div className="space-y-3">{Object.entries(analytics.data.cases_by_status || {}).map(([status, raw]) => <div key={status}><div className="mb-1 flex justify-between text-sm"><span>{caseLabels[status] || display(status)}</span><strong>{Number(raw)}</strong></div><div className="h-2 overflow-hidden rounded-full bg-zinc-800"><div className="h-full rounded-full bg-violet-500" style={{ width: `${(Number(raw) / caseTotal) * 100}%` }} /></div></div>)}</div>}</Panel>
    </section>

    <section className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
      <Panel title="Atividade recente" description="Atualizações em linguagem direta."><State loading={activity.loading} error={activity.error} empty={!activity.loading && !activity.data?.items.length} />{activity.data?.items.map(item => <Link key={`${item.area}:${item.id}`} href={item.href} className="block rounded-lg p-3 hover:bg-zinc-800/60"><p className="text-sm font-medium">{item.message}</p><p className="mt-1 text-xs text-zinc-400">{item.area} · {dateText(item.created_at)}</p></Link>)}</Panel>
      <Panel title="Pergunte ao LexFlow" description="Assistência opcional; nada é executado sem confirmação."><button className={`${primary} justify-start gap-2`} onClick={() => window.dispatchEvent(new CustomEvent(OPEN_AI_EVENT, { detail: { prompt: "Organize minhas pendências persistidas sem inventar prazos ou providências." } }))}><Bot aria-hidden="true" size={18} /> Abrir assistente</button></Panel>
    </section>

    <RoutineAttention />
    <Panel title="Cadastros rápidos"><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"><Link className={`${button} justify-start gap-2`} href="/dashboard/crm"><UserPlus aria-hidden="true" size={17} /> Novo cliente</Link><Link className={`${button} justify-start gap-2`} href="/dashboard/tracker"><BriefcaseBusiness aria-hidden="true" size={17} /> Novo processo</Link><Link className={`${button} justify-start gap-2`} href="/dashboard/tasks"><CalendarCheck aria-hidden="true" size={17} /> Novo compromisso</Link><Link className={`${button} justify-start gap-2`} href="/dashboard/petitions/editor"><FilePlus2 aria-hidden="true" size={17} /> Criar documento</Link></div></Panel>
    <p className="max-w-[72ch] text-sm text-zinc-400">Confira datas judiciais e publicações na fonte oficial. O painel organiza registros; não calcula prazos jurídicos.</p>
  </Page>;
}
