"use client";

import { useMemo, useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { Field, Panel, State, button, control, errorText, primary, useResource } from "./shared";
import type { List, Row } from "./records";

type Snapshot = { document_id: string; version: number; sha256: string };
type Source = { id: string; document_id?: string; title: string; version?: number; page?: number; paragraph: number; locator: string; excerpt: string };
type MatrixItem = { id: string; statement: string; status: "supported" | "conflicting" | "unverified" | "missing"; source_ids: string[]; review_note: string; human_review_required: true };
type Matrix = { facts: MatrixItem[]; evidence: MatrixItem[]; legal_bases: MatrixItem[]; requests: MatrixItem[]; gaps: string[]; conflicts: string[]; limitations: string[]; human_review_required: true };
type MatrixResult = { matrix: Matrix; snapshots: Snapshot[]; sources: Source[]; coverage: { source_characters: number; total_content_characters: number; truncated: boolean }; source_query: string; provider: string; model: string; saved: false };
type DraftResult = { title: string; content_markdown: string; verification: { verdict: "blocked" | "needs_review"; summary: string; issues: { severity: "high" | "medium" | "low"; category: string; message: string; source_ids: string[] }[] }; sources: Source[]; generator_model: string; verifier_model: string; model_independent: boolean; saved: false };

const sectionNames = { facts: "Fatos", evidence: "Provas", legal_bases: "Fundamentos", requests: "Pedidos" } as const;
const statusNames = { supported: "Com fonte", conflicting: "Conflitante", unverified: "Não verificado", missing: "Ausente" } as const;

export function LegalAiWorkbench({ caseId, onSaved }: { caseId?: string; onSaved: () => void }) {
  const cases = useResource<List>(caseId ? null : "/workspace/cases?limit=200");
  const [selectedCase, setSelectedCase] = useState(caseId || "");
  const documents = useResource<List>(selectedCase ? `/workspace/documents?case_id=${encodeURIComponent(selectedCase)}&limit=50` : null);
  const [documentIds, setDocumentIds] = useState<string[]>([]);
  const [sourceQuery, setSourceQuery] = useState("Organize os fatos, as provas, os fundamentos jurídicos confirmados e os pedidos possíveis, indicando lacunas e conflitos.");
  const [matrixConsent, setMatrixConsent] = useState(false); const [matrixResult, setMatrixResult] = useState<MatrixResult | null>(null);
  const [approvedIds, setApprovedIds] = useState<string[]>([]); const [pieceType, setPieceType] = useState("initial_petition");
  const [addressing, setAddressing] = useState("Juízo competente, a confirmar pelo advogado.");
  const [draftInstructions, setDraftInstructions] = useState("Prepare uma minuta objetiva sem suprir lacunas nem criar fundamentos.");
  const [draftConsent, setDraftConsent] = useState(false); const [draft, setDraft] = useState<DraftResult | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const sources = useMemo(() => new Map(matrixResult?.sources.map(source => [source.id, source]) || []), [matrixResult]);
  const approvedFacts = approvedIds.some(id => id.startsWith("F")); const approvedRequests = approvedIds.some(id => id.startsWith("P"));

  function resetAnalysis() { setMatrixResult(null); setApprovedIds([]); setDraft(null); setMatrixConsent(false); setDraftConsent(false); setNotice(""); }
  function toggleDocument(id: string) {
    setDocumentIds(current => current.includes(id) ? current.filter(item => item !== id) : current.length < 5 ? [...current, id] : current);
    resetAnalysis();
  }
  async function analyze(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.post<MatrixResult>(`/engagement/cases/${selectedCase}/evidence-matrix`, {
        document_ids: documentIds, instructions: sourceQuery, consent: matrixConsent,
      });
      setMatrixResult(result); setApprovedIds([]); setDraft(null); setMatrixConsent(false);
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  async function generateDraft() {
    if (!matrixResult) return;
    setBusy(true); setError(""); setNotice("");
    try {
      setDraft(await api.post<DraftResult>(`/engagement/cases/${selectedCase}/guided-draft`, {
        document_ids: documentIds, snapshots: matrixResult.snapshots, source_query: matrixResult.source_query,
        matrix: matrixResult.matrix, approved_item_ids: approvedIds, piece_type: pieceType,
        addressing, instructions: draftInstructions, consent: draftConsent,
      }));
      setDraftConsent(false);
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  async function saveDraft() {
    if (!draft) return;
    setBusy(true); setError("");
    try {
      await api.post<Row>("/workspace/documents", {
        title: draft.title, case_id: selectedCase, kind: "document", document_type: "petition",
        content_text: draft.content_markdown, content_format: "markdown",
      });
      setNotice("Minuta salva como rascunho. Ela ainda precisa passar por edição, revisão e aprovação humana."); onSaved();
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }

  return <div className="space-y-4">
    <Panel title="1. Montar matriz de evidências" description="A IA só pode usar os documentos selecionados e mantém cada conclusão ligada ao trecho original.">
      <form className="space-y-3" onSubmit={analyze}><fieldset className="space-y-3" disabled={busy}>
        {!caseId && <Field label="Processo"><select className={control} required value={selectedCase} onChange={event => { setSelectedCase(event.target.value); setDocumentIds([]); resetAnalysis(); }}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>}
        <State loading={documents.loading} error={cases.error || documents.error} empty={Boolean(selectedCase && !documents.loading && !documents.data?.items.length)} />
        {documents.data?.items.length ? <fieldset><legend className="mb-2 text-sm font-medium">Documentos citáveis — escolha até 5</legend><div className="grid gap-2 sm:grid-cols-2">{documents.data.items.map(row => <label key={row.id} className="flex min-h-11 min-w-0 items-start gap-3 rounded-lg border border-zinc-800 p-3 text-sm"><input className="mt-1" type="checkbox" checked={documentIds.includes(row.id)} disabled={!documentIds.includes(row.id) && documentIds.length >= 5} onChange={() => toggleDocument(row.id)} /><span className="min-w-0 break-words"><strong className="block">{row.title}</strong><span className="text-xs text-zinc-400">versão {row.current_version} · {row.filename || "texto interno"}</span></span></label>)}</div></fieldset> : null}
        <Field label="Objetivo da análise"><textarea className={control} rows={3} minLength={5} maxLength={4000} value={sourceQuery} onChange={event => { setSourceQuery(event.target.value); resetAnalysis(); }} /></Field>
        <label className="flex min-h-11 items-start gap-3 text-sm"><input className="mt-1" type="checkbox" checked={matrixConsent} onChange={event => setMatrixConsent(event.target.checked)} />Autorizo o envio destes documentos para esta análise e revisarei cada item antes de usá-lo.</label>
        <button className={primary} disabled={!selectedCase || !documentIds.length || !matrixConsent}>{busy ? "Analisando…" : "Gerar matriz para revisão"}</button>
      </fieldset></form>
    </Panel>

    {matrixResult && <Panel title="2. Revisar e aprovar a base da minuta" description="Marque somente itens sustentados que você conferiu. Conflitos, lacunas e itens sem fonte ficam fora da geração.">
      <p className="text-xs text-zinc-400">{matrixResult.coverage.truncated ? "A análise usou uma seleção do conteúdo. Confira os documentos originais antes de usar o resultado." : "Confira o resultado nos documentos originais antes de usar."}</p>
      {(Object.keys(sectionNames) as Array<keyof typeof sectionNames>).map(section => <section key={section} className="min-w-0 space-y-2"><h3 className="text-sm font-semibold">{sectionNames[section]}</h3>{matrixResult.matrix[section].length ? matrixResult.matrix[section].map(item => <article key={item.id} className="min-w-0 rounded-lg border border-zinc-800 p-3"><label className="flex min-w-0 items-start gap-3"><input aria-label={`Aprovar ${item.id}`} className="mt-1" type="checkbox" disabled={item.status !== "supported"} checked={approvedIds.includes(item.id)} onChange={event => setApprovedIds(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} /><span className="min-w-0 break-words text-sm"><strong>{item.id} · {statusNames[item.status]}</strong><span className="mt-1 block">{item.statement}</span><span className="mt-1 block text-xs text-zinc-400">{item.review_note}</span></span></label>{item.source_ids.map(id => { const source = sources.get(id); return source ? <details key={id} className="mt-2 min-w-0 break-words text-xs"><summary className="min-h-9 cursor-pointer content-center text-blue-300">[{id}] {source.title} · {source.locator}</summary><p className="whitespace-pre-wrap break-words rounded bg-zinc-950 p-2 text-zinc-300">{source.excerpt}</p></details> : null; })}</article>) : <p className="text-sm text-zinc-500">Nenhum item.</p>}</section>)}
      {(matrixResult.matrix.gaps.length > 0 || matrixResult.matrix.conflicts.length > 0) && <div className="grid gap-3 sm:grid-cols-2"><section className="rounded-lg border border-amber-900 p-3"><h3 className="text-sm font-semibold text-amber-200">Lacunas</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-zinc-300">{matrixResult.matrix.gaps.map(item => <li key={item}>{item}</li>)}</ul></section><section className="rounded-lg border border-amber-900 p-3"><h3 className="text-sm font-semibold text-amber-200">Conflitos</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-zinc-300">{matrixResult.matrix.conflicts.map(item => <li key={item}>{item}</li>)}</ul></section></div>}
      <div className="grid gap-3 sm:grid-cols-2"><Field label="Tipo de peça"><select className={control} value={pieceType} onChange={event => setPieceType(event.target.value)}><option value="initial_petition">Petição inicial</option><option value="defense">Contestação ou defesa</option><option value="intermediate_petition">Manifestação intermediária</option></select></Field><Field label="Endereçamento conferido"><input className={control} minLength={2} maxLength={1000} value={addressing} onChange={event => setAddressing(event.target.value)} /></Field></div>
      <Field label="Orientações de redação"><textarea className={control} rows={3} minLength={5} maxLength={4000} value={draftInstructions} onChange={event => setDraftInstructions(event.target.value)} /></Field>
      <label className="flex min-h-11 items-start gap-3 text-sm"><input className="mt-1" type="checkbox" checked={draftConsent} onChange={event => setDraftConsent(event.target.checked)} />Revisei os fatos e pedidos marcados e autorizo a geração da minuta com uma segunda verificação automática.</label>
      <button type="button" className={primary} disabled={busy || !approvedFacts || !approvedRequests || !draftConsent || addressing.length < 2 || draftInstructions.length < 5} onClick={generateDraft}>{busy ? "Gerando e verificando…" : "Gerar minuta e verificar"}</button>
    </Panel>}

    {draft && <Panel title="3. Minuta e parecer automático" description="O segundo passe procura inconsistências; ele não substitui a aprovação de um advogado.">
      <div className={`rounded-lg border p-3 ${draft.verification.verdict === "blocked" ? "border-red-800 bg-red-950/20" : "border-amber-800 bg-amber-950/20"}`}><p className="text-sm font-semibold">{draft.verification.verdict === "blocked" ? "Verificação bloqueou o uso sem correções" : "Verificação concluída — revisão humana pendente"}</p><p className="mt-1 text-sm">{draft.verification.summary}</p><p className="mt-1 text-xs text-zinc-400">Gerador: {draft.generator_model} · verificador: {draft.verifier_model}{draft.model_independent ? " (modelo distinto)" : " (segunda passagem no mesmo modelo)"}</p></div>
      {draft.verification.issues.length > 0 && <ul className="space-y-2">{draft.verification.issues.map((issue, index) => <li key={`${issue.category}:${index}`} className="rounded-lg border border-zinc-800 p-3 text-sm"><strong className={issue.severity === "high" ? "text-red-300" : issue.severity === "medium" ? "text-amber-300" : "text-blue-300"}>{issue.severity === "high" ? "Alta" : issue.severity === "medium" ? "Média" : "Baixa"}</strong> · {issue.message}</li>)}</ul>}
      <pre className="max-h-[70dvh] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-950 p-4 font-sans text-sm leading-relaxed">{draft.content_markdown}</pre>
      <p className="text-xs text-amber-300">Salvar cria somente um rascunho. A peça ainda deve ser editada e passar pelo fluxo Revisar → Aprovar → Versão final.</p>
      <button type="button" className={primary} disabled={busy || Boolean(notice)} onClick={saveDraft}>{busy ? "Salvando…" : "Salvar como rascunho"}</button>
    </Panel>}
    <State error={error} />{notice && <p role="status" className="rounded-lg border border-emerald-800 p-3 text-sm text-emerald-200">{notice}</p>}
  </div>;
}
