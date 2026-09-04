"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { Action, Field, Panel, State, button, dateText, primary, useResource } from "./shared";
import { display, type Row } from "./records";

type Analysis = Row & {
  status: string;
  revision: number;
  classifications?: Array<{ document_id: string; category: string; confidence: number; source_ids: string[] }>;
  timeline?: Array<{ id: string; event_date?: string; description: string; source_ids: string[] }>;
  contradiction_groups?: Array<{ id: string; topic: string; explanation: string; source_ids: string[] }>;
  limitations?: string[];
  coverage?: { documents: number; source_characters: number; total_content_characters: number; truncated: boolean };
  error?: string;
  sources: Array<{ document_id: string; title: string; version: number }>;
};

export function DocumentIntelligence({ caseId, documents }: { caseId: string; documents: Row[] }) {
  const analyses = useResource<Analysis[]>(`/engagement/cases/${caseId}/document-intelligence`);
  const [selected, setSelected] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [partialAcknowledged, setPartialAcknowledged] = useState<Record<string, boolean>>({});
  const usable = documents.filter(document => Boolean(document.content_text));

  async function review(item: Analysis, decision: "approve" | "reject") {
    if (decision === "approve" && item.coverage?.truncated && !partialAcknowledged[item.id]) {
      window.alert("Confirme que a análise cobre apenas parte do conteúdo antes de aprovar.");
      return;
    }
    const note = window.prompt(
      decision === "approve" ? "Registre o que foi conferido" : "Registre o motivo da rejeição",
    )?.trim();
    if (!note) return;
    await api.post(`/engagement/cases/${caseId}/document-intelligence/${item.id}/review`, {
      decision, note, expected_revision: item.revision,
      acknowledge_partial: Boolean(partialAcknowledged[item.id]),
    });
    analyses.reload();
  }

  return <Panel title="Inteligência documental" description="Classifica anexos, monta a linha do tempo probatória e aponta divergências com referência ao documento. Nada é aprovado automaticamente.">
    <div className="space-y-3 rounded-xl border border-zinc-800 p-4">
      <fieldset className="space-y-2"><legend className="text-sm font-medium">Documentos com texto disponível</legend>
        {usable.map(document => <label key={document.id} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={selected.includes(document.id)} onChange={event => setSelected(current => event.target.checked ? [...current, document.id].slice(0, 10) : current.filter(id => id !== document.id))} /> <span>{document.title}</span></label>)}
        {!usable.length && <p className="text-sm text-zinc-400">Envie ou processe ao menos um documento com texto antes de analisar.</p>}
      </fieldset>
      <Field label="Confirmação"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /> <span>Autorizo o envio destes documentos ao provedor de IA configurado.</span></Field>
      <Action className={primary} run={async () => {
        if (!selected.length || !consent) throw new Error("Selecione os documentos e confirme a autorização.");
        await api.post(`/engagement/cases/${caseId}/document-intelligence`, { request_id: crypto.randomUUID(), document_ids: selected, consent: true });
        setSelected([]); setConsent(false); analyses.reload();
      }}>Analisar documentos selecionados</Action>
    </div>
    <State loading={analyses.loading} error={analyses.error} empty={!analyses.data?.length} emptyText="Nenhuma análise documental registrada." />
    <div className="space-y-4">{analyses.data?.map(item => <article key={item.id} className="space-y-3 rounded-xl border border-zinc-800 p-4">
      <p className="text-xs text-zinc-400">{display(item.status)} · {dateText(item.created_at)} · {item.sources.map(source => `${source.title} v${source.version}`).join(" · ")}</p>
      {item.error && <p role="alert" className="text-sm text-amber-300">{item.error}</p>}
      {!!item.classifications?.length && <section><h3 className="text-sm font-medium">Classificação dos anexos</h3><ul className="mt-1 space-y-1 text-sm text-zinc-300">{item.classifications.map(row => <li key={row.document_id}>{item.sources.find(source => source.document_id === row.document_id)?.title || row.document_id}: {display(row.category)} · {Math.round(row.confidence * 100)}% · fontes {row.source_ids.join(", ")}</li>)}</ul></section>}
      {!!item.timeline?.length && <section><h3 className="text-sm font-medium">Linha do tempo probatória</h3><ol className="mt-1 space-y-2">{item.timeline.map(row => <li key={row.id} className="text-sm"><span className="text-zinc-400">{row.event_date ? dateText(row.event_date) : "Data não determinada"}</span> · {row.description}<span className="block text-xs text-zinc-500">Fontes: {row.source_ids.join(", ")}</span></li>)}</ol></section>}
      {!!item.contradiction_groups?.length && <section><h3 className="text-sm font-medium text-amber-200">Divergências para conferir</h3><div className="mt-1 space-y-2">{item.contradiction_groups.map(row => <p key={row.id} className="text-sm"><strong>{row.topic}</strong>: {row.explanation}<span className="block text-xs text-zinc-500">Fontes: {row.source_ids.join(", ")}</span></p>)}</div></section>}
      {!!item.limitations?.length && <p className="text-xs text-zinc-400">Limitações: {item.limitations.join(" · ")}</p>}
      {item.coverage && <p className={`text-xs ${item.coverage.truncated ? "text-amber-300" : "text-zinc-400"}`}>
        Cobertura: {item.coverage.source_characters.toLocaleString("pt-BR")} de {item.coverage.total_content_characters.toLocaleString("pt-BR")} caracteres citáveis
        {item.coverage.truncated ? " · análise parcial" : " · conteúdo integral disponível ao analisador"}.
      </p>}
      {item.status === "review_required" && item.coverage?.truncated && <label className="flex min-h-11 items-center gap-3 rounded-lg border border-amber-500/40 p-3 text-sm text-amber-100">
        <input type="checkbox" checked={Boolean(partialAcknowledged[item.id])} onChange={event => setPartialAcknowledged(current => ({ ...current, [item.id]: event.target.checked }))} />
        <span>Estou ciente de que esta análise é parcial e conferi essa limitação.</span>
      </label>}
      {item.status === "review_required" && <div className="flex flex-wrap gap-2"><Action className={primary} run={() => review(item, "approve")}>Aprovar após conferência</Action><Action className={button} run={() => review(item, "reject")}>Rejeitar análise</Action></div>}
    </article>)}</div>
  </Panel>;
}
