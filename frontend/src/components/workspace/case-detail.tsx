"use client";
import { Bot } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { OPEN_AI_EVENT } from "@/components/ai-assistant";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import { Documents } from "./documents";
import { DocumentIntelligence } from "./document-intelligence";
import { CaseMonitoring } from "./controladoria";
import { Ledger } from "./ledger";
import { CaseRoutines } from "./routines";
import { Records, display, type List, type Row } from "./records";
import { Action, Field, Page, Panel, State, button, confirmDiscardDrafts, control, dateText, errorText, primary, useResource } from "./shared";
export function CaseDetail({ id }: { id: string }) {
  const { user } = useUser(); const admin = isOfficeAdminRole(user.role);
  const resource = useResource<Row>(`/workspace/cases/${id}`); const parties = useResource<List>(`/workspace/cases/${id}/parties`);
  const caseRecord = resource.data?.case;
  const access = useResource<List>(admin ? `/workspace/cases/${id}/access` : null); const team = useResource<Row[] | List>("/workspace/members");
  const nextActions = useResource<List>(`/workspace/tasks?case_id=${id}&open_only=true&limit=3`);
  const publications = useResource<List>(`/workspace/publications?case_id=${id}&limit=20`);
  const [view, setView] = useState("overview"); const [addingParty, setAddingParty] = useState(false); const [error, setError] = useState(""); const [sync, setSync] = useState(""); const [notice, setNotice] = useState(""); const [syncRevision, setSyncRevision] = useState(0);
  const members: Row[] = Array.isArray(team.data) ? team.data : team.data?.items || [];
  const history = [
    ...(resource.data?.documents || []).map((item: Row) => ({ ...item, timelineKind: "Documento atualizado", timelineAt: item.updated_at })),
    ...(publications.data?.items || []).map((item: Row) => ({ ...item, timelineKind: "Andamento processual", timelineAt: item.published_at || item.updated_at })),
  ].filter(item => item.timelineAt).sort((left, right) => String(right.timelineAt).localeCompare(String(left.timelineAt))).slice(0, 10);
  return <Page title={caseRecord?.title || "Processo 360°"} subtitle={caseRecord ? `${caseRecord.number || "Sem número judicial"} · ${caseRecord.court || "Tribunal não informado"} · ${display(caseRecord.status)}` : "Carregando processo"} backHref="/dashboard/tracker" backLabel="Voltar aos processos">
    <State loading={resource.loading} error={resource.error || error} />
    {notice && <p role="status" className="text-sm text-green-300">{notice}</p>}
    {resource.data && <>
      <nav aria-label="O que deseja consultar neste processo" className="flex flex-wrap gap-2 border-b border-zinc-800 pb-4">
        {Object.entries({ overview: "Resumo do processo", tasks: "Agenda", documents: "Arquivos" }).map(([key, label]) => <button key={key} aria-pressed={view === key} className={`${button} ${view === key ? "border-blue-500 bg-blue-500/15 text-blue-100" : ""}`} onClick={() => { if (key === view || confirmDiscardDrafts()) setView(key); }}>{label}</button>)}
        <details className="min-w-0"><summary className={`${button} ${["routines", "publications", "ledger"].includes(view) ? "border-blue-500 bg-blue-500/15 text-blue-100" : ""} cursor-pointer list-none`}>Mais informações</summary><div className="mt-2 flex flex-wrap gap-2">
          {Object.entries({ routines: "Diligências", publications: "Andamentos", ...(admin ? { ledger: "Honorários e despesas" } : {}) }).map(([key, label]) => <button key={key} aria-pressed={view === key} className={`${button} ${view === key ? "border-blue-500 bg-blue-500/15 text-blue-100" : ""}`} onClick={() => { if (key === view || confirmDiscardDrafts()) setView(key); }}>{label}</button>)}
        </div></details>
      </nav>
      {view === "routines" && <CaseRoutines key={id} caseId={id} />}
      {view === "tasks" && <Records key={id} kind="tasks" caseId={id} embedded />}
      {view === "documents" && <><DocumentIntelligence caseId={id} documents={resource.data.documents || []} /><Documents key={id} caseId={id} embedded /></>}
      {view === "ledger" && <Ledger caseId={id} embedded />}
      {view === "publications" && <><Panel title="Consulta processual pública"><p className="text-xs text-zinc-400">Importa informações do processo público para conferência. Não consulta autos sigilosos nem calcula prazos. Informe a sigla do tribunal, como TJSP ou TRF1.</p><Field label="Tribunal"><input className={control} value={sync} onChange={e => setSync(e.target.value)} placeholder="TJSP" /></Field><Action run={async () => {
        const result = await api.post<{ imported: number }>(`/engagement/cases/${id}/sync`, { tribunal: sync }); setNotice(`Consulta concluída: ${result.imported} novos andamentos.`); setSyncRevision(value => value + 1);
      }}>Consultar fonte oficial</Action></Panel><Records key={syncRevision} kind="publications" caseId={id} embedded /></>}
      {view === "overview" && <>
        <section aria-labelledby="case-summary" className="rounded-2xl bg-blue-500/10 p-5 md:p-6"><div className="max-w-3xl"><h2 id="case-summary" className="text-lg font-semibold text-blue-100">Visão do processo</h2><p className="mt-2 text-sm text-zinc-200">{caseRecord?.number || "Processo sem número informado"} · {caseRecord?.court || "Tribunal ou vara não informados"}</p><p className="mt-1 text-sm text-zinc-300">Situação: {display(caseRecord?.status)}. Consulte a fonte oficial antes de decidir qualquer prazo.</p></div><div className="mt-4 flex flex-wrap gap-2"><button type="button" className={primary} onClick={() => setView("tasks")}>Ver agenda do processo</button><button type="button" className={button} onClick={() => window.dispatchEvent(new CustomEvent(OPEN_AI_EVENT, { detail: { contextKind: "case", caseId: id } }))}><Bot aria-hidden="true" size={16} /> Analisar com IA</button></div></section>
        <CaseMonitoring caseId={id} processNumber={caseRecord?.number} court={caseRecord?.court} />
        <Panel title="Próximas providências"><State loading={nextActions.loading} error={nextActions.error} />{!nextActions.loading && !nextActions.error && !nextActions.data?.items.length && <p className="text-sm text-zinc-400">Ainda não há providências abertas neste processo. Use a agenda para registrar a próxima ação.</p>}<div className="divide-y divide-zinc-800">{nextActions.data?.items.map(item => <article key={item.id} className="py-3 first:pt-0"><p className="text-sm font-medium">{item.title}</p><p className="mt-1 text-xs text-zinc-400">{display(item.kind)} · {dateText(item.due_at)} · {item.manually_reviewed ? "Data conferida" : "Conferência da data pendente"}</p></article>)}</div></Panel>
        <Panel title="Histórico recente"><State loading={publications.loading} error={publications.error} />{!publications.loading && !publications.error && !history.length && <p className="text-sm text-zinc-400">O histórico aparecerá quando houver documentos ou andamentos neste processo.</p>}<div className="divide-y divide-zinc-800">{history.map(item => <article key={`${item.timelineKind}:${item.id}`} className="py-3 first:pt-0"><p className="text-sm font-medium">{item.title || item.filename || "Registro do processo"}</p><p className="mt-1 text-xs text-zinc-400">{item.timelineKind} · {dateText(item.timelineAt)}</p></article>)}</div></Panel>
        <Panel title="Partes relacionadas" collapsibleOnMobile><State loading={parties.loading} error={parties.error} />{!parties.loading && !parties.error && !parties.data?.items.length && <p className="text-sm text-zinc-400">Nenhuma parte relacionada.</p>}{parties.data?.items.map(row => <p key={row.id} className="text-sm">{row.name} · {display(row.side)} · {row.role || "Sem função informada"}</p>)}
          {!addingParty && <button type="button" className={button} onClick={() => setAddingParty(true)}>Gerenciar partes</button>}
          {addingParty && <form className="grid sm:grid-cols-2 gap-3" onSubmit={async e => { e.preventDefault(); const form = e.currentTarget; const d = new FormData(form); setError(""); try { await api.post(`/workspace/cases/${id}/parties`, { name: d.get("name"), tax_id: d.get("tax_id") || null, side: d.get("side"), role: d.get("role") || null }); form.reset(); setAddingParty(false); parties.reload(); } catch (err) { setError(errorText(err)); } }}>
            <Field label="Nome"><input className={control} required name="name" minLength={2} maxLength={200} /></Field><Field label="CPF/CNPJ"><input className={control} name="tax_id" maxLength={20} /></Field>
            <Field label="Relação"><select className={control} name="side"><option value="client">Cliente</option><option value="opponent">Parte contrária</option><option value="third_party">Terceiro</option></select></Field><Field label="Função"><input className={control} name="role" maxLength={100} /></Field><div className="flex flex-wrap gap-2"><button className={primary}>Salvar parte</button><button type="button" className={button} onClick={() => setAddingParty(false)}>Cancelar</button></div>
          </form>}
        </Panel>
        {admin && caseRecord?.restricted && <Panel title="Acesso ao processo restrito" collapsibleOnMobile><State error={access.error || team.error} />{access.data?.items.map(row => <p className="text-xs" key={row.user_id}>{members.find(m => (m.id || m.user_id) === row.user_id)?.full_name || row.user_id} <Action run={() => api.delete(`/workspace/cases/${id}/access/${row.user_id}`)} onDone={access.reload}>Revogar</Action></p>)}
          <form className="flex flex-wrap gap-2" onSubmit={async e => { e.preventDefault(); const user_id = new FormData(e.currentTarget).get("user_id"); try { await api.post(`/workspace/cases/${id}/access`, { user_id }); access.reload(); } catch (err) { setError(errorText(err)); } }}><select name="user_id" required className={`${control} max-w-sm`} aria-label="Membro autorizado"><option value="">Selecione um membro</option>{members.map(row => <option key={row.id || row.user_id} value={row.id || row.user_id}>{row.full_name || row.user_name || row.email}</option>)}</select><button className={primary}>Autorizar membro</button></form>
        </Panel>}
      </>}
    </>}
  </Page>;
}
