"use client";
import Link from "next/link";
import { useState } from "react";
import { api, apiBlob } from "@/lib/api-client";
import { DOCUMENT_TYPES, documentTypeLabels, exportFilename, type BrandCapabilities, type BrandProfile, type DocumentExport, type DocumentType } from "@/lib/branding";
import { Action, Field, Panel, PrivatePdfPreview, State, button, control, dateText, download, errorText, primary, useResource } from "./shared";
import type { Row } from "./records";

export function DocumentExports({ document, onClose }: { document: Row; onClose: () => void }) {
  const profiles = useResource<{ items: BrandProfile[] }>(`/branding/profiles?document_id=${encodeURIComponent(document.id)}`);
  const capabilities = useResource<BrandCapabilities>("/branding/capabilities");
  const exports = useResource<{ items: DocumentExport[] }>(`/branding/documents/${document.id}/exports`);
  const [profileId, setProfileId] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>(document.document_type || "general");
  const [message, setMessage] = useState(""); const [preview, setPreview] = useState<{ blob: Blob; artifact: DocumentExport } | null>(null);
  async function show(artifact: DocumentExport) {
    setPreview(null);
    const blob = await apiBlob(`/branding/exports/${artifact.id}/download?format=pdf`);
    setPreview({ blob, artifact });
  }
  async function generate() {
    setBusy(true); setError(""); setMessage(""); setPreview(null);
    try {
      const artifact = await api.post<DocumentExport>(`/branding/documents/${document.id}/exports`, { expected_version: document.current_version, profile_id: profileId || null, document_type: documentType });
      exports.reload(); setMessage(`Exportação preservada: documento v${artifact.document_version}, identidade v${artifact.brand_version}. Os arquivos abaixo não mudam com futuras edições.`);
      await show(artifact);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }
  const published = profiles.data?.items.filter(profile => profile.published_version) || [];
  return <Panel title={`Exportar documento: ${document.title}`}>
    <p className="text-sm text-zinc-400">Gera PDF e Word a partir do texto salvo (v{document.current_version}). Anexos originais, provas e arquivos assinados não são alterados. A identidade deve estar publicada.</p>
    <State loading={profiles.loading || capabilities.loading} error={error || profiles.error || capabilities.error} />
    {message && <p role="status" className="text-sm text-green-300">{message}</p>}
    <Field label="Identidade para esta exportação"><select className={control} value={profileId} disabled={busy} onChange={e => setProfileId(e.target.value)}>
      <option value="">Automática — responsável pelo caso, depois escritório</option>{published.map(profile => <option key={profile.id} value={profile.id}>{profile.name} · {profile.scope === "office" ? "Escritório" : "Advogado responsável"} · v{profile.published_version}</option>)}
    </select></Field>
    <Field label="Variação visual do documento"><select className={control} value={documentType} disabled={busy} onChange={event => setDocumentType(event.target.value as DocumentType)}>{DOCUMENT_TYPES.map(type => <option key={type} value={type}>{documentTypeLabels[type]}</option>)}</select></Field>
    {!profiles.loading && !published.length && <p className="text-sm text-amber-300">Nenhuma identidade publicada elegível. <Link className="underline" href="/dashboard/brand">Configure e publique uma identidade</Link> do responsável ou do escritório.</p>}
    {capabilities.data && !capabilities.data.pdf_available && <p className="text-sm text-amber-300">O renderizador PDF não está disponível. Exportações anteriores continuam acessíveis.</p>}
    {!String(document.content_text || "").trim() && <p className="text-sm text-amber-300">Este registro não tem texto autoral salvo. O anexo original continua disponível, sem aplicação automática de identidade.</p>}
    <div className="flex flex-wrap gap-2"><button type="button" className={primary} disabled={busy || !capabilities.data?.pdf_available || !published.length || !String(document.content_text || "").trim()} onClick={generate}>{busy ? "Gerando arquivos…" : "Gerar PDF e Word da versão salva"}</button><button type="button" className={button} disabled={busy} onClick={onClose}>Fechar exportações</button></div>
    {preview && <PrivatePdfPreview blob={preview.blob} title={`PDF preservado · documento v${preview.artifact.document_version} · identidade v${preview.artifact.brand_version}`} filename={exportFilename(document.title, "pdf")} onClose={() => setPreview(null)} />}
    <section aria-label="Histórico de exportações" className="space-y-3 border-t border-zinc-800 pt-4"><h3 className="text-sm font-medium">Exportações preservadas</h3>
      <State loading={exports.loading} error={exports.error} empty={!exports.data?.items.length} />
      {exports.data?.items.map(artifact => <article key={artifact.id} className="space-y-2 border-b border-zinc-800 pb-3">
        <p className="text-sm">{documentTypeLabels[artifact.document_type || "general"]} · documento v{artifact.document_version} · identidade v{artifact.brand_version} · {dateText(artifact.created_at)}</p>
        <div className="flex flex-wrap gap-2"><Action run={() => show(artifact)}>Visualizar PDF preservado</Action><Action run={() => download(`/branding/exports/${artifact.id}/download?format=pdf`, exportFilename(document.title, "pdf"))}>Baixar PDF</Action><Action run={() => download(`/branding/exports/${artifact.id}/download?format=docx`, exportFilename(document.title, "docx"))}>Baixar Word</Action></div>
        <details><summary className="min-h-11 content-center cursor-pointer text-xs text-zinc-400">Identificação e integridade dos arquivos</summary><dl className="text-xs break-all space-y-2"><div><dt>Exportação</dt><dd>{artifact.id}</dd></div><div><dt>SHA-256 do PDF</dt><dd>{artifact.sha256_pdf}</dd></div><div><dt>SHA-256 do Word</dt><dd>{artifact.sha256_docx}</dd></div></dl></details>
      </article>)}
    </section>
  </Panel>;
}
