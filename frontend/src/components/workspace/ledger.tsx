"use client";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api-client";
import { Action, Field, Page, Panel, State, button, control, dateText, errorText, money, primary, useResource } from "./shared";
import { display, type List } from "./records";
export function Ledger({ caseId, embedded = false }: { caseId?: string; embedded?: boolean }) {
  const entries = useResource<List>(`/workspace/ledger${caseId ? `?case_id=${caseId}` : ""}`); const cases = useResource<List>("/workspace/cases");
  const [kind, setKind] = useState("fee"); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [reverse, setReverse] = useState("");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const pending = entries.data?.items.filter(row => row.status === "draft") || [];
  const posted = entries.data?.items.filter(row => row.status !== "draft") || [];
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    const body = { case_id: values.get("case_id") || null, amount: values.get("amount") || "0", currency: "BRL", description: values.get("description"),
      ...(kind === "payment" ? { confirmation_reason: values.get("reason"), request_id: requestId } : { entry_type: kind, ...(kind === "time" ? { duration_minutes: Number(values.get("minutes")) } : {}) }) };
    setBusy(true); setError(""); try { await api.post(kind === "payment" ? "/workspace/ledger/payments/manual" : "/workspace/ledger", body); form.reset(); setRequestId(crypto.randomUUID()); entries.reload(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const content = <>
    <Panel title="Registrar lançamento"><form onSubmit={submit} className="space-y-3">
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Tipo"><select className={control} value={kind} onChange={e => setKind(e.target.value)}><option value="fee">Honorário</option><option value="expense">Despesa</option><option value="time">Apontamento de horas</option><option value="payment">Recebimento confirmado manualmente</option></select></Field>
        <Field label="Processo"><select key={Boolean(cases.data).toString()} className={control} name="case_id" required defaultValue={caseId || ""}><option value="">Selecione…</option>{cases.data?.items.map(row => <option key={row.id} value={row.id}>{row.title}</option>)}</select></Field>
        <Field label="Descrição"><input className={control} name="description" required minLength={2} maxLength={500} /></Field>
        <Field label="Valor (R$)"><input className={control} type="number" min={kind === "time" ? "0" : "0.01"} max="999999999999.99" step="0.01" required name="amount" /></Field>
        {kind === "time" && <Field label="Duração (minutos)"><input className={control} type="number" min="1" max="1440" required name="minutes" /></Field>}
        {kind === "payment" && <Field label="Evidência / justificativa do recebimento"><input className={control} name="reason" minLength={3} maxLength={500} required /></Field>}
      </div><State error={error || cases.error} /><button className={primary} disabled={busy}>{busy ? "Registrando…" : "Registrar lançamento"}</button>
    </form></Panel>
    <Panel title="Pendências"><State loading={entries.loading} error={entries.error} />
      {entries.data && !pending.length && <p className="text-sm text-zinc-400">Nenhum lançamento pendente de efetivação.</p>}
      <div className="divide-y divide-zinc-800">{pending.map(row => <article key={row.id} className="py-3 space-y-2">
        <div className="flex flex-wrap justify-between gap-2"><p className="text-sm">{row.description}</p><p className="font-mono text-sm">{money(row.amount)}</p></div>
        <p className="text-xs text-zinc-400">{{ fee: "Honorário", payment: "Recebimento manual", expense: "Despesa", time: "Horas" }[row.entry_type as string]} · Rascunho · {dateText(row.created_at)}{row.duration_minutes ? ` · ${row.duration_minutes} min` : ""}</p>
        {row.manual_confirmation_reason && <p className="text-xs text-zinc-400">Confirmação: {row.manual_confirmation_reason}</p>}
        <Action run={() => api.post(`/workspace/ledger/${row.id}/post`, {})} onDone={entries.reload} className={primary}>Efetivar lançamento</Action>
      </article>)}</div>
    </Panel>
    <Panel title="Lançamentos registrados"><State empty={Boolean(entries.data) && !pending.length && !posted.length} />
      <div className="divide-y divide-zinc-800">{posted.map(row => <article key={row.id} className="py-3 space-y-2">
        <div className="flex flex-wrap justify-between gap-2"><p className="text-sm">{row.description}</p><p className="font-mono text-sm">{money(row.amount)}</p></div>
        <p className="text-xs text-zinc-400">{{ fee: "Honorário", payment: "Recebimento manual", expense: "Despesa", time: "Horas" }[row.entry_type as string]} · {display(row.status)} · {dateText(row.created_at)}{row.duration_minutes ? ` · ${row.duration_minutes} min` : ""}</p>
        {row.manual_confirmation_reason && <p className="text-xs text-zinc-400">Confirmação: {row.manual_confirmation_reason}</p>}
        <div className="flex flex-wrap gap-2">{row.status === "posted" && !row.reversal_of_id && <button className={button} onClick={() => setReverse(row.id)}>Estornar com justificativa</button>}</div>
        {reverse === row.id && <form className="flex flex-wrap gap-2" onSubmit={async e => {
          e.preventDefault(); const reason = new FormData(e.currentTarget).get("reason"); setError("");
          try { await api.post(`/workspace/ledger/${row.id}/reverse`, { reason }); setReverse(""); entries.reload(); } catch (err) { setError(errorText(err)); }
        }}><input className={`${control} max-w-sm`} aria-label="Justificativa do estorno" name="reason" required minLength={3} maxLength={500} placeholder="Justificativa" /><button className={button}>Confirmar estorno</button></form>}
      </article>)}</div>
    </Panel>
  </>;
  return embedded ? <section aria-label="Honorários do caso" className="space-y-4">{content}</section> : <Page title="Honorários, despesas e horas" subtitle="Recebimentos são declarados manualmente com justificativa; não confirmam pagamento bancário.">{content}</Page>;
}
