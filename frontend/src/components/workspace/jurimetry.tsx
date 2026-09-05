"use client";

import { useRef, useState, type FormEvent } from "react";

import { api } from "@/lib/api-client";
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

type Options = {
  provider_available: boolean;
  source_name: string;
  source_documentation_url: string;
  tribunals: string[];
  sample_limits: Array<50 | 100 | 200>;
  max_period_days: number;
};

type Filters = {
  date_from: string;
  date_to: string;
  degree?: string;
  class_code?: number;
  subject_code?: number;
  court_unit_code?: number;
};

type Bucket = { label: string; code: string | null; count: number; sample_share_percent: number };
type Analysis = {
  request_id: string;
  snapshot_id: string | null;
  persisted: boolean;
  tribunal: string;
  filters: Filters;
  sample_limit: 50 | 100 | 200;
  sample_size: number;
  total_matches: number | null;
  total_relation: "eq" | "gte" | "unknown";
  source_name: string;
  source_url: string;
  queried_at: string;
  source_updated_at: string | null;
  universe: string;
  metrics: {
    filings_by_month: Bucket[];
    cases_by_degree: Bucket[];
    cases_by_class: Bucket[];
    subject_occurrences: Bucket[];
    cases_by_court_unit: Bucket[];
    coverage: Record<string, number>;
  };
  limitations: string[];
};

type SnapshotList = { items: Analysis[] };

const filterLabels: Record<keyof Filters, string> = {
  date_from: "Ajuizamento a partir de",
  date_to: "Ajuizamento até",
  degree: "Grau",
  class_code: "Código da classe",
  subject_code: "Código do assunto",
  court_unit_code: "Código do órgão julgador",
};

const coverageLabels: Record<string, string> = {
  filing_date: "Data de ajuizamento",
  degree: "Grau",
  case_class: "Classe",
  subjects: "Assuntos",
  court_unit: "Órgão julgador",
  source_update: "Atualização da fonte",
};

function optionalInteger(value: FormDataEntryValue | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function totalText(analysis: Analysis) {
  if (analysis.total_matches == null || analysis.total_relation === "unknown") return "Total do universo não informado pela fonte";
  return `${analysis.total_relation === "gte" ? "Pelo menos " : ""}${analysis.total_matches.toLocaleString("pt-BR")} processos encontrados pela fonte`;
}

function tribunalLabel(alias: string) {
  const upper = alias.toUpperCase();
  if (upper === "STJ") return "STJ — Superior Tribunal de Justiça";
  if (upper === "STM") return "STM — Superior Tribunal Militar";
  if (upper === "TSE") return "TSE — Tribunal Superior Eleitoral";
  if (upper === "TST") return "TST — Tribunal Superior do Trabalho";
  if (/^TJ[A-Z]{2,3}$/.test(upper)) return `${upper} — Tribunal de Justiça (${upper.slice(2)})`;
  if (/^TRE-[A-Z]{2,3}$/.test(upper)) return `${upper} — Tribunal Regional Eleitoral (${upper.slice(4)})`;
  if (/^TRF\d+$/.test(upper)) return `${upper} — Tribunal Regional Federal`;
  if (/^TRT\d+$/.test(upper)) return `${upper} — Tribunal Regional do Trabalho`;
  return upper;
}

function MetricGroup({ title, items }: { title: string; items: Bucket[] }) {
  return <section className="min-w-0">
    <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
    {!items.length ? <p className="mt-2 text-sm text-zinc-400">Campo não informado na amostra.</p> : <ol className="mt-2 space-y-2">
      {items.map(item => <li key={`${item.code || "sem-codigo"}-${item.label}`} className="flex min-w-0 items-start justify-between gap-3 border-b border-zinc-800/80 pb-2 text-sm">
        <span className="min-w-0 text-zinc-300">{item.label}{item.code ? <span className="block text-xs text-zinc-400">Código {item.code}</span> : null}</span>
        <span className="shrink-0 text-right text-zinc-100">{item.count.toLocaleString("pt-BR")}<span className="block text-xs text-zinc-400">{item.sample_share_percent.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% da amostra</span></span>
      </li>)}
    </ol>}
  </section>;
}

function AnalysisView({ analysis }: { analysis: Analysis }) {
  const filters = Object.entries(analysis.filters).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return <div className="space-y-5" aria-live="polite">
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-zinc-800 p-3"><p className="text-xs text-zinc-400">Amostra analisada</p><p className="mt-1 text-xl font-semibold">{analysis.sample_size.toLocaleString("pt-BR")}</p><p className="text-xs text-zinc-400">limite solicitado: {analysis.sample_limit}</p></div>
      <div className="rounded-lg border border-zinc-800 p-3 sm:col-span-2"><p className="text-xs text-zinc-400">Universo informado</p><p className="mt-1 text-sm text-zinc-200">{totalText(analysis)}</p><p className="mt-1 text-xs text-zinc-400">{analysis.universe}</p></div>
    </div>

    <section aria-label="Proveniência da consulta" className="rounded-lg border border-blue-900/70 bg-blue-950/20 p-3 text-sm">
      <p className="font-medium text-blue-100">{analysis.source_name}</p>
      <p className="mt-1 text-zinc-300">Consultado em {dateText(analysis.queried_at)}.</p>
      <p className="mt-1 text-zinc-400">Última atualização informada nos registros da amostra: {analysis.source_updated_at ? dateText(analysis.source_updated_at) : "não informada"}.</p>
      <a className="mt-2 inline-flex min-h-11 items-center text-blue-300" href={analysis.source_url} target="_blank" rel="noreferrer">Ver endpoint oficial consultado</a>
      {analysis.persisted && <p className="text-xs text-emerald-300">Snapshot imutável salvo para este escritório.</p>}
    </section>

    {analysis.sample_size === 0 ? <State empty emptyText="A fonte não retornou processos para estes filtros. Nenhum indicador foi calculado." /> : <>
      <div className="grid gap-5 md:grid-cols-2">
        <MetricGroup title="Ajuizamentos por mês" items={analysis.metrics.filings_by_month} />
        <MetricGroup title="Processos por grau" items={analysis.metrics.cases_by_degree} />
        <MetricGroup title="Processos por classe" items={analysis.metrics.cases_by_class} />
        <MetricGroup title="Ocorrências de assuntos" items={analysis.metrics.subject_occurrences} />
        <MetricGroup title="Processos por órgão julgador" items={analysis.metrics.cases_by_court_unit} />
        <section><h3 className="text-sm font-semibold text-zinc-200">Cobertura dos campos</h3><dl className="mt-2 space-y-2 text-sm">{Object.entries(analysis.metrics.coverage).map(([key, count]) => <div key={key} className="flex justify-between gap-3"><dt className="text-zinc-400">{coverageLabels[key] || key}</dt><dd>{count.toLocaleString("pt-BR")} de {analysis.sample_size.toLocaleString("pt-BR")}</dd></div>)}</dl></section>
      </div>
    </>}

    <details className="rounded-lg border border-zinc-800 p-3"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-zinc-200">Filtros e limitações</summary><div className="space-y-3 border-t border-zinc-800 pt-3 text-sm"><dl className="grid gap-2 sm:grid-cols-2">{filters.map(([key, value]) => <div key={key}><dt className="text-xs text-zinc-400">{filterLabels[key as keyof Filters] || key}</dt><dd className="text-zinc-300">{String(value)}</dd></div>)}</dl><ul className="list-disc space-y-2 pl-5 text-amber-200">{analysis.limitations.map(item => <li key={item}>{item}</li>)}</ul></div></details>
  </div>;
}

export function Jurimetry() {
  const options = useResource<Options>("/jurimetria/options");
  const snapshots = useResource<SnapshotList>("/jurimetria/snapshots?limit=20");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<{ fingerprint: string; id: string } | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const filters: Filters = {
      date_from: String(values.get("date_from") || ""),
      date_to: String(values.get("date_to") || ""),
      degree: String(values.get("degree") || "").trim() || undefined,
      class_code: optionalInteger(values.get("class_code")),
      subject_code: optionalInteger(values.get("subject_code")),
      court_unit_code: optionalInteger(values.get("court_unit_code")),
    };
    const input = {
      tribunal: String(values.get("tribunal") || ""),
      filters,
      sample_limit: Number(values.get("sample_limit")),
      persist_snapshot: values.get("persist_snapshot") === "on",
    };
    const fingerprint = JSON.stringify(input);
    if (request.current?.fingerprint !== fingerprint) request.current = { fingerprint, id: crypto.randomUUID() };
    setBusy(true); setError("");
    try {
      const result = await api.post<Analysis>("/jurimetria/analyses", { request_id: request.current.id, ...input });
      setAnalysis(result);
      request.current = null;
      if (result.persisted) snapshots.reload();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  const unavailable = options.data && !options.data.provider_available;
  return <Page title="Jurimetria descritiva" subtitle="Explore metadados públicos do DataJud com filtros transparentes. Esta área descreve a amostra consultada e nunca prevê o resultado de processos.">
    <Panel title="Nova consulta" description={`Informe um período de até ${options.data?.max_period_days || 366} dias. Filtros vazios não serão aplicados.`}>
      <State loading={options.loading} error={options.error} />
      {options.error && <button type="button" className={button} onClick={options.reload}>Tentar carregar a configuração novamente</button>}
      {unavailable && <State error="DataJud está indisponível ou não configurado. Nenhum número será exibido até a fonte voltar." />}
      <form className="space-y-4" onSubmit={submit}>
        <fieldset disabled={busy || options.loading || Boolean(options.error) || Boolean(unavailable)} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Tribunal"><select className={control} name="tribunal" required defaultValue=""><option value="">Selecione o tribunal…</option>{options.data?.tribunals.map(tribunal => <option key={tribunal} value={tribunal}>{tribunalLabel(tribunal)}</option>)}</select></Field>
            <Field label="Ajuizamento a partir de"><input className={control} name="date_from" type="date" required /></Field>
            <Field label="Ajuizamento até"><input className={control} name="date_to" type="date" required /></Field>
          </div>
          <details className="rounded-lg border border-zinc-800 p-3"><summary className="min-h-11 cursor-pointer content-center text-sm font-medium text-blue-300">Adicionar filtros oficiais</summary><div className="grid gap-3 border-t border-zinc-800 pt-3 sm:grid-cols-2 lg:grid-cols-4"><Field label="Grau"><input className={control} name="degree" maxLength={16} pattern="[A-Za-z0-9_-]+" placeholder="Ex.: G1" /></Field><Field label="Código da classe TPU"><input className={control} name="class_code" type="number" min="1" step="1" inputMode="numeric" /></Field><Field label="Código do assunto TPU"><input className={control} name="subject_code" type="number" min="1" step="1" inputMode="numeric" /></Field><Field label="Código do órgão julgador"><input className={control} name="court_unit_code" type="number" min="1" step="1" inputMode="numeric" /></Field></div></details>
          <div className="grid items-end gap-3 sm:grid-cols-2"><Field label="Tamanho máximo da amostra"><select className={control} name="sample_limit" defaultValue="100">{(options.data?.sample_limits || [50, 100, 200]).map(limit => <option key={limit} value={limit}>{limit} processos</option>)}</select></Field><Field label="Salvar snapshot desta consulta"><input name="persist_snapshot" type="checkbox" /></Field></div>
          <p className="text-xs text-amber-300">Os resultados dependem da cobertura e atualização do DataJud. Use-os como descrição da amostra, não como estimativa de êxito, prazo ou estratégia.</p>
          <State error={error} />
          <button className={primary}>{busy ? "Consultando fonte oficial…" : "Executar análise descritiva"}</button>
        </fieldset>
      </form>
    </Panel>

    {analysis && <Panel title="Resultado da consulta" status={analysis.persisted ? "Snapshot salvo" : "Não salvo"}><AnalysisView analysis={analysis} /></Panel>}

    <Panel title="Snapshots salvos" description="Registros imutáveis do resultado e das limitações observadas no momento da consulta." collapsibleOnMobile>
      <State loading={snapshots.loading} error={snapshots.error} empty={!snapshots.loading && !snapshots.error && !snapshots.data?.items.length} emptyText="Nenhum snapshot foi salvo neste escritório." />
      {snapshots.error && <button type="button" className={button} onClick={snapshots.reload}>Tentar carregar os snapshots novamente</button>}
      <div className="divide-y divide-zinc-800">{snapshots.data?.items.map(item => <article key={item.snapshot_id || item.request_id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-medium">{item.tribunal.toUpperCase()} · {item.sample_size.toLocaleString("pt-BR")} processos na amostra</p><p className="text-xs text-zinc-400">Consultado em {dateText(item.queried_at)} · período {item.filters.date_from} a {item.filters.date_to}</p></div><button type="button" className={button} onClick={() => setAnalysis(item)}>Abrir snapshot</button></article>)}</div>
    </Panel>

    {options.data && <a className="inline-flex min-h-11 items-center text-sm text-blue-300" href={options.data.source_documentation_url} target="_blank" rel="noreferrer">Documentação oficial do DataJud</a>}
  </Page>;
}
