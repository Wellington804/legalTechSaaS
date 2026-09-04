"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Action, Panel, State, button, control, dateText, primary, useResource } from "@/components/workspace/shared";

type EvaluationCase = { id: string; name: string; legal_area: string; version: number; status: string; revision: number; reviewed_at?: string };
type Metric = { numerator: number; denominator: number; rate?: number; status: string };
type Run = { id: string; status: string; provider: string; model: string; case_count: number; aggregate_metrics?: Record<string, Metric>; error?: string; created_at: string; results?: Array<{ id: string; status: string; case_id: string; metrics?: Record<string, Metric>; error?: string }> };

const metricNames: Record<string, string> = {
  citation_fidelity: "Fidelidade das citações",
  omissions: "Omissões",
  contradictions: "Contradições",
  hallucinations: "Alucinações",
};

function Metrics({ values }: { values?: Record<string, Metric> }) {
  if (!values) return null;
  return <dl className="grid gap-2 sm:grid-cols-2">{Object.entries(values).map(([key, value]) => <div key={key} className="rounded-lg bg-zinc-950 p-3"><dt className="text-xs text-zinc-400">{metricNames[key] || key}</dt><dd className="text-sm font-medium">{value.status === "unknown" || value.rate == null ? "Sem denominador" : `${Math.round(value.rate * 100)}%`} <span className="font-normal text-zinc-500">({value.numerator}/{value.denominator})</span></dd></div>)}</dl>;
}

export function AIQualityLab() {
  const cases = useResource<EvaluationCase[]>("/engagement/assistant/evaluations/cases");
  const runs = useResource<Run[]>("/engagement/assistant/evaluations/runs");
  const [payload, setPayload] = useState("");
  const [detail, setDetail] = useState<Run | null>(null);

  async function review(item: EvaluationCase, decision: "approve" | "reject") {
    const note = window.prompt(decision === "approve" ? "Descreva a revisão jurídica realizada" : "Motivo da rejeição")?.trim();
    if (!note) return;
    await api.post(`/engagement/assistant/evaluations/cases/${item.id}/review`, { decision, note, expected_revision: item.revision });
    cases.reload();
  }

  return <Panel title="Laboratório de qualidade jurídica" description="Corpus ouro com peças revisadas e benchmarks separados de citação, omissão, contradição e alucinação.">
    <details className="rounded-xl border border-zinc-800 p-4"><summary className="cursor-pointer text-sm font-medium">Importar casos de referência em JSON</summary><div className="mt-3 space-y-3"><p className="text-xs text-zinc-400">Cada caso deve conter nome, área, versão e content com draft_request, reference_draft, fontes, perguntas e respostas ouro. A peça de referência nunca é enviada ao modelo avaliado.</p><textarea className={control} rows={8} value={payload} onChange={event => setPayload(event.target.value)} placeholder={'{"cases":[{"name":"...","legal_area":"...","version":1,"content":{"draft_request":"...","reference_draft":"...","sources":[],"questions":[],"gold_answers":[]}}]}'} /><Action className={primary} run={async () => { const parsed = JSON.parse(payload); await api.post("/engagement/assistant/evaluations/cases/import", parsed); setPayload(""); cases.reload(); }}>Validar e importar</Action></div></details>
    <State loading={cases.loading} error={cases.error} empty={!cases.data?.length} emptyText="Nenhum caso de referência cadastrado." />
    <div className="space-y-2">{cases.data?.map(item => <article key={item.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-zinc-800 p-3"><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{item.name} · v{item.version}</p><p className="text-xs text-zinc-400">{item.legal_area} · {item.status}{item.reviewed_at ? ` · revisado em ${dateText(item.reviewed_at)}` : ""}</p></div>{item.status === "draft" && <><Action className={primary} run={() => review(item, "approve")}>Aprovar corpus</Action><Action className={button} run={() => review(item, "reject")}>Rejeitar</Action></>}</article>)}</div>
    <div className="flex flex-wrap gap-2"><Action className={primary} run={async () => { await api.post("/engagement/assistant/evaluations/runs", { request_id: crypto.randomUUID() }); runs.reload(); }}>Executar corpus aprovado</Action><Action run={async () => { cases.reload(); runs.reload(); }}>Atualizar resultados</Action></div>
    <State loading={runs.loading} error={runs.error} empty={!runs.data?.length} emptyText="Nenhum benchmark executado." />
    <div className="space-y-3">{runs.data?.map(item => <article key={item.id} className="space-y-2 rounded-xl border border-zinc-800 p-4"><p className="text-sm font-medium">{item.status} · {item.case_count} casos · {dateText(item.created_at)}</p><p className="text-xs text-zinc-400">{item.provider} / {item.model}</p>{item.error && <p role="alert" className="text-sm text-amber-300">{item.error}</p>}<Metrics values={item.aggregate_metrics} /><Action run={async () => setDetail(await api.get<Run>(`/engagement/assistant/evaluations/runs/${item.id}`))}>Ver resultados por caso</Action></article>)}</div>
    {detail && <section className="space-y-2 rounded-xl border border-blue-800 bg-blue-950/20 p-4" aria-label="Resultados detalhados"><div className="flex items-center justify-between gap-2"><h3 className="text-sm font-medium">Resultados por caso</h3><button className={button} onClick={() => setDetail(null)}>Fechar</button></div>{detail.results?.map(result => <article key={result.id} className="border-t border-zinc-800 pt-2"><p className="text-xs text-zinc-400">{result.case_id} · {result.status}</p>{result.error && <p className="text-sm text-amber-300">{result.error}</p>}<Metrics values={result.metrics} /></article>)}</section>}
  </Panel>;
}
