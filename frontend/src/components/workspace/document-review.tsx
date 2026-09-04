"use client";

import { useState } from "react";
import { api } from "@/lib/api-client";
import { useUser } from "@/context/user-context";
import type { Row } from "./records";
import { Action, Field, Panel, State, button, control, dateText, errorText, primary, useResource } from "./shared";

type Review = { id: string; version: number; status: string; comment: string | null; created_by_name: string; created_at: string };
const labels: Record<string, string> = { draft: "Rascunho", in_review: "Em revisão", approved: "Aprovado", final: "Versão final", comment: "Comentário", reopened: "Reaberto" };

export function DocumentReview({ document, onClose, onChanged }: { document: Row; onClose: () => void; onChanged: () => void }) {
  const { user } = useUser();
  const canApprove = ["admin", "partner", "lawyer"].includes(user.permissionRole || "");
  const reviews = useResource<{ items: Review[] }>(`/workspace/documents/${document.id}/reviews`);
  const [error, setError] = useState(""); const [diff, setDiff] = useState(""); const [busy, setBusy] = useState(false);
  const record = async (status: string, comment?: string) => {
    setError("");
    try { await api.post(`/workspace/documents/${document.id}/reviews`, { status, comment: comment || null, expected_version: document.current_version }); reviews.reload(); onChanged(); }
    catch (reason) { setError(errorText(reason)); }
  };
  return <Panel title={`Revisão: ${document.title}`}>
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-medium">{labels[document.review_status || "draft"]} · versão {document.current_version}</p><p className="text-xs text-zinc-400">Uma nova edição reabre o documento como rascunho sem apagar o histórico.</p></div><button className={button} type="button" onClick={onClose}>Fechar</button></div>
    <State error={error} />
    <div className="flex flex-wrap gap-2">
      {(document.review_status || "draft") === "draft" && <Action className={primary} run={() => record("in_review")}>Enviar para revisão</Action>}
      {document.review_status === "in_review" && <>{canApprove && <Action className={primary} run={() => record("approved")}>Aprovar esta versão</Action>}<Action run={() => record("reopened", "Reaberto para correções.")}>Reabrir rascunho</Action></>}
      {document.review_status === "approved" && <>{canApprove && <Action className={primary} run={() => record("final")}>Marcar como versão final</Action>}<Action run={() => record("reopened", "Reaberto para correções.")}>Reabrir rascunho</Action></>}
      {document.review_status === "final" && <Action run={() => record("reopened", "Versão final reaberta para nova correção.")}>Reabrir documento</Action>}
    </div>
    <form className="space-y-2" onSubmit={async event => { event.preventDefault(); const form = event.currentTarget; const comment = String(new FormData(form).get("comment") || ""); setBusy(true); await record("comment", comment); setBusy(false); form.reset(); }}><Field label="Comentário da revisão"><textarea className={control} name="comment" required maxLength={5000} rows={3} /></Field><button className={button} disabled={busy}>{busy ? "Registrando…" : "Adicionar comentário"}</button></form>
    {Number(document.current_version) > 1 && <div className="space-y-2"><Action run={async () => { const result = await api.get<{ diff: string }>(`/workspace/documents/${document.id}/compare?from_version=${Number(document.current_version) - 1}&to_version=${document.current_version}`); setDiff(result.diff || "Nenhuma diferença textual."); }}>Comparar com a versão anterior</Action>{diff && <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-xs">{diff}</pre>}</div>}
    <div><h3 className="text-sm font-medium">Histórico de revisão</h3><State loading={reviews.loading} error={reviews.error} empty={!reviews.data?.items.length} emptyText="Ainda não há registros de revisão." /><div className="divide-y divide-zinc-800">{reviews.data?.items.map(item => <article key={item.id} className="py-2"><p className="text-xs text-zinc-400">{labels[item.status] || item.status} · versão {item.version} · {item.created_by_name} · {dateText(item.created_at)}</p>{item.comment && <p className="mt-1 whitespace-pre-wrap text-sm">{item.comment}</p>}</article>)}</div></div>
  </Panel>;
}
