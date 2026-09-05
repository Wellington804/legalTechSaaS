"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { CheckCircle2, Circle, ExternalLink, Plus, Search, ShieldCheck, Trash2 } from "lucide-react";

import { Page, Panel, State, button, control, dateText, primary } from "@/components/workspace/shared";
import {
  type OabEnrollment,
  type OabEnrollmentStatus,
  type OabEnrollmentType,
  useOabStore,
} from "@/store/useOabStore";


const ENROLLMENT_TYPES: { value: OabEnrollmentType; label: string }[] = [
  { value: "principal", label: "Inscrição principal" },
  { value: "supplementary", label: "Inscrição suplementar" },
  { value: "transfer", label: "Transferência de inscrição" },
  { value: "other", label: "Outro processo de inscrição" },
];

const STATUSES: { value: OabEnrollmentStatus; label: string }[] = [
  { value: "planning", label: "Planejando" },
  { value: "gathering", label: "Organizando informações" },
  { value: "submitted", label: "Protocolado — informado por você" },
  { value: "awaiting_response", label: "Aguardando retorno — informado por você" },
  { value: "completed", label: "Concluído — informado por você" },
  { value: "paused", label: "Pausado" },
];

const labelFor = <T extends string>(items: { value: T; label: string }[], value: T) =>
  items.find(item => item.value === value)?.label || value;

function EnrollmentCard({ enrollment }: { enrollment: OabEnrollment }) {
  const { saving, updateEnrollment, addChecklistItem, updateChecklistItem, deleteChecklistItem } = useOabStore();
  const [status, setStatus] = useState(enrollment.status);
  const [protocol, setProtocol] = useState(enrollment.protocol || "");
  const checklistRequestId = useRef(crypto.randomUUID());
  const completed = enrollment.checklist.filter(item => item.is_completed).length;
  const progress = enrollment.checklist.length ? Math.round((completed / enrollment.checklist.length) * 100) : 0;

  async function saveProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await updateEnrollment(enrollment, { status, protocol: protocol.trim() || null }).catch(() => undefined);
  }

  async function addItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await addChecklistItem(enrollment.id, checklistRequestId.current, String(data.get("title") || ""), String(data.get("notes") || ""))
      .then(() => { checklistRequestId.current = crypto.randomUUID(); form.reset(); })
      .catch(() => undefined);
  }

  return (
    <article className="min-w-0 space-y-5 rounded-xl border border-zinc-800 bg-zinc-900/25 p-4 md:p-5">
      <header className="flex min-w-0 flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-zinc-100">OAB/{enrollment.uf}</h3>
            <span className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs text-zinc-300">
              {labelFor(ENROLLMENT_TYPES, enrollment.enrollment_type)}
            </span>
          </div>
          <p className="mt-1 text-sm text-zinc-400">{labelFor(STATUSES, enrollment.status)}</p>
        </div>
        <a className={button} href={enrollment.source_url} target="_blank" rel="noopener noreferrer">
          Abrir fonte da UF <ExternalLink aria-hidden="true" className="ml-2" size={16} />
        </a>
      </header>

      <div className="rounded-lg border border-blue-900/70 bg-blue-950/20 p-3 text-sm text-blue-100">
        <p>{enrollment.source_notice}</p>
        <p className="mt-2 text-xs text-blue-200/80">
          Fonte registrada em {dateText(enrollment.source_checked_at)} · versão {enrollment.source_version}
        </p>
      </div>

      <form onSubmit={saveProgress} className="space-y-3">
        <fieldset disabled={saving} className="grid min-w-0 gap-3 sm:grid-cols-2">
          <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300">
            <span>Situação do seu acompanhamento</span>
            <select className={control} value={status} onChange={event => setStatus(event.target.value as OabEnrollmentStatus)}>
              {STATUSES.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300">
            <span>Protocolo informado por você (opcional)</span>
            <input className={control} value={protocol} onChange={event => setProtocol(event.target.value)} maxLength={120} autoComplete="off" />
          </label>
        </fieldset>
        <button className={primary} disabled={saving}>
          {saving ? "Salvando…" : "Salvar acompanhamento"}
        </button>
      </form>

      <section className="space-y-3" aria-label={`Checklist de OAB/${enrollment.uf}`}>
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <h4 className="font-medium text-zinc-100">Checklist criado por você</h4>
            <p className="text-sm text-zinc-400">Copie apenas o que você conferiu na fonte oficial. O LexFlow não presume exigências.</p>
          </div>
          <p className="shrink-0 text-sm text-zinc-300">{completed} de {enrollment.checklist.length} marcados · {progress}%</p>
        </div>

        {!enrollment.checklist.length && (
          <p className="rounded-lg border border-dashed border-zinc-700 p-3 text-sm text-zinc-400">
            Nenhum item adicionado. Consulte a Seccional e registre aqui somente o que se aplica ao seu caso.
          </p>
        )}

        <ul className="space-y-2">
          {enrollment.checklist.map(item => (
            <li key={item.id} className="flex min-w-0 items-start gap-3 rounded-lg border border-zinc-800 p-3">
              <button
                type="button"
                className="mt-0.5 min-h-11 min-w-11 rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-emerald-300 disabled:opacity-50"
                aria-label={item.is_completed ? `Marcar ${item.title} como pendente` : `Marcar ${item.title} como concluído`}
                disabled={saving}
                onClick={() => void updateChecklistItem(enrollment.id, item, { is_completed: !item.is_completed }).catch(() => undefined)}
              >
                {item.is_completed ? <CheckCircle2 aria-hidden="true" className="mx-auto text-emerald-400" size={20} /> : <Circle aria-hidden="true" className="mx-auto" size={20} />}
              </button>
              <div className="min-w-0 flex-1">
                <p className={`break-words text-sm font-medium ${item.is_completed ? "text-zinc-400 line-through" : "text-zinc-100"}`}>{item.title}</p>
                {item.notes && <p className="mt-1 whitespace-pre-wrap break-words text-sm text-zinc-400">{item.notes}</p>}
              </div>
              <button
                type="button"
                className="min-h-11 min-w-11 rounded-lg text-red-300/70 hover:bg-red-950/30 hover:text-red-200 disabled:opacity-50"
                aria-label={`Remover ${item.title}`}
                disabled={saving}
                onClick={() => {
                  if (window.confirm("Remover este item do seu checklist?")) {
                    void deleteChecklistItem(enrollment.id, item).catch(() => undefined);
                  }
                }}
              >
                <Trash2 aria-hidden="true" className="mx-auto" size={17} />
              </button>
            </li>
          ))}
        </ul>

        <form onSubmit={addItem} className="grid min-w-0 gap-3 rounded-lg border border-zinc-800 p-3 sm:grid-cols-2">
          <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300">
            <span>Novo item conferido na fonte</span>
            <input className={control} name="title" required minLength={1} maxLength={200} placeholder="Descreva o item sem anexar documentos" />
          </label>
          <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300">
            <span>Observação pessoal (opcional)</span>
            <input className={control} name="notes" maxLength={2000} placeholder="Ex.: conferir prazo diretamente com a Seccional" />
          </label>
          <button className={primary} disabled={saving}>
            <Plus aria-hidden="true" className="mr-2" size={16} /> {saving ? "Salvando…" : "Adicionar item"}
          </button>
        </form>
      </section>
    </article>
  );
}

export function OabEnrollmentWorkspace() {
  const { sources, enrollments, loading, saving, error, load, clearError, createEnrollment } = useOabStore();
  const [query, setQuery] = useState("");
  const [selectedUf, setSelectedUf] = useState("");
  const [notice, setNotice] = useState("");
  const enrollmentRequestId = useRef(crypto.randomUUID());

  useEffect(() => { void load(); }, [load]);

  const filteredSources = useMemo(() => {
    const normalized = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
    const value = normalized(query.trim());
    return value ? sources.filter(source => normalized(source.uf).includes(value) || normalized(source.state_name).includes(value)) : sources;
  }, [query, sources]);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setNotice("");
    await createEnrollment({
      request_id: enrollmentRequestId.current,
      uf: String(data.get("uf")),
      enrollment_type: String(data.get("enrollment_type")) as OabEnrollmentType,
      status: "planning",
      protocol: null,
    }).then(() => {
      enrollmentRequestId.current = crypto.randomUUID();
      form.reset();
      setSelectedUf("");
      setNotice("Acompanhamento criado. Agora registre apenas informações que você confirmou.");
    }).catch(() => undefined);
  }

  const directory = sources[0];

  return (
    <Page
      title="Acompanhamento de inscrição na OAB"
      subtitle="Organize seu próprio progresso e acesse fontes oficiais. Esta área não envia pedidos, consulta protocolos nem confirma exigências perante a OAB."
    >
      <div className="rounded-xl border border-amber-800/80 bg-amber-950/20 p-4 text-sm text-amber-100">
        <div className="flex items-start gap-3">
          <ShieldCheck aria-hidden="true" className="mt-0.5 shrink-0" size={19} />
          <div>
            <p className="font-medium">Use como apoio de organização, não como orientação oficial.</p>
            <p className="mt-1 text-amber-200/80">Regras, documentos, prazos e valores podem variar. Confirme tudo diretamente com a Seccional.</p>
          </div>
        </div>
      </div>

      {error && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border border-red-900 bg-red-950/30 p-3 text-sm text-red-200 sm:flex-row sm:items-center sm:justify-between">
          <span>{error}</span>
          <button type="button" className={button} onClick={() => { clearError(); void load(); }}>Tentar novamente</button>
        </div>
      )}
      {notice && <p role="status" className="rounded-lg border border-emerald-900 bg-emerald-950/20 p-3 text-sm text-emerald-200">{notice}</p>}

      <Panel title="Fontes oficiais por estado" description="Diretório nacional do Conselho Federal, com um link oficial para cada uma das 27 UFs.">
        <label className="block max-w-xl space-y-1.5 text-sm font-medium text-zinc-300">
          <span>Buscar por estado ou UF</span>
          <span className="relative block">
            <Search aria-hidden="true" className="absolute left-3 top-3.5 text-zinc-500" size={17} />
            <input className={`${control} pl-10`} type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Ex.: Minas Gerais ou MG" />
          </span>
        </label>
        <State loading={loading} empty={!loading && !error && !filteredSources.length} emptyText="Nenhuma UF corresponde à busca." />
        <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filteredSources.map(source => (
            <article key={source.uf} className="flex min-w-0 flex-col justify-between gap-3 rounded-lg border border-zinc-800 p-3">
              <div>
                <h3 className="font-medium text-zinc-100">{source.state_name} · {source.uf}</h3>
                <p className="mt-1 text-xs text-zinc-400">Fonte conferida em {dateText(source.source_checked_at)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <a className={button} href={source.official_url} target="_blank" rel="noopener noreferrer">
                  Abrir OAB/{source.uf} <ExternalLink aria-hidden="true" className="ml-2" size={15} />
                </a>
                <button type="button" className={button} onClick={() => setSelectedUf(source.uf)}>Acompanhar esta UF</button>
              </div>
            </article>
          ))}
        </div>
        {directory && (
          <div className="flex flex-wrap gap-3 border-t border-zinc-800 pt-4 text-sm">
            <a className="inline-flex min-h-11 items-center text-blue-300 hover:text-blue-200" href={directory.directory_url} target="_blank" rel="noopener noreferrer">
              Diretório nacional das Seccionais <ExternalLink aria-hidden="true" className="ml-2" size={15} />
            </a>
            <a className="inline-flex min-h-11 items-center text-blue-300 hover:text-blue-200" href={directory.provision_url} target="_blank" rel="noopener noreferrer">
              Provimento 178/2017 — transferência e inscrição suplementar <ExternalLink aria-hidden="true" className="ml-2" size={15} />
            </a>
          </div>
        )}
      </Panel>

      <Panel title="Novo acompanhamento" description="Cria um registro privado para a sua conta neste escritório.">
        <form onSubmit={create} className="grid min-w-0 gap-3 sm:grid-cols-2">
          <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300">
            <span>UF da Seccional</span>
            <select className={control} name="uf" required value={selectedUf} onChange={event => setSelectedUf(event.target.value)}>
              <option value="">Selecione uma UF</option>
              {sources.map(source => <option key={source.uf} value={source.uf}>{source.uf} · {source.state_name}</option>)}
            </select>
          </label>
          <label className="block min-w-0 space-y-1.5 text-sm font-medium text-zinc-300">
            <span>Tipo de acompanhamento</span>
            <select className={control} name="enrollment_type" required defaultValue="principal">
              {ENROLLMENT_TYPES.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <button className={primary} disabled={saving || loading}>
            <Plus aria-hidden="true" className="mr-2" size={16} /> {saving ? "Criando…" : "Criar acompanhamento"}
          </button>
        </form>
      </Panel>

      <Panel title="Meus acompanhamentos" description="Situações e protocolos abaixo são informados por você e não são sincronizados com a OAB.">
        <State loading={loading} empty={!loading && !error && !enrollments.length} emptyText="Você ainda não criou nenhum acompanhamento. Escolha uma UF acima para começar." />
        <div className="space-y-4">
          {enrollments.map(enrollment => <EnrollmentCard key={`${enrollment.id}:${enrollment.revision}`} enrollment={enrollment} />)}
        </div>
      </Panel>
    </Page>
  );
}
