"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { List, Row } from "./records";
import { DocumentExports } from "./document-exports";
import { DraftNotice, Field, Panel, State, button, control, errorText, primary, useAccountDraft, useDraftGuard, useResource } from "./shared";

type Template = { key: string; title: string; description: string; version: string; fields: { key: string; label: string; required: boolean }[]; review_required: true };
type Preview = { title: string; content_text: string; content_format: "plain"; missing_fields: { key: string; label: string }[]; source: { case_revision: number; client_revision: number; template_version: string; profile_fingerprint: string }; review_required: true };
type Context = { case: Row; client: Row; lawyer: Row; addresses: Array<{ id: string; label: string; value: string }>; signature_city?: string };
export function DocumentKit({ caseId, onSaved }: { caseId?: string; onSaved: () => void }) {
  const catalog = useResource<{ items: Template[] }>("/document-kit/templates"); const cases = useResource<List>(caseId ? null : "/workspace/cases");
  const draftKey = `kit:${caseId || "all"}`;
  const [selectedCase, setSelectedCase] = useAccountDraft(`${draftKey}:case`, caseId || ""); const [templateKey, setTemplateKey] = useAccountDraft(`${draftKey}:template`, ""); const [values, setValues] = useAccountDraft<Record<string, string>>(`${draftKey}:values`, {});
  const [preview, setPreview] = useState<Preview | null>(null); const [reviewed, setReviewed] = useState(false); const [saved, setSaved] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [requests] = useAccountDraft(`${draftKey}:requests`, new Map<string, string>()); const draft = useDraftGuard(undefined, Boolean(templateKey));
  const context = useResource<Context>(selectedCase ? `/document-kit/context?case_id=${encodeURIComponent(selectedCase)}` : null);
  const [addressChoice, setAddressChoice] = useState("");
  const selected = catalog.data?.items.find(item => item.key === templateKey);
  function invalidate() { setPreview(null); setReviewed(false); setSaved(null); draft.setDirty(true); }
  useEffect(() => {
    if (!context.data) return;
    const firstAddress = context.data.addresses[0];
    setAddressChoice(current => current || firstAddress?.id || "custom");
    setValues(current => ({ ...current, signed_on: current.signed_on || new Date().toISOString().slice(0, 10), client_qualification: current.client_qualification || context.data!.client.qualification || "", professional_address: current.professional_address || firstAddress?.value || "", location: current.location || context.data!.signature_city || "" }));
  // useAccountDraft intentionally keeps its setter local to this render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [context.data]);
  return <Panel title="Biblioteca guiada de documentos" description="Escolha o processo e revise apenas os dados específicos da peça.">
    <p className="text-xs text-amber-300">Rascunhos genéricos, não homologados juridicamente. Revise poderes, condições e adequação ao caso antes de usar. Não há assinatura, envio ou protocolo automático.</p>
    <State loading={catalog.loading || context.loading} error={catalog.error || cases.error || context.error || error} />
    <form className="space-y-3" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError(""); setPreview(null); setReviewed(false);
      try { setPreview(await api.post<Preview>("/document-kit/preview", { template_key: templateKey, case_id: selectedCase, values })); } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
    }}><fieldset disabled={busy} className="min-w-0 space-y-3">
      <div className="grid sm:grid-cols-2 gap-3"><Field label="Tipo de documento"><select className={control} required value={templateKey} onChange={e => { setTemplateKey(e.target.value); setValues({}); invalidate(); }}><option value="">Selecione…</option>{catalog.data?.items.map(item => <option value={item.key} key={item.key}>{item.title}</option>)}</select></Field>
      {!caseId && <Field label="Processo relacionado"><select className={control} required value={selectedCase} onChange={e => { setSelectedCase(e.target.value); invalidate(); }}><option value="">Selecione…</option>{cases.data?.items.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></Field>}</div>
      {selected && <><p className="text-xs text-zinc-400">{selected.description} · versão {selected.version}. Os dados permanentes vêm dos cadastros e podem ser personalizados somente neste documento.</p>{context.data && <div className="grid gap-3 sm:grid-cols-3"><article className="rounded-lg border border-zinc-800 p-3"><p className="text-xs text-zinc-400">Cliente</p><p className="mt-1 text-sm font-medium">{context.data.client.name}</p><p className="text-xs text-zinc-400">{context.data.client.tax_id || "CPF/CNPJ não informado"}</p></article><article className="rounded-lg border border-zinc-800 p-3"><p className="text-xs text-zinc-400">Advogado responsável</p><p className="mt-1 text-sm font-medium">{context.data.lawyer.name}</p><p className="text-xs text-zinc-400">{context.data.lawyer.oab ? `OAB ${context.data.lawyer.oab}/${context.data.lawyer.oab_uf || "—"}` : "OAB não informada"}</p></article><article className="rounded-lg border border-zinc-800 p-3"><p className="text-xs text-zinc-400">Processo</p><p className="mt-1 text-sm font-medium">{context.data.case.title}</p><p className="text-xs text-zinc-400">{context.data.case.number || "Número não informado"}</p></article></div>}
      {selected.fields.some(field => field.key === "professional_address") && <Field label="Endereço profissional usado"><select className={control} value={addressChoice} onChange={event => { const choice = event.target.value; setAddressChoice(choice); const savedAddress = context.data?.addresses.find(item => item.id === choice); setValues(current => ({ ...current, professional_address: savedAddress?.value || "" })); invalidate(); }}><option value="">Selecione…</option>{context.data?.addresses.map(address => <option key={address.id} value={address.id}>{address.label}</option>)}<option value="custom">Personalizar somente neste documento</option></select></Field>}
      {addressChoice === "custom" && selected.fields.some(field => field.key === "professional_address") && <Field label="Endereço profissional deste documento"><textarea className={control} rows={2} maxLength={4000} value={values.professional_address || ""} onChange={event => { setValues(current => ({ ...current, professional_address: event.target.value })); invalidate(); }} /></Field>}
      <div className="grid sm:grid-cols-2 gap-3">{selected.fields.filter(field => !["client_qualification", "professional_address", "location"].includes(field.key)).map(field => <Field key={field.key} label={`${field.label}${field.required ? " (necessário para salvar)" : ""}`}>{field.key === "signed_on" ? <input type="date" className={control} value={values[field.key] || ""} onChange={e => { setValues(current => ({ ...current, [field.key]: e.target.value })); invalidate(); }} /> : <textarea className={control} rows={2} maxLength={4000} value={values[field.key] || ""} onChange={e => { setValues(current => ({ ...current, [field.key]: e.target.value })); invalidate(); }} />}</Field>)}</div>
      {selected.fields.some(field => field.key === "client_qualification") && <details className="rounded-lg border border-zinc-800 p-3"><summary className="min-h-11 cursor-pointer list-none content-center text-sm font-medium text-blue-300">Personalizar dados somente neste documento</summary><div className="mt-3 grid gap-3 sm:grid-cols-2"><Field label="Qualificação e endereço do cliente"><textarea className={control} rows={3} value={values.client_qualification || ""} onChange={event => { setValues(current => ({ ...current, client_qualification: event.target.value })); invalidate(); }} /></Field><Field label="Cidade da assinatura"><input className={control} value={values.location || ""} onChange={event => { setValues(current => ({ ...current, location: event.target.value })); invalidate(); }} /></Field></div></details>}</>}
      <DraftNotice dirty={draft.dirty} /><button className={primary} disabled={!selected || !selectedCase}>{busy ? "Processando…" : "Gerar prévia para revisão"}</button>
    </fieldset></form>
    {preview && <section aria-label="Prévia do kit" className="space-y-3 border-t border-zinc-800 pt-3">
      <h3 className="text-sm font-semibold">{preview.title}</h3><pre className="max-h-[60dvh] overflow-y-auto whitespace-pre-wrap break-words rounded-lg bg-zinc-950 p-3 text-sm font-sans">{preview.content_text}</pre>
      {preview.missing_fields.length > 0 && <div role="alert" className="space-y-2 text-sm text-amber-300"><p>Preencha os dados antes de salvar:</p><ul className="list-disc pl-5">{preview.missing_fields.map(field => <li key={field.key}>{field.label}</li>)}</ul><p className="text-xs">Dados de identificação devem ser corrigidos no cadastro do cliente ou no perfil do advogado responsável. Gere uma nova prévia após corrigir.</p><div className="flex flex-wrap gap-2"><Link className={button} href="/dashboard/crm">Consultar clientes</Link><Link className={button} href="/dashboard/account">Consultar meu perfil</Link></div></div>}
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={reviewed} disabled={busy || Boolean(preview.missing_fields.length) || Boolean(saved)} onChange={e => setReviewed(e.target.checked)} />Revisei todo o texto e confirmo sua adequação ao caso.</label>
      <button type="button" className={primary} disabled={busy || !reviewed || Boolean(preview.missing_fields.length) || Boolean(saved)} onClick={async () => {
        setBusy(true); setError(""); const fingerprint = preview.source.profile_fingerprint;
        if (!requests.has(fingerprint)) requests.set(fingerprint, crypto.randomUUID());
        try { const result = await api.post<{ document: Row }>("/document-kit/documents", { request_id: requests.get(fingerprint), template_key: templateKey, case_id: selectedCase, values, source: preview.source, reviewed: true }); setSaved(result.document); draft.setDirty(false); onSaved(); } catch (err) { if (err instanceof ApiError && err.status === 409) requests.delete(fingerprint); setError(`${errorText(err)} O rascunho foi mantido. Se os cadastros mudaram, gere e revise uma nova prévia.`); } finally { setBusy(false); }
      }}>{busy ? "Salvando…" : saved ? "Documento salvo" : "Salvar documento revisado"}</button>
    </section>}
    {saved && <><p role="status" className="text-sm text-green-300">Documento vinculado ao caso, com versão preservada. A exportação usa a identidade publicada.</p><DocumentExports document={saved} onClose={() => setSaved(null)} /></>}
  </Panel>;
}
