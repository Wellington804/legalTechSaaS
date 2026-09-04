"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { display } from "./records";
import { DraftNotice, Field, Page, Panel, State, button, control, dateText, errorText, primary, useAccountDraft, useDraftGuard, useResource } from "./shared";

type Step = { id: string; title: string; description: string; href: string; status: "done" | "pending" | "not_applicable" };
type Overview = {
  steps: Step[]; subscription: { status: string; ends_at: string | null; days_remaining: number | null; write_allowed: boolean };
  security: { email_verified: boolean; mfa_enabled: boolean; environment: string; sentry_configured: boolean; account_email_configured: boolean; https_configured: boolean };
  support_url: string | null; release: string; weekly: { last_report_at: string | null; next_review_at: string | null }; data_policy: string;
};
type Feedback = { id: string; kind: string; area: string; message: string; release: string; created_at: string };
type TeamFeedback = Feedback & { user_id: string; user_name: string };
const areas = { dashboard: "Central", account: "Conta", clients: "Clientes", cases: "Processos", tasks: "Agenda", documents: "Documentos", finance: "Financeiro", communications: "Comunicações", other: "Outra área" };

export function Pilot() {
  const { user } = useUser(); const admin = isOfficeAdminRole(user.role);
  const overview = useResource<Overview>("/pilot/overview"); const reports = useResource<{ items: Feedback[] }>("/pilot/feedback");
  const team = useResource<{ items: TeamFeedback[]; summary: { total: number; problems: number; weekly_reviews: number; last_report_at: string | null } }>(admin ? "/pilot/feedback/team" : null);
  const draft = useDraftGuard("pilot:feedback");
  const [kind, setKind] = useState(draft.initialValues?.kind || "problem"); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [requestId] = useAccountDraft<{ current: string | null }>("pilot:feedback:request", { current: null }); const data = overview.data;
  const nextStep = data?.steps.find(step => step.status === "pending");
  return <Page title="Primeiros passos e piloto" subtitle="Piloto fechado com dados reais controlados, acompanhamento semanal e uso restrito aos participantes autorizados.">
    <State loading={overview.loading} error={overview.error} />
    {data && <>
      <Panel title="O que fazer agora">
        {nextStep ? <div className="flex flex-wrap items-center justify-between gap-3"><div className="min-w-0"><p className="text-sm font-medium">{nextStep.title}</p><p className="text-xs text-zinc-400">{nextStep.description}</p></div><Link href={nextStep.href} className={primary}>Abrir próxima etapa</Link></div>
          : <p className="text-sm">As etapas disponíveis foram concluídas ou não se aplicam ao seu acesso.</p>}
      </Panel>
      <Panel title="Acompanhamento do piloto" collapsibleOnMobile>
        <p className="text-sm">Acesso: {display(data.subscription.status)} · termina em {dateText(data.subscription.ends_at)}{data.subscription.days_remaining != null && ` · ${data.subscription.days_remaining} dias restantes`}</p>
        {!data.subscription.write_allowed && <p className="text-sm text-amber-300">Gravações indisponíveis neste período. Consulte o responsável pelo piloto para regularizar o acesso.</p>}
        <p className="text-xs text-zinc-400">Versão {data.release} · último relato {dateText(data.weekly.last_report_at)} · próxima revisão {dateText(data.weekly.next_review_at)}.</p>
        {data.support_url ? <a href={data.support_url} target="_blank" rel="noopener noreferrer" className={button}>Abrir suporte</a> : <p className="text-xs text-zinc-400">Registre o relato abaixo para receber acompanhamento durante o piloto.</p>}
      </Panel>
      <Panel title="Seu primeiro atendimento">
        <p className="text-xs text-zinc-400">Use um atendimento autorizado de ponta a ponta. Registre somente o necessário e confira fontes oficiais antes de agir.</p>
        <ol className="divide-y divide-zinc-800">{data.steps.map(step => <li key={step.id} className="py-3 flex flex-wrap items-center justify-between gap-3"><div className="min-w-0 flex-1"><p className="text-sm">{step.title} · {step.status === "done" ? "Concluído" : step.status === "not_applicable" ? "Não se aplica ao seu acesso" : "Pendente"}</p><p className="text-xs text-zinc-400">{step.description}</p></div>{step.status !== "not_applicable" && <Link href={step.href} className={button}>Abrir etapa</Link>}</li>)}</ol>
      </Panel>
      <Panel title="Regras deste piloto" collapsibleOnMobile>
        <ul className="list-disc space-y-2 pl-5 text-sm"><li>Use apenas dados autorizados e controlados pelo advogado participante.</li><li>Confira andamentos, intimações e prazos na fonte oficial.</li><li>Não compartilhe links do portal ou da agenda fora dos destinatários previstos.</li><li>Relate dificuldades e resultados ao menos uma vez por semana.</li></ul>
        <p className="text-xs text-zinc-400">Conexão segura: {data.security.https_configured ? "ativa" : "pendente"} · e-mail verificado: {data.security.email_verified ? "sim" : "não"} · ambiente: {data.security.environment}.</p>
      </Panel>
    </>}
    <div id="feedback" className="scroll-mt-20"><Panel title="Relatar problema ou revisar a semana">
      <p className="text-xs text-zinc-400">Descreva a dificuldade sem nomes de clientes, CPF, números de processo ou segredos. Nenhuma captura de tela, URL do caso ou log é anexado automaticamente.</p>
      <form ref={draft.formRef} className="space-y-3" onChange={() => { draft.setDirty(true); requestId.current = null; }} onSubmit={async event => {
        event.preventDefault(); const form = event.currentTarget; const values = new FormData(form); setError(""); setNotice(""); setBusy(true);
        requestId.current ||= crypto.randomUUID();
        try {
          await api.post("/pilot/feedback", { request_id: requestId.current, kind, area: values.get("area"), message: values.get("message"), completed_steps: kind === "weekly" ? values.getAll("completed") : [], help_steps: kind === "weekly" ? values.getAll("help") : [], consent: true });
          form.reset(); draft.setDirty(false); requestId.current = null; reports.reload(); overview.reload(); setNotice("Relato registrado. Nenhum atendimento externo foi presumido.");
        } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
      }}><fieldset disabled={busy} className="min-w-0 space-y-3">
        <div className="grid sm:grid-cols-2 gap-3"><Field label="Tipo de relato"><select name="kind" className={control} value={kind} onChange={e => setKind(e.target.value)}><option value="problem">Relatar problema</option><option value="weekly">Revisão semanal</option></select></Field><Field label="Área"><select name="area" className={control}>{Object.entries(areas).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field></div>
        {kind === "weekly" && data && <div className="grid sm:grid-cols-2 gap-3">{[["completed", "Consegui usar sozinho"], ["help", "Preciso de ajuda"]].map(([name, label]) => <fieldset key={name} className="rounded-lg border border-zinc-800 p-3"><legend className="text-xs">{label}</legend>{data.steps.filter(step => step.status !== "not_applicable").map(step => <label className="flex min-h-11 items-center gap-2 text-sm" key={step.id}><input type="checkbox" name={name} value={step.id} />{step.title}</label>)}</fieldset>)}</div>}
        <Field label="O que aconteceu ou precisa melhorar?"><textarea name="message" className={control} required maxLength={3000} rows={5} /></Field>
        <label className="flex min-h-11 gap-2 items-center text-xs"><input type="checkbox" name="consent" required />Autorizo registrar este relato para acompanhamento do piloto.</label>
        <DraftNotice dirty={draft.dirty} /><State error={error} /><button className={primary}>{busy ? "Registrando…" : "Registrar relato"}</button>
      </fieldset></form>{notice && <p role="status" className="text-sm text-green-300">{notice}</p>}
    </Panel></div>
    <Panel title="Meus relatos"><State loading={reports.loading} error={reports.error} empty={!reports.data?.items.length} />{reports.data?.items.map(report => <article key={report.id} className="space-y-1 border-b border-zinc-800 pb-3"><p className="text-xs text-zinc-400">{report.kind === "weekly" ? "Revisão semanal" : "Problema"} · {dateText(report.created_at)} · {report.release}</p><p className="text-sm whitespace-pre-wrap">{report.message}</p></article>)}</Panel>
    {admin && <Panel title="Acompanhamento do escritório"><State loading={team.loading} error={team.error} empty={!team.data?.items.length} /><div className="grid gap-3 sm:grid-cols-3"><p className="rounded-lg border border-zinc-800 p-3 text-sm">Relatos: <strong>{team.data?.summary.total || 0}</strong></p><p className="rounded-lg border border-zinc-800 p-3 text-sm">Problemas: <strong>{team.data?.summary.problems || 0}</strong></p><p className="rounded-lg border border-zinc-800 p-3 text-sm">Revisões semanais: <strong>{team.data?.summary.weekly_reviews || 0}</strong></p></div>{team.data?.items.map(report => <article key={report.id} className="space-y-1 border-b border-zinc-800 py-3"><p className="text-xs text-zinc-400">{report.user_name} · {report.kind === "weekly" ? "Revisão semanal" : "Problema"} · {dateText(report.created_at)} · {areas[report.area as keyof typeof areas] || report.area}</p><p className="whitespace-pre-wrap text-sm">{report.message}</p></article>)}</Panel>}
  </Page>;
}
