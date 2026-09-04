"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { flushSync } from "react-dom";
import { api } from "@/lib/api-client";
import { useUser } from "@/context/user-context";
import { Action, DraftNotice, Field, Page, Panel, State, button, confirmDiscardDrafts, control, dateText, errorText, primary, scrollWorkspaceToTop, useDraftGuard, useResource } from "./shared";
import { TaskReminder } from "./routines";
import { ClientImport } from "./client-import";
import { FileCenter } from "./file-center";

export type Row = { id: string; [key: string]: any };
export type List = { items: Row[]; limit: number };
type Input = { key: string; label: string; type?: string; required?: boolean; options?: string[]; relation?: "clients" | "cases" | "members"; max?: number };
export type Definition = { title: string; subtitle: string; path: string; fields: Input[]; columns: string[] };
export const definitions: Record<string, Definition> = {
  clients: { title: "Clientes e oportunidades", subtitle: "Cadastro único do escritório. Converta uma oportunidade mudando sua etapa; o histórico permanece no mesmo registro.", path: "clients", columns: ["name", "email", "phone", "stage"], fields: [
    { key: "name", label: "Nome / razão social", required: true, max: 200 }, { key: "email", label: "E-mail", type: "email", max: 320 },
    { key: "phone", label: "WhatsApp", type: "tel", max: 32 }, { key: "tax_id", label: "CPF/CNPJ", max: 20 },
    { key: "person_type", label: "Tipo de pessoa", options: ["individual", "company"] }, { key: "qualification", label: "Qualificação", type: "textarea", max: 500 },
    { key: "occupation", label: "Profissão / atividade", max: 160 },
    { key: "has_legal_representative", label: "Há representante legal?", type: "checkbox" },
    { key: "representative_name", label: "Nome completo do representante", required: true, max: 200 },
    { key: "representative_tax_id", label: "CPF/CNPJ do representante", max: 20 },
    { key: "representative_qualification", label: "Qualificação do representante", type: "textarea", max: 500 },
    { key: "representative_email", label: "E-mail do representante", type: "email" },
    { key: "representative_phone", label: "WhatsApp do representante", type: "tel" },
    { key: "representative_address_street", label: "Endereço do representante — rua / avenida" },
    { key: "representative_address_number", label: "Endereço do representante — número" },
    { key: "representative_address_complement", label: "Endereço do representante — complemento" },
    { key: "representative_address_district", label: "Endereço do representante — bairro" },
    { key: "representative_address_city", label: "Endereço do representante — cidade" },
    { key: "representative_address_state", label: "Endereço do representante — UF", max: 2 },
    { key: "representative_address_postal_code", label: "Endereço do representante — CEP", max: 10 },
    { key: "address_street", label: "Rua / avenida" }, { key: "address_number", label: "Número" }, { key: "address_complement", label: "Complemento" },
    { key: "address_district", label: "Bairro" }, { key: "address_city", label: "Cidade" }, { key: "address_state", label: "UF", max: 2 }, { key: "address_postal_code", label: "CEP", max: 10 },
    { key: "stage", label: "Etapa", options: ["lead", "prospect", "client", "inactive"] },
  ] },
  cases: { title: "Processos", subtitle: "Acompanhe os processos do escritório e mantenha os dados conferidos com as fontes oficiais.", path: "cases", columns: ["title", "number", "court", "status"], fields: [
    { key: "client_id", label: "Cliente", relation: "clients", required: true }, { key: "title", label: "Assunto do processo", required: true },
    { key: "number", label: "Número do processo" }, { key: "court", label: "Tribunal / vara" },
    { key: "status", label: "Situação", options: ["open", "paused", "closed", "archived"] },
    { key: "responsible_user_id", label: "Responsável", relation: "members", required: true },
    { key: "restricted", label: "Restrito ao responsável e membros autorizados", type: "checkbox" },
  ] },
  tasks: { title: "Agenda e prazos", subtitle: "Datas são informadas e revisadas pelo responsável. Não há cálculo automático de prazo judicial.", path: "tasks", columns: ["title", "kind", "due_at", "status"], fields: [
    { key: "case_id", label: "Caso", relation: "cases", required: true }, { key: "title", label: "Título", required: true },
    { key: "kind", label: "Tipo", options: ["task", "deadline", "hearing"] }, { key: "due_at", label: "Data e horário local", type: "datetime-local" },
    { key: "status", label: "Situação", options: ["pending", "in_progress", "completed", "cancelled"] },
    { key: "assigned_user_id", label: "Atribuído a", relation: "members" },
    { key: "location", label: "Local da diligência", max: 300 }, { key: "contact", label: "Contato no local", max: 200 },
    { key: "notes", label: "Orientações para a diligência", type: "textarea", max: 5000 },
    { key: "manually_reviewed", label: "Data e origem conferidas por mim", type: "checkbox" },
  ] },
  library: { title: "Biblioteca jurídica", subtitle: "Acervo privado com fonte e data. Links são referências; o sistema não atesta a vigência ou o entendimento jurídico.", path: "library", columns: ["title", "source_url", "created_at"], fields: [
    { key: "title", label: "Título", required: true }, { key: "source_url", label: "Link da fonte", type: "url", required: true },
    { key: "note", label: "Anotações e contexto", type: "textarea" },
    { key: "source_date", label: "Data da fonte", type: "date" },
  ] },
  publications: { title: "Publicações e andamentos", subtitle: "Cada registro conserva origem e data. A confirmação de leitura não cria nem calcula prazos.", path: "publications", columns: ["title", "source_url", "published_at", "acknowledged_at"], fields: [
    { key: "case_id", label: "Caso", relation: "cases", required: true }, { key: "title", label: "Descrição do andamento", required: true },
    { key: "source_url", label: "Link da fonte", type: "url", required: true }, { key: "published_at", label: "Data da publicação", type: "date", required: true },
  ] },
};
const labels: Record<string, string> = { lead: "Novo contato", prospect: "Em atendimento", client: "Cliente", inactive: "Inativo", individual: "Pessoa física", company: "Pessoa jurídica", open: "Aberto", paused: "Suspenso", closed: "Encerrado", archived: "Arquivado", pending: "Pendente", completed: "Concluída", cancelled: "Cancelada", canceled: "Cancelada", active: "Ativa", trial: "Período de teste", past_due: "Pagamento pendente", recorded: "Registrada", queued: "Na fila", sent: "Enviada", delivered: "Entregue", failed: "Falha", posted: "Efetivado", reversed: "Estornado", portal: "Portal", whatsapp: "WhatsApp", email: "E-mail", starter: "Inicial", professional: "Profissional", office: "Escritório", task: "Tarefa", deadline: "Prazo", hearing: "Audiência", judicial_event: "Movimentação judicial", opponent: "Parte contrária", third_party: "Terceiro" };
const creationLabels: Record<keyof typeof definitions, string> = { clients: "Cadastrar cliente", cases: "Novo processo", tasks: "Criar compromisso", library: "Adicionar referência", publications: "Registrar andamento" };
const submitLabels: Record<string, string> = { clients: "Cadastrar cliente", cases: "Salvar processo", tasks: "Criar compromisso", library: "Salvar referência", publications: "Registrar andamento" };
const listTitles: Record<keyof typeof definitions, string> = { clients: "Clientes do escritório", cases: "Processos do escritório", tasks: "Agenda do escritório", library: "Referências do escritório", publications: "Andamentos do escritório" };
const clientCoreKeys = new Set(["name", "tax_id", "email", "phone", "stage"]);
export function display(value: unknown, key?: string): string {
  if (value == null || value === "") return "—";
  if (value === "in_progress") return "Em andamento";
  if (key?.endsWith("_at")) return dateText(value);
  return labels[String(value)] || String(value);
}

function ClientCoreFields({ record, autoFocus = false }: { record?: Row; autoFocus?: boolean }) {
  return <div className="grid gap-3 sm:grid-cols-2">{definitions.clients.fields.filter(field => clientCoreKeys.has(field.key)).map(field => {
    const value = record?.[field.key] ?? (field.key === "stage" ? "lead" : "");
    return <Field key={field.key} label={field.label}>{field.options
      ? <select name={field.key} defaultValue={value} className={control}>{field.options.map(option => <option key={option} value={option}>{display(option)}</option>)}</select>
      : <input name={field.key} type={field.type || "text"} required={field.required} defaultValue={value} maxLength={field.max || 500} autoFocus={autoFocus && field.key === "name"} className={control} />}</Field>;
  })}</div>;
}

function QuickClientDialog({ onCancel, onCreated }: { onCancel: () => void; onCreated: (client: Row) => void }) {
  const dialog = useRef<HTMLDialogElement>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError("");
    const value = (key: string) => String(data.get(key) || "").trim();
    try {
      const client = await api.post<Row>("/workspace/clients", {
        name: value("name"), tax_id: value("tax_id") || null, email: value("email") || null,
        phone: value("phone") || null, stage: value("stage") || "lead",
      });
      onCreated(client);
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  return <dialog ref={dialog} aria-labelledby="quick-client-title" onCancel={event => { event.preventDefault(); onCancel(); }} onClick={event => { if (event.target === event.currentTarget) onCancel(); }} className="m-auto max-h-[85dvh] w-[calc(100%_-_2rem)] max-w-xl overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-950 p-4 text-zinc-100 backdrop:bg-black/70 max-sm:m-0 max-sm:mt-auto max-sm:h-[calc(100dvh-1rem)] max-sm:max-h-[calc(100dvh-1rem)] max-sm:w-full max-sm:max-w-none max-sm:rounded-b-none">
    <form onSubmit={submit} className="space-y-4"><header><h2 id="quick-client-title" className="text-lg font-semibold">Novo cliente</h2><p className="mt-1 text-sm text-zinc-400">Cadastre os dados essenciais e continue neste processo.</p></header>
      <fieldset disabled={busy} className="space-y-4"><ClientCoreFields autoFocus /><State error={error} /><div className="flex flex-wrap justify-end gap-2"><button type="button" className={button} onClick={onCancel}>Cancelar</button><button className={primary}>{busy ? "Cadastrando…" : "Cadastrar e selecionar"}</button></div></fieldset>
    </form>
  </dialog>;
}

export function RecordForm({ definition, record, onDone, caseId }: { definition: Definition; record?: Row; onDone: (created?: Row) => void; caseId?: string }) {
  const { user } = useUser();
  const clients = useResource<List>(definition.fields.some(f => f.relation === "clients") ? "/workspace/clients" : null);
  const cases = useResource<List>(definition.fields.some(f => f.relation === "cases") ? "/workspace/cases" : null);
  const members = useResource<List>(definition.fields.some(f => f.relation === "members") ? "/workspace/members" : null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [hasRepresentative, setHasRepresentative] = useState(Boolean(record?.has_legal_representative));
  const [quickClient, setQuickClient] = useState(false);
  const [createdClient, setCreatedClient] = useState<Row | null>(null);
  const [relationValues, setRelationValues] = useState<Record<string, string>>({
    client_id: String(record?.client_id || ""), case_id: String(record?.case_id || caseId || ""), responsible_user_id: String(record?.responsible_user_id || user.id || ""), assigned_user_id: String(record?.assigned_user_id || ""),
  });
  const draft = useDraftGuard(`record:${definition.path}:${caseId || "all"}:${record?.id || "new"}`);
  function selectCreatedClient(created: Row) {
    const id = String(created.id);
    flushSync(() => {
      setCreatedClient(created); setRelationValues(current => ({ ...current, client_id: id })); setQuickClient(false);
    });
    const select = draft.formRef.current?.elements.namedItem("client_id");
    if (select instanceof HTMLSelectElement) { select.value = id; select.dispatchEvent(new Event("change", { bubbles: true })); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); const body: Record<string, unknown> = {};
    for (const field of definition.fields) {
      if (record && ((definition.path === "cases" && field.key === "client_id") || (definition.path === "tasks" && ["case_id", "kind"].includes(field.key)))) continue;
      const value = data.get(field.key);
      body[field.key] = field.type === "checkbox" ? value === "on" : field.type === "datetime-local" && value ? new Date(String(value)).toISOString() : value || null;
    }
    if (definition.path === "clients") {
      const address = { street: body.address_street, number: body.address_number, complement: body.address_complement, district: body.address_district, city: body.address_city, state: body.address_state, postal_code: body.address_postal_code };
      const representativeAddress = { street: body.representative_address_street, number: body.representative_address_number, complement: body.representative_address_complement, district: body.representative_address_district, city: body.representative_address_city, state: body.representative_address_state, postal_code: body.representative_address_postal_code };
      for (const key of Object.keys(address)) delete body[`address_${key}`];
      for (const key of Object.keys(representativeAddress)) delete body[`representative_address_${key}`];
      const hasAddress = Object.values(address).some(Boolean);
      if (hasAddress && (!address.street || !address.number || !address.city || String(address.state || "").length !== 2 || String(address.postal_code || "").length < 8)) { setError("Complete rua, número, cidade, UF e CEP do cliente."); return; }
      const hasRepresentativeAddress = Object.values(representativeAddress).some(Boolean);
      if (hasRepresentativeAddress && (!representativeAddress.street || !representativeAddress.number || !representativeAddress.city || String(representativeAddress.state || "").length !== 2 || String(representativeAddress.postal_code || "").length < 8)) { setError("Complete rua, número, cidade, UF e CEP do representante legal."); return; }
      body.address = hasAddress ? address : null;
      body.representative_address = body.has_legal_representative && hasRepresentativeAddress ? representativeAddress : null;
    }
    if (record?.revision != null) body.expected_revision = Number(data.get("draft_revision"));
    setBusy(true); setError("");
    try {
      const saved = record ? await api.put<Row>(`/workspace/${definition.path}/${record.id}`, body) : await api.post<Row>(`/workspace/${definition.path}`, body);
      draft.setDirty(false); if (!record) form.reset(); onDone(saved);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  return <>{quickClient && <QuickClientDialog onCancel={() => setQuickClient(false)} onCreated={selectCreatedClient} />}<form ref={draft.formRef} onSubmit={submit} onChange={event => { if ((event.target as HTMLInputElement).name === "due_at") { const review = event.currentTarget.elements.namedItem("manually_reviewed") as HTMLInputElement | null; if (review) review.checked = false; } draft.setDirty(true); }} className="space-y-3"><fieldset disabled={busy} className="min-w-0 space-y-3">
    {record?.revision != null && <input type="hidden" name="draft_revision" defaultValue={record.revision} />}
    {definition.path === "clients" && <ClientCoreFields record={record} />}
    <div className="grid sm:grid-cols-2 gap-3">{definition.fields.map(field => {
      if (definition.path === "clients" && clientCoreKeys.has(field.key)) return null;
      if (definition.path === "clients" && field.key.startsWith("representative_") && !hasRepresentative) return null;
      const address = field.key.startsWith("address_") ? record?.address : field.key.startsWith("representative_address_") ? record?.representative_address : null;
      const addressField = field.key.startsWith("address_") ? field.key.replace("address_", "") : field.key.replace("representative_address_", "");
      let value = address ? address[addressField] : record?.[field.key] ?? (field.key === "case_id" ? caseId : field.key === "responsible_user_id" ? user.id : "") ?? "";
      if (field.type === "datetime-local" && value) { const d = new Date(value); value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
      const options = field.relation === "clients" ? [...(clients.data?.items || []), ...(createdClient && !clients.data?.items.some(item => item.id === createdClient.id) ? [createdClient] : [])] : field.relation === "members" ? members.data?.items?.filter(row => field.key !== "responsible_user_id" || ["admin", "partner", "lawyer"].includes(row.role)) : cases.data?.items;
      if (definition.path === "cases" && field.key === "client_id" && !record) {
        const empty = !clients.loading && !options?.length;
        return <fieldset key={field.key} className="min-w-0"><legend className="mb-1.5 text-sm font-medium text-zinc-300">Cliente</legend><div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><select aria-label="Cliente" name="client_id" value={relationValues.client_id || ""} onChange={event => setRelationValues(current => ({ ...current, client_id: event.target.value }))} required className={control}><option value="">Selecione um cliente…</option>{options?.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}</select><button type="button" className={button} onClick={() => setQuickClient(true)}>{empty ? "Cadastrar primeiro cliente" : "+ Novo cliente"}</button></div>{empty && <div className="mt-2 text-sm"><p className="font-medium">Nenhum cliente cadastrado.</p><p className="mt-1 text-zinc-400">Cadastre o cliente para continuar com o processo.</p></div>}</fieldset>;
      }
      return <div key={field.key} className="min-w-0"><Field label={field.label}>
        {field.type === "textarea" ? <textarea name={field.key} defaultValue={value} maxLength={field.max || 10000} className={control} rows={4} />
          : field.type === "checkbox" ? <input name={field.key} type="checkbox" defaultChecked={Boolean(value)} onChange={field.key === "has_legal_representative" ? event => setHasRepresentative(event.currentTarget.checked) : undefined} className="h-4 w-4" />
          : field.options || field.relation ? <select key={`${field.key}:${Boolean(options)}`} name={field.key} disabled={Boolean(record && ((definition.path === "cases" && field.key === "client_id") || (definition.path === "tasks" && ["case_id", "kind"].includes(field.key))))} value={field.relation ? relationValues[field.key] ?? String(value || "") : undefined} onChange={field.relation ? event => setRelationValues(current => ({ ...current, [field.key]: event.target.value })) : undefined} defaultValue={field.relation ? undefined : value || field.options?.[0] || ""} required={field.required} className={control}>
            {field.relation && <option value="">Selecione…</option>}{field.options?.map(option => <option key={option} value={option}>{display(option)}</option>)}
            {options?.map(option => <option key={option.id} value={option.id}>{option.name || option.full_name || option.title}</option>)}
          </select> : <input name={field.key} type={field.type || "text"} required={field.required} defaultValue={value} maxLength={field.max || 500} className={control} />}
      </Field></div>;
    })}</div>
    {definition.path === "tasks" && record && <p className="text-xs text-amber-300">Alterar data ou situação cancela lembretes anteriores. Salve e revise seu lembrete novamente.</p>}
    {definition.path === "tasks" && <p className="text-xs text-zinc-400">Não conhece a data? Deixe em branco; a tarefa pode ser acompanhada e concluída sem inventar um prazo. Lembretes exigem data conferida.</p>}
    {record && draft.dirty && <p className="text-xs text-zinc-400">A revisão original do rascunho foi preservada. Em caso de conflito, cancele esta edição e confira o registro atual antes de reaplicar suas alterações.</p>}
    <DraftNotice dirty={draft.dirty} /><State error={error || clients.error || cases.error || members.error} /><button disabled={busy} className={primary}>{busy ? "Salvando…" : record ? "Salvar alterações" : submitLabels[definition.path]}</button></fieldset>
  </form></>;
}

export function Records({ kind, caseId, embedded = false }: { kind: keyof typeof definitions; caseId?: string; embedded?: boolean }) {
  const { drafts } = useUser();
  const definition = definitions[kind]; const path = `/workspace/${definition.path}${caseId ? `?case_id=${caseId}` : ""}`;
  const resource = useResource<List>(path); const [editing, setEditing] = useState<Row | null>(null); const [creating, setCreating] = useState(false); const [query, setQuery] = useState("");
  const [selectedClient, setSelectedClient] = useState<Row | null>(null);
  const [reminderFor, setReminderFor] = useState<Row | null>(null);
  const clientCases = useResource<List>(selectedClient ? `/workspace/cases?client_id=${selectedClient.id}&limit=200` : null);
  const items = resource.data?.items.filter(row => definition.columns.some(key => String(row[key] || "").toLocaleLowerCase().includes(query.toLocaleLowerCase()))) || [];
  const closeForm = () => {
    if (!confirmDiscardDrafts()) return;
    drafts.delete(`record:${definition.path}:${caseId || "all"}:${editing?.id || "new"}`);
    setEditing(null); setCreating(false);
  };
  const emptyMessage = query ? "Nenhum registro corresponde ao filtro. Limpe ou ajuste a busca." : `Ainda não há registros nesta área. ${creationLabels[kind]} para iniciar.`;
  const content = <>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm text-zinc-400">Consulte a lista e abra um registro quando precisar agir.</p>
      <button className={primary} onClick={() => { if (confirmDiscardDrafts()) { setEditing(null); setCreating(true); scrollWorkspaceToTop(); } }}>{creationLabels[kind]}</button>
    </div>
    {(creating || editing) && <Panel title={editing ? "Editar registro" : creationLabels[kind]}>
      <RecordForm key={`${definition.path}:${caseId || "all"}:${editing?.id || "new"}`} definition={definition} record={editing || undefined} caseId={caseId} onDone={() => { setEditing(null); setCreating(false); setReminderFor(null); resource.reload(); }} />
      <button type="button" className={button} onClick={closeForm}>{editing ? "Cancelar edição" : "Cancelar cadastro"}</button>
    </Panel>}
    {reminderFor && <TaskReminder key={`${reminderFor.id}:${reminderFor.revision}`} task={reminderFor} onClose={() => setReminderFor(null)} />}
    {kind === "clients" && <ClientImport onImported={resource.reload} />}
    {selectedClient && <Panel title={`Cliente 360° — ${selectedClient.name}`}>
      <p className="text-sm break-words">{[selectedClient.email, selectedClient.phone, selectedClient.tax_id].filter(Boolean).join(" · ") || "Contato não informado"}</p>
      <State loading={clientCases.loading} error={clientCases.error} empty={!clientCases.data?.items.length} />
      {clientCases.data?.items.map(row => <div key={row.id}><Link className="text-sm text-blue-300" href={`/dashboard/cases/${row.id}`}>{row.title} · {display(row.status)} → partes, agenda, documentos e honorários</Link></div>)}
      <details className="border-t border-zinc-800 pt-3"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-blue-300">Abrir arquivos do cliente</summary><div className="mt-4"><FileCenter clientId={String(selectedClient.id)} embedded /></div></details>
      <button className={button} onClick={() => setSelectedClient(null)}>Fechar visão do cliente</button>
    </Panel>}
    <Panel title={listTitles[kind]}>
      <Field label="Filtrar registros carregados"><input className={control} value={query} onChange={e => setQuery(e.target.value)} type="search" placeholder="Nome, situação ou referência" /></Field>
      <State loading={resource.loading} error={resource.error} />
      {!resource.loading && !resource.error && !items.length && <p className="text-sm text-zinc-400">{emptyMessage}</p>}
      <div className="divide-y divide-zinc-800">{items.map(row => <article key={row.id} className="py-3 flex flex-col sm:flex-row sm:flex-wrap justify-between gap-3">
        <div className="min-w-0 flex-1"><p className="text-sm font-medium break-words">{display(row[definition.columns[0]])}</p>
          <p className="text-xs text-zinc-400 mt-1 break-words">{definition.columns.slice(1).map(key => display(row[key], key)).join(" · ")}</p>
          {kind === "tasks" && <><p className="text-xs text-zinc-400 mt-1">{[row.location, row.contact].filter(Boolean).join(" · ")}</p>{row.notes && <details><summary className="min-h-11 content-center cursor-pointer text-xs text-blue-300">Orientações da diligência</summary><p className="text-sm whitespace-pre-wrap">{row.notes}</p></details>}</>}
          {row.case_id && <Link className="text-xs text-blue-300" href={`/dashboard/cases/${row.case_id}`}>Abrir processo</Link>}
        </div>
        <div className="flex flex-wrap items-start gap-2">
          {kind === "cases" && <Link className={primary} href={`/dashboard/cases/${row.id}`}>Abrir processo</Link>}
          {kind === "clients" && <button className={primary} onClick={() => setSelectedClient(row)}>Ver cliente</button>}
          {kind === "tasks" && <button className={primary} onClick={() => { if (confirmDiscardDrafts()) { setEditing(row); setCreating(false); scrollWorkspaceToTop(); } }}>Editar compromisso</button>}
          {kind === "library" && <button className={primary} onClick={() => { if (confirmDiscardDrafts()) { setEditing(row); setCreating(false); scrollWorkspaceToTop(); } }}>Editar referência</button>}
          {kind === "publications" && !row.acknowledged_at && <Action className={primary} run={() => api.post(`/workspace/publications/${row.id}/acknowledge`, {})} onDone={resource.reload}>Confirmar leitura</Action>}
          {["cases", "clients", "tasks"].includes(kind) && <details className="min-w-0"><summary className={`${button} cursor-pointer list-none`}>Mais ações</summary><div className="mt-2 flex flex-wrap gap-2">
            {kind === "cases" && <button className={button} onClick={() => { if (confirmDiscardDrafts()) { setEditing(row); setCreating(false); scrollWorkspaceToTop(); } }}>Editar processo</button>}
            {kind === "clients" && <button className={button} onClick={() => { if (confirmDiscardDrafts()) { setEditing(row); setCreating(false); scrollWorkspaceToTop(); } }}>Editar cliente</button>}
            {kind === "tasks" && <button className={button} onClick={() => { setReminderFor(row); scrollWorkspaceToTop(); }}>Meu lembrete</button>}
          </div></details>}
        </div>
      </article>)}</div>
      {resource.data && resource.data.items.length >= resource.data.limit && <p className="text-xs text-amber-300">Limite de carregamento atingido. Use a busca geral para localizar outros registros.</p>}
    </Panel>
  </>;
  return embedded ? <div className="space-y-4">{content}</div> : <Page title={definition.title} subtitle={definition.subtitle}>{content}</Page>;
}
