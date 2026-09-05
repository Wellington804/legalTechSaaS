"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Action, Field, Panel, State, button, control, dateText, primary, useResource } from "@/components/workspace/shared";

type EvaluationCase = {
  id: string;
  name: string;
  legal_area: string;
  version: number;
  status: string;
  revision: number;
  content: {
    draft_request: string;
    reference_draft: string;
    sources: Array<{ id: string; title: string; page?: number; paragraph: number; locator: string; excerpt: string }>;
    questions: Array<{ id: string; prompt: string; required: boolean }>;
    gold_answers: Array<{ question_id: string; expected_status: "supported" | "contradicted" | "unknown"; source_ids: string[]; reviewer_note: string }>;
  };
  reviewed_at?: string;
};
type Metric = { numerator: number; denominator: number; rate?: number; status: string };
type Run = {
  id: string;
  status: string;
  provider: string;
  model: string;
  case_count: number;
  aggregate_metrics?: Record<string, Metric>;
  error?: string;
  created_at: string;
  results?: Array<{ id: string; status: string; case_id: string; metrics?: Record<string, Metric>; error?: string }>;
};

const metricNames: Record<string, string> = {
  citation_fidelity: "Fidelidade das citações",
  omissions: "Omissões",
  contradictions: "Contradições",
  hallucinations: "Informações sem fonte",
};

function Metrics({ values }: { values?: Record<string, Metric> }) {
  if (!values) return null;
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="rounded-lg bg-zinc-950 p-3">
          <dt className="text-xs text-zinc-400">{metricNames[key] || key}</dt>
          <dd className="text-sm font-medium">
            {value.status === "unknown" || value.rate == null ? "Sem base para calcular" : `${Math.round(value.rate * 100)}%`}
            <span className="ml-1 font-normal text-zinc-400">({value.numerator}/{value.denominator})</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function AIQualityLab() {
  const cases = useResource<EvaluationCase[]>("/engagement/assistant/evaluations/cases");
  const runs = useResource<Run[]>("/engagement/assistant/evaluations/runs");
  const [payload, setPayload] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [reviewing, setReviewing] = useState<EvaluationCase | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [detail, setDetail] = useState<Run | null>(null);

  function toggleCase(id: string) {
    setSelected(current => current.includes(id)
      ? current.filter(item => item !== id)
      : current.length < 5 ? [...current, id] : current);
  }

  async function submitReview(decision: "approve" | "reject") {
    if (!reviewing || !reviewNote.trim()) throw new Error("Descreva o que foi conferido antes de concluir a revisão.");
    await api.post(`/engagement/assistant/evaluations/cases/${reviewing.id}/review`, {
      decision,
      note: reviewNote.trim(),
      expected_revision: reviewing.revision,
    });
    setReviewing(null);
    setReviewNote("");
    cases.reload();
  }

  return (
    <Panel
      title="Casos de referência"
      description="Compare a IA com respostas previamente conferidas por outro advogado. Uma execução não altera documentos nem processos."
    >
      <details className="rounded-xl border border-zinc-800 p-4">
        <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium">Importar casos em JSON</summary>
        <div className="mt-3 space-y-3">
          <p className="max-w-[72ch] text-sm text-zinc-400">
            Use somente material autorizado e sem dados pessoais desnecessários. A peça de referência fica fora da pergunta enviada ao modelo.
          </p>
          <Field label="Casos de referência em JSON">
            <textarea className={control} rows={8} value={payload} onChange={event => setPayload(event.target.value)} />
          </Field>
          <Action className={primary} run={async () => {
            if (!payload.trim()) throw new Error("Cole o arquivo JSON antes de importar.");
            await api.post("/engagement/assistant/evaluations/cases/import", JSON.parse(payload));
            setPayload("");
            cases.reload();
          }}>Validar e importar</Action>
        </div>
      </details>

      <State loading={cases.loading} error={cases.error} empty={!cases.error && !cases.data?.length} emptyText="Nenhum caso de referência cadastrado." />
      {cases.error && <button type="button" className={button} onClick={cases.reload}>Tentar carregar os casos novamente</button>}
      <div className="space-y-2">
        {cases.data?.map(item => {
          const approved = item.status === "approved";
          return (
            <article key={item.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 p-3">
              <label className="flex min-h-11 min-w-0 flex-1 cursor-pointer items-center gap-3">
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  disabled={!approved || (!selected.includes(item.id) && selected.length >= 5)}
                  onChange={() => toggleCase(item.id)}
                  aria-label={`Selecionar ${item.name}, versão ${item.version}`}
                />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">{item.name} · versão {item.version}</span>
                  <span className="block text-xs text-zinc-400">
                    {item.legal_area} · {item.status}{item.reviewed_at ? ` · revisado em ${dateText(item.reviewed_at)}` : ""}
                  </span>
                </span>
              </label>
              {item.status === "draft" && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={primary} onClick={() => { setReviewing(item); setReviewNote(""); }}>Abrir revisão completa</button>
                </div>
              )}
            </article>
          );
        })}
      </div>

      {reviewing && (
        <section className="space-y-3 rounded-xl border border-blue-800 bg-blue-950/20 p-4" aria-label="Concluir revisão jurídica">
          <h3 className="text-base font-semibold">Revisão completa: {reviewing.name} · versão {reviewing.version}</h3>
          <div className="space-y-4 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-sm">
            <section><h4 className="font-medium text-zinc-100">Pedido usado no teste</h4><p className="mt-1 whitespace-pre-wrap text-zinc-300">{reviewing.content.draft_request}</p></section>
            <section><h4 className="font-medium text-zinc-100">Resposta de referência</h4><p className="mt-1 max-h-96 overflow-y-auto whitespace-pre-wrap text-zinc-300">{reviewing.content.reference_draft}</p></section>
            <section><h4 className="font-medium text-zinc-100">Perguntas e respostas esperadas</h4><ol className="mt-2 space-y-3">{reviewing.content.questions.map(question => {
              const answer = reviewing.content.gold_answers.find(item => item.question_id === question.id);
              return <li key={question.id} className="rounded-lg border border-zinc-800 p-3"><p className="font-medium text-zinc-200">{question.id} · {question.prompt}</p><p className="mt-1 text-zinc-400">Resultado esperado: {answer?.expected_status === "supported" ? "confirmado pelas fontes" : answer?.expected_status === "contradicted" ? "contradito pelas fontes" : "não confirmado"}.</p>{answer?.source_ids.length ? <p className="text-zinc-400">Fontes: {answer.source_ids.join(", ")}</p> : null}{answer?.reviewer_note && <p className="mt-1 whitespace-pre-wrap text-zinc-300">Nota: {answer.reviewer_note}</p>}</li>;
            })}</ol></section>
            <section><h4 className="font-medium text-zinc-100">Fontes conferidas</h4><ol className="mt-2 space-y-3">{reviewing.content.sources.map(source => <li key={source.id} className="rounded-lg border border-zinc-800 p-3"><p className="font-medium text-zinc-200">{source.id} · {source.title}</p><p className="text-zinc-400">{source.locator}{source.page ? ` · página ${source.page}` : ""} · parágrafo {source.paragraph}</p><p className="mt-1 whitespace-pre-wrap text-zinc-300">{source.excerpt}</p></li>)}</ol></section>
          </div>
          <Field label="Registro da revisão">
            <textarea className={control} rows={4} value={reviewNote} onChange={event => setReviewNote(event.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Action className={primary} run={() => submitReview("approve")}>Aprovar caso conferido</Action>
            <Action run={() => submitReview("reject")}>Rejeitar caso conferido</Action>
            <button type="button" className={button} onClick={() => { setReviewing(null); setReviewNote(""); }}>Cancelar</button>
          </div>
        </section>
      )}

      <section className="space-y-3 border-t border-zinc-800 pt-4" aria-labelledby="executar-corpus">
        <div>
          <h3 id="executar-corpus" className="text-sm font-semibold">Executar teste</h3>
          <p className="mt-1 text-sm text-zinc-400">Selecione de um a cinco casos aprovados. Selecionados: {selected.length}/5.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Action className={primary} run={async () => {
            if (!selected.length) throw new Error("Selecione ao menos um caso aprovado.");
            await api.post("/engagement/assistant/evaluations/runs", { request_id: crypto.randomUUID(), case_ids: selected });
            runs.reload();
          }}>Executar casos selecionados</Action>
          <Action run={async () => { cases.reload(); runs.reload(); }}>Atualizar resultados</Action>
        </div>
      </section>

      <State loading={runs.loading} error={runs.error} empty={!runs.error && !runs.data?.length} emptyText="Nenhum teste executado." />
      {runs.error && <button type="button" className={button} onClick={runs.reload}>Tentar carregar os resultados novamente</button>}
      <div className="space-y-3">
        {runs.data?.map(item => (
          <article key={item.id} className="space-y-2 rounded-xl border border-zinc-800 p-4">
            <p className="text-sm font-medium">{item.status} · {item.case_count} casos · {dateText(item.created_at)}</p>
            <p className="text-xs text-zinc-400">{item.provider} / {item.model}</p>
            {item.error && <p role="alert" className="text-sm text-amber-300">{item.error}</p>}
            <Metrics values={item.aggregate_metrics} />
            <Action run={async () => setDetail(await api.get<Run>(`/engagement/assistant/evaluations/runs/${item.id}`))}>Ver resultados por caso</Action>
          </article>
        ))}
      </div>

      {detail && (
        <section className="space-y-2 rounded-xl border border-blue-800 bg-blue-950/20 p-4" aria-label="Resultados detalhados">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium">Resultados por caso</h3>
            <button type="button" className={button} onClick={() => setDetail(null)}>Fechar</button>
          </div>
          {detail.results?.map(result => (
            <article key={result.id} className="border-t border-zinc-800 pt-2">
              <p className="text-xs text-zinc-400">{result.case_id} · {result.status}</p>
              {result.error && <p className="text-sm text-amber-300">{result.error}</p>}
              <Metrics values={result.metrics} />
            </article>
          ))}
        </section>
      )}
    </Panel>
  );
}
