"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { Archive, ArrowDown, ArrowLeft, ArrowUp, CheckCircle2, Copy, Eye, EyeOff, FileText, GripVertical, Lock, Palette, Plus, Redo2, Sparkles, Trash2, Undo2, Unlock, Upload, X } from "lucide-react";
import { api, apiBlob, apiClient } from "@/lib/api-client";
import { isOfficeAdminRole, useUser } from "@/context/user-context";
import {
  BRAND_FONT_FAMILIES, brandPreflight, brandSettingLabels, defaultBrandSettings, documentTypeLabels, DOCUMENT_TYPES, effectiveBrandSettings,
  identifiedBrandSettings, PROFESSIONAL_FIELDS, professionalFieldLabels, type BrandAsset, type BrandCapabilities,
  moveBrandLayerToEdge, reorderBrandLayer, requiredBrandMargins, type BrandLayer, type BrandProfile, type BrandSettings, type BrandVariantSettings, type BrandVariants, type BrandVersion,
  type DocumentType, type ProfessionalData, type ProfessionalField,
} from "@/lib/branding";
import { Action, Field, Page, Panel, PrivatePdfPreview, State, button, control, dateText, download, errorText, primary, useResource } from "./shared";
import { BrandLivePreview, PrivateBrandImage } from "./brand-live-preview";

type Items<T> = { items: T[] };
type EditorElement = "identity" | "references" | "layers" | "header" | "body" | "footer" | "logo" | "watermark" | "paper" | "publish";
type ReferenceIntent = "reproduce" | "modernize" | "inspire";
type Crop = { x_percent: number; y_percent: number; width_percent: number; height_percent: number };
type Proposal = { id: number; settings: BrandSettings; observations: string[]; warnings: string[]; refinement_passes?: number; changes: (keyof BrandSettings)[]; selected: (keyof BrandSettings)[] };

const starters: Record<string, { label: string; description: string; settings: Partial<BrandSettings> }> = {
  reference: { label: "Usar minha referência", description: "Anexe um documento, logo ou exemplo visual.", settings: {} },
  ai: { label: "Criar com IA", description: "Descreva a identidade e construa junto com o assistente.", settings: {} },
  manual: { label: "Começar em branco", description: "Monte manualmente cores, imagens e camadas.", settings: {} },
  sober: { label: "Sóbrio", description: "Azul profundo e hierarquia discreta.", settings: { primary_color: "#17324D", header_alignment: "left" } },
  traditional: { label: "Tradicional", description: "Composição central e formal.", settings: { primary_color: "#3B2F2F", header_alignment: "center" } },
  contemporary: { label: "Contemporâneo", description: "Contraste limpo e margens amplas.", settings: { primary_color: "#1D4ED8", margin_left_mm: 28, margin_right_mm: 28 } },
  minimal: { label: "Minimalista", description: "Poucos elementos e foco no texto.", settings: { primary_color: "#27272A", watermark_opacity: 0.03 } },
};
const assetLabels: Record<BrandAsset["kind"], string> = { reference: "Referência", logo: "Logotipo", logo_dark: "Logo para fundo escuro", logo_mono: "Logo monocromático", watermark: "Marca-d'água", background: "Fundo fiel" };
const alignments = [{ value: "left", label: "Esquerda" }, { value: "center", label: "Centro" }, { value: "right", label: "Direita" }] as const;
const variantKeys = new Set<keyof BrandSettings>([
  "margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "header_text", "footer_text",
  "header_alignment", "footer_alignment", "header_divider", "footer_divider", "different_first_page", "first_header_text", "page_numbers",
  "logo_width_mm", "watermark_opacity", "watermark_position", "watermark_rotation_deg", "watermark_width_mm", "header_fields", "footer_fields",
]);
const personalFields = new Set<ProfessionalField>(["professional_name", "oab", "professional_email", "professional_phone", "professional_address"]);
const editorAreas: { id: EditorElement; label: string; hint: string }[] = [
  { id: "identity", label: "Direção visual", hint: "Nome, cores e tipografia" },
  { id: "references", label: "Referências", hint: "Arquivos e análise visual" },
  { id: "layers", label: "Camadas visuais", hint: "Papel, marca, linhas e conteúdo" },
  { id: "header", label: "Cabeçalho", hint: "Dados, logo e alinhamento" },
  { id: "body", label: "Texto", hint: "Tamanhos e entrelinhas" },
  { id: "footer", label: "Rodapé", hint: "Contatos e paginação" },
  { id: "watermark", label: "Marca-d'água", hint: "Texto, imagem e intensidade" },
  { id: "paper", label: "Papel e margens", hint: "Formato e área útil" },
  { id: "publish", label: "Revisar e publicar", hint: "PDF real e histórico" },
];
const signature = (name: string, settings: BrandSettings, variants: BrandVariants) => JSON.stringify({ name, settings, variants });

export function Branding() {
  const { user } = useUser();
  const profiles = useResource<Items<BrandProfile>>("/branding/profiles");
  const capabilities = useResource<BrandCapabilities>("/branding/capabilities");
  const [selected, setSelected] = useState<BrandProfile | null>(null);
  const [openAt, setOpenAt] = useState<EditorElement>("identity");
  const [openInAi, setOpenInAi] = useState(false);
  const [creating, setCreating] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const canCreate = ["SOCIO", "ASSOCIADO"].includes(user.role);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); const starter = String(data.get("starter") || "sober");
    setBusy(true); setError("");
    try {
      const profile = await api.post<BrandProfile>("/branding/profiles", {
        name: data.get("name"), scope: data.get("scope"), settings: { ...defaultBrandSettings, ...starters[starter].settings }, variants: {},
      });
      setCreating(false); setOpenAt(starter === "reference" ? "references" : "identity"); setOpenInAi(starter === "ai"); setSelected(profile); profiles.reload();
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }

  if (selected && capabilities.data) return <Page title="Estúdio de identidade documental" subtitle="Construa, visualize e publique a aparência usada nos documentos do LexFlow.">
    <BrandEditor initial={selected} initialElement={openAt} initialMobileTab={openInAi ? "ai" : "edit"} capabilities={capabilities.data} onBack={() => { setSelected(null); profiles.reload(); }} onChanged={profiles.reload} />
  </Page>;

  return <Page title="Identidade documental" subtitle="Organize identidades pessoais e do escritório. Cada publicação fica preservada para manter o histórico dos documentos.">
    <State loading={profiles.loading || capabilities.loading} error={profiles.error || capabilities.error || error} />
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Suas identidades</h2><p className="text-sm text-zinc-400">Abra uma identidade para editar com prévia em tempo real.</p></div>{canCreate && <button type="button" className={primary} onClick={() => setCreating(true)}>Nova identidade</button>}</div>
    {!profiles.loading && !profiles.data?.items.length && <section className="rounded-2xl border border-dashed border-zinc-700 p-8 text-center"><Palette className="mx-auto text-blue-300" aria-hidden="true" /><h2 className="mt-3 text-lg font-semibold">Crie sua primeira identidade</h2><p className="mt-1 text-sm text-zinc-400">Comece por um estilo ou use um documento como referência.</p>{canCreate && <button className={`${primary} mt-4`} onClick={() => setCreating(true)}>Começar agora</button>}</section>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{profiles.data?.items.map(profile => <article key={profile.id} className="group overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/25 transition hover:border-blue-700">
      <button type="button" className="block w-full text-left" onClick={() => { setOpenAt("identity"); setOpenInAi(false); setSelected(profile); }}>
        <div className="bg-zinc-950/60 p-4"><BrandLivePreview name={profile.name} settings={effectiveBrandSettings(profile.settings, profile.variants || {}, "general")} compact /></div>
        <div className="space-y-2 p-4"><div className="flex items-start justify-between gap-2"><h2 className="font-semibold">{profile.name}</h2><span className={`rounded-full px-2 py-1 text-xs ${profile.published_version ? "bg-emerald-950 text-emerald-300" : "bg-amber-950 text-amber-300"}`}>{profile.published_version ? `Publicada v${profile.published_version}` : "Rascunho"}</span></div><p className="text-sm text-zinc-400">{profile.scope === "office" ? "Identidade do escritório" : "Identidade pessoal"}</p><span className="inline-flex min-h-11 items-center text-sm text-blue-300">Abrir estúdio</span></div>
      </button>
    </article>)}</div>
    {creating && <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-3" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !busy) setCreating(false); }}><section role="dialog" aria-modal="true" aria-labelledby="new-brand-title" className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-950 p-5 shadow-2xl">
      <div className="flex items-start justify-between gap-3"><div><h2 id="new-brand-title" className="text-xl font-semibold">Nova identidade</h2><p className="mt-1 text-sm text-zinc-400">Escolha apenas o ponto de partida; tudo poderá ser editado no estúdio.</p></div><button type="button" className={button} aria-label="Fechar" disabled={busy} onClick={() => setCreating(false)}><X aria-hidden="true" size={18} /></button></div>
      <form onSubmit={create} className="mt-5 space-y-4"><div className="grid gap-3 sm:grid-cols-2"><Field label="Nome da identidade"><input className={control} name="name" minLength={2} maxLength={100} required autoFocus placeholder="Ex.: Identidade profissional" /></Field><Field label="Uso"><select className={control} name="scope" defaultValue="personal"><option value="personal">Minha identidade profissional</option>{isOfficeAdminRole(user.role) && <option value="office">Identidade do escritório</option>}</select></Field></div>
        <fieldset><legend className="mb-2 text-sm font-medium text-zinc-300">Ponto de partida</legend><div className="grid gap-3 sm:grid-cols-2">{Object.entries(starters).map(([id, item]) => <label key={id} className="cursor-pointer rounded-xl border border-zinc-800 p-4 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-950/20"><input className="sr-only" type="radio" name="starter" value={id} defaultChecked={id === "sober"} /><span className="font-medium">{item.label}</span><span className="mt-1 block text-xs text-zinc-400">{item.description}</span><span className="mt-3 block h-2 w-16 rounded-full" style={{ background: item.settings.primary_color || defaultBrandSettings.primary_color }} /></label>)}</div></fieldset>
        <State error={error} /><div className="flex flex-wrap justify-end gap-2"><button type="button" className={button} disabled={busy} onClick={() => setCreating(false)}>Cancelar</button><button className={primary} disabled={busy}>{busy ? "Criando…" : "Criar e abrir estúdio"}</button></div>
      </form>
    </section></div>}
  </Page>;
}

type DraftSnapshot = { name: string; settings: BrandSettings; variants: BrandVariants };
function BrandEditor({ initial, initialElement, initialMobileTab, capabilities, onBack, onChanged }: { initial: BrandProfile; initialElement: EditorElement; initialMobileTab: "edit" | "ai"; capabilities: BrandCapabilities; onBack: () => void; onChanged: () => void }) {
  const [profile, setProfile] = useState(initial); const [name, setName] = useState(initial.name); const [settings, setSettings] = useState(initial.settings); const [variants, setVariants] = useState<BrandVariants>(initial.variants || {});
  const [documentType, setDocumentType] = useState<DocumentType>("general"); const [element, setElement] = useState<EditorElement>(initialElement); const [mobileTab, setMobileTab] = useState<"edit" | "preview" | "ai">(initialMobileTab);
  const [saveState, setSaveState] = useState<"saved" | "saving" | "unsaved" | "failed" | "conflict">("saved"); const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [busy, setBusy] = useState(false); const [approved, setApproved] = useState(false); const [pdf, setPdf] = useState<Blob | null>(null); const [referencePdf, setReferencePdf] = useState<{ blob: Blob; filename: string } | null>(null);
  const [kind, setKind] = useState<BrandAsset["kind"]>("reference"); const [uploading, setUploading] = useState(false); const [brief, setBrief] = useState(""); const [referenceIds, setReferenceIds] = useState<string[]>([]); const [referencePages, setReferencePages] = useState<Record<string, number>>({}); const [referenceIntent, setReferenceIntent] = useState<ReferenceIntent>("reproduce"); const [generateLogo, setGenerateLogo] = useState(false); const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedReferenceId, setSelectedReferenceId] = useState(""); const [crop, setCrop] = useState<Crop>({ x_percent: 10, y_percent: 5, width_percent: 80, height_percent: 20 }); const [overlayOpacity, setOverlayOpacity] = useState(0); const [compareMode, setCompareMode] = useState<"overlay" | "side" | "difference">("overlay");
  const [selectedLayerId, setSelectedLayerId] = useState(initial.settings.layout_layers[0]?.id || "");
  const [saveGeneration, setSaveGeneration] = useState(0);
  const assets = useResource<Items<BrandAsset>>(profile.can_edit ? `/branding/profiles/${profile.id}/assets` : null);
  const versions = useResource<Items<BrandVersion>>(profile.can_edit ? `/branding/profiles/${profile.id}/versions` : null);
  const professional = useResource<ProfessionalData>(profile.can_edit ? `/branding/profiles/${profile.id}/professional-data` : null);
  const draftRef = useRef({ name, settings, variants }); const revisionRef = useRef(profile.revision); const savedSignature = useRef(signature(initial.name, initial.settings, initial.variants || {})); const failedSignature = useRef(""); const inFlight = useRef(false);
  const undoRef = useRef<DraftSnapshot[]>([]); const redoRef = useRef<DraftSnapshot[]>([]); const lastHistoryAt = useRef(0); const [, setHistoryVersion] = useState(0);
  draftRef.current = { name, settings, variants };
  const currentSignature = signature(name, settings, variants); const dirty = currentSignature !== savedSignature.current;
  const effective = effectiveBrandSettings(settings, variants, documentType);
  const preflight = useMemo(() => brandPreflight(effective, assets.data?.items || [], professional.data), [effective, assets.data?.items, professional.data]);

  function remember() {
    const now = Date.now();
    if (now - lastHistoryAt.current > 450) undoRef.current = [...undoRef.current.slice(-29), structuredClone(draftRef.current)];
    lastHistoryAt.current = now; redoRef.current = []; setHistoryVersion(value => value + 1);
  }
  function restore(snapshot: DraftSnapshot) { setName(snapshot.name); setSettings(snapshot.settings); setVariants(snapshot.variants); setApproved(false); setPdf(null); setMessage(""); }
  function undo() { const snapshot = undoRef.current.pop(); if (!snapshot) return; redoRef.current.push(structuredClone(draftRef.current)); restore(snapshot); lastHistoryAt.current = 0; setHistoryVersion(value => value + 1); }
  function redo() { const snapshot = redoRef.current.pop(); if (!snapshot) return; undoRef.current.push(structuredClone(draftRef.current)); restore(snapshot); lastHistoryAt.current = 0; setHistoryVersion(value => value + 1); }

  async function persist() {
    if (!profile.can_edit || inFlight.current || signature(draftRef.current.name, draftRef.current.settings, draftRef.current.variants) === savedSignature.current) return;
    inFlight.current = true; setSaveState("saving"); setError(""); const snapshot = structuredClone(draftRef.current); const snapshotSignature = signature(snapshot.name, snapshot.settings, snapshot.variants);
    try {
      const saved = await api.put<BrandProfile>(`/branding/profiles/${profile.id}`, { ...snapshot, expected_revision: revisionRef.current });
      revisionRef.current = saved.revision; savedSignature.current = snapshotSignature; failedSignature.current = ""; setProfile(saved); setSaveState(signature(draftRef.current.name, draftRef.current.settings, draftRef.current.variants) === snapshotSignature ? "saved" : "unsaved"); onChanged();
    } catch (reason) { const text = errorText(reason); failedSignature.current = snapshotSignature; setError(text); setSaveState(text.toLocaleLowerCase("pt-BR").includes("outra sessão") ? "conflict" : "failed"); }
    finally { inFlight.current = false; setSaveGeneration(value => value + 1); }
  }
  useEffect(() => {
    if (!dirty || saveState === "conflict" || saveState === "failed" && currentSignature === failedSignature.current) return;
    setSaveState("unsaved"); const timer = window.setTimeout(() => void persist(), 1000); return () => window.clearTimeout(timer);
    // persist reads the latest draft through refs; generation retriggers after a concurrent edit.
  }, [currentSignature, saveGeneration, saveState === "conflict", saveState === "failed"]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!dirty) return; const warn = (event: BeforeUnloadEvent) => event.preventDefault(); window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);

  function change<K extends keyof BrandSettings>(key: K, value: BrandSettings[K]) {
    remember();
    setApproved(false); setPdf(null); setMessage("");
    if (documentType !== "general" && variantKeys.has(key)) setVariants(current => ({ ...current, [documentType]: { ...(current[documentType] || {}), [key]: value } }));
    else setSettings(current => ({ ...current, [key]: value }));
  }
  function setLayers(next: BrandLayer[]) {
    remember();
    setApproved(false); setPdf(null); setMessage("");
    setSettings(current => ({ ...current, layout_layers: next, layout_mode: next.length ? "composed" : current.layout_mode === "composed" ? "reconstructed" : current.layout_mode }));
    if (selectedLayerId && !next.some(layer => layer.id === selectedLayerId)) setSelectedLayerId(next[0]?.id || "");
  }
  function changeLayer(layer: BrandLayer) { setLayers(settings.layout_layers.map(item => item.id === layer.id ? layer : item)); }
  function toggleProfessional(area: "header_fields" | "footer_fields", field: ProfessionalField) {
    const current = effective[area]; change(area, (current.includes(field) ? current.filter(item => item !== field) : [...current, field]) as BrandSettings[typeof area]);
  }
  async function upload(file?: File, uploadKind: BrandAsset["kind"] = kind) {
    if (!file) return; setUploading(true); setError("");
    try { if (file.size > 10 * 1024 * 1024) throw new Error("Envie um arquivo de até 10 MB."); const body = new FormData(); body.set("file", file); body.set("kind", uploadKind); const asset = await apiClient<BrandAsset>(`/branding/profiles/${profile.id}/assets`, { method: "POST", body }); assets.reload(); setReferenceIds(ids => asset.kind === "reference" ? [...ids, asset.id].slice(-3) : ids); if (asset.kind === "reference") setSelectedReferenceId(asset.id); if (asset.kind === "logo") change("logo_asset_id", asset.id); if (asset.kind === "watermark") change("watermark_asset_id", asset.id); if (asset.kind === "background") { change("background_asset_id", asset.id); change("layout_mode", "exact"); } setMessage(`${asset.filename} foi analisado e adicionado${asset.kind === "reference" ? ". Nenhuma alteração foi aplicada automaticamente." : " ao rascunho."}`); }
    catch (reason) { setError(errorText(reason)); } finally { setUploading(false); }
  }
  async function requestAi(prompt: string) {
    if (dirty || !prompt.trim()) return; setBusy(true); setError("");
    try {
      const selectedElement = element === "references" || element === "publish" ? "identity" : element;
      const result = await api.post<Omit<Proposal, "id" | "changes" | "selected">>(`/branding/profiles/${profile.id}/suggest`, { brief: prompt, reference_ids: referenceIds, reference_pages: Object.fromEntries(Object.entries(referencePages).filter(([id]) => referenceIds.includes(id))), consent: true, generate_logo: generateLogo, reference_intent: referenceIntent, document_type: documentType, selected_element: selectedElement, selected_layer_id: selectedLayerId || null, expected_revision: revisionRef.current });
      const changed = (Object.keys(defaultBrandSettings) as (keyof BrandSettings)[]).filter(key => JSON.stringify(effective[key]) !== JSON.stringify(result.settings[key]));
      setProposals(current => [{ ...result, id: Date.now(), changes: changed, selected: changed }, ...current].slice(0, 3)); setBrief(""); assets.reload();
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  async function askAi(event: FormEvent<HTMLFormElement>) { event.preventDefault(); await requestAi(brief); }
  function applyProposal(proposal: Proposal) {
    remember();
    const base: Partial<BrandSettings> = {}; const variant: BrandVariantSettings = {};
    for (const key of proposal.selected) {
      if (documentType !== "general" && variantKeys.has(key)) Object.assign(variant, { [key]: proposal.settings[key] });
      else Object.assign(base, { [key]: proposal.settings[key] });
    }
    if (proposal.selected.includes("layout_layers") && proposal.settings.layout_layers.length) base.layout_mode = "composed";
    setSettings(current => ({ ...current, ...base })); if (documentType !== "general") setVariants(current => ({ ...current, [documentType]: { ...(current[documentType] || {}), ...variant } }));
    if (proposal.selected.includes("layout_layers")) { setSelectedLayerId(proposal.settings.layout_layers[0]?.id || ""); setElement("layers"); }
    setProposals(current => current.filter(item => item.id !== proposal.id)); setMessage("Sugestão aplicada ao rascunho. Revise a prévia; o salvamento automático não publica a identidade.");
  }
  async function preview() {
    setBusy(true); setError(""); setPdf(null); try { setPdf(await apiBlob(`/branding/profiles/${profile.id}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: revisionRef.current, document_type: documentType }) })); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  async function openReference(asset: BrandAsset) { setBusy(true); setError(""); try { setReferencePdf({ blob: await apiBlob(`/branding/assets/${asset.id}/download`), filename: asset.filename }); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); } }
  async function extractReference(asset: BrandAsset, extractKind: "logo" | "watermark" | "background") {
    if (dirty) return; setBusy(true); setError("");
    try {
      const page = referencePages[asset.id] || 1;
      const area = extractKind === "background" ? { x_percent: 0, y_percent: 0, width_percent: 100, height_percent: 100 } : crop;
      const extracted = await api.post<BrandAsset>(`/branding/profiles/${profile.id}/assets/${asset.id}/extract`, { expected_revision: revisionRef.current, kind: extractKind, page, ...area });
      assets.reload();
      if (extractKind === "logo") change("logo_asset_id", extracted.id);
      if (extractKind === "watermark") change("watermark_asset_id", extracted.id);
      if (extractKind === "background") { change("background_asset_id", extracted.id); change("layout_mode", "exact"); change("show_document_title", false); change("header_fields", []); change("footer_fields", []); }
      setMessage(extractKind === "background" ? "Página aplicada como fundo fiel. Ajuste as margens e confira o PDF real antes de publicar." : `${assetLabels[extractKind]} extraído e aplicado ao rascunho.`);
    } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  async function publish() {
    if (dirty || !approved) return; setBusy(true); setError("");
    try { const saved = await api.post<BrandProfile>(`/branding/profiles/${profile.id}/publish`, { expected_revision: revisionRef.current }); revisionRef.current = saved.revision; savedSignature.current = signature(saved.name, saved.settings, saved.variants || {}); setProfile(saved); setSettings(saved.settings); setVariants(saved.variants || {}); setApproved(false); setSaveState("saved"); versions.reload(); onChanged(); setMessage(`Versão ${saved.published_version} publicada. Exportações anteriores continuam preservadas.`); }
    catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }
  async function duplicate() { const copy = await api.post<BrandProfile>(`/branding/profiles/${profile.id}/duplicate`, { expected_revision: revisionRef.current }); setMessage(`A cópia “${copy.name}” foi criada sem duplicar os arquivos privados.`); onChanged(); }
  async function archive() { if (!window.confirm("Arquivar esta identidade? Publicações e exportações anteriores serão preservadas.")) return; await api.post(`/branding/profiles/${profile.id}/archive`, { expected_revision: revisionRef.current }); onBack(); }
  function restoreVersion(version: BrandVersion) { remember(); restore({ name, settings: version.settings, variants: version.variants || {} }); setMessage(`A versão ${version.version} foi restaurada como rascunho. Nada foi publicado ainda.`); }

  const saveLabel = saveState === "saving" ? "Salvando…" : saveState === "saved" ? "Salvo" : saveState === "conflict" ? "Conflito de edição" : saveState === "failed" ? "Não foi possível salvar" : "Alterações pendentes";
  const overlayReference = assets.data?.items.find(asset => asset.id === selectedReferenceId && asset.kind === "reference" && asset.content_type !== "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
  return <div className="space-y-4">
    <header className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/25 p-3"><div className="flex min-w-0 items-center gap-2"><button type="button" className={`${button} gap-2`} aria-label="Voltar às identidades" onClick={onBack}><ArrowLeft aria-hidden="true" size={17} /> <span className="hidden sm:inline">Identidades</span></button><div className="min-w-0"><input aria-label="Nome da identidade" className="w-full min-w-0 bg-transparent text-lg font-semibold outline-none focus:ring-2 focus:ring-blue-500" value={name} maxLength={100} disabled={!profile.can_edit} onChange={event => { remember(); setName(event.target.value); }} /><p className="text-xs text-zinc-400">{profile.scope === "office" ? "Escritório" : "Pessoal"} · r{revisionRef.current} · <span role="status">{profile.can_edit ? saveLabel : "Somente leitura"}</span></p></div></div>{profile.can_edit && <div className="flex flex-wrap gap-2"><button type="button" className={button} aria-label="Desfazer" title="Desfazer" disabled={!undoRef.current.length} onClick={undo}><Undo2 aria-hidden="true" size={16} /></button><button type="button" className={button} aria-label="Refazer" title="Refazer" disabled={!redoRef.current.length} onClick={redo}><Redo2 aria-hidden="true" size={16} /></button><Action className={`${button} gap-2`} run={duplicate}><Copy aria-hidden="true" size={16} /> Duplicar</Action><Action className={`${button} gap-2`} run={archive}><Archive aria-hidden="true" size={16} /> Arquivar</Action><button type="button" className={primary} disabled={!dirty || busy || saveState === "conflict"} onClick={() => void persist()}>{saveState === "saving" ? "Salvando…" : "Salvar agora"}</button></div>}</header>
    <State error={error} />{message && <p role="status" className="rounded-lg border border-emerald-900 bg-emerald-950/25 p-3 text-sm text-emerald-200">{message}</p>}
    <nav aria-label="Modo do estúdio no celular" className="grid grid-cols-3 gap-2 lg:hidden">{(["edit", "preview", "ai"] as const).map(tab => <button key={tab} className={mobileTab === tab ? primary : button} aria-pressed={mobileTab === tab} onClick={() => setMobileTab(tab)}>{tab === "edit" ? "Editar" : tab === "preview" ? "Visualizar" : "IA"}</button>)}</nav>
    <div className="flex max-w-full gap-2 overflow-x-auto pb-1" aria-label="Tipo de documento">{DOCUMENT_TYPES.map(type => <button key={type} type="button" className={`${documentType === type ? primary : button} shrink-0 whitespace-nowrap`} aria-pressed={documentType === type} onClick={() => setDocumentType(type)}>{documentTypeLabels[type]}{type !== "general" && variants[type] && <span className="ml-1 text-xs">•</span>}</button>)}</div>
    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(17rem,.78fr)_minmax(24rem,1.35fr)_minmax(18rem,.9fr)]">
      <aside className={`${mobileTab === "edit" ? "block" : "hidden"} min-w-0 space-y-3 lg:block`}><nav aria-label="Elementos da identidade" className="grid gap-2">{editorAreas.map(area => <button key={area.id} type="button" aria-current={element === area.id ? "page" : undefined} onClick={() => setElement(area.id)} className={`rounded-xl border p-3 text-left transition ${element === area.id ? "border-blue-500 bg-blue-950/20" : "border-zinc-800 bg-zinc-900/25 hover:border-zinc-600"}`}><span className="block text-sm font-medium">{area.label}</span><span className="mt-1 block text-xs text-zinc-400">{area.hint}</span></button>)}</nav><EditorControls element={element} scope={profile.scope} capabilities={capabilities} settings={effective} baseSettings={settings} assets={assets.data?.items || []} professional={professional.data} documentType={documentType} busy={busy || uploading || !profile.can_edit} change={change} toggleProfessional={toggleProfessional} kind={kind} setKind={setKind} upload={upload} openReference={openReference} preview={preview} publish={publish} approved={approved} setApproved={setApproved} dirty={dirty} versions={versions} restoreVersion={restoreVersion} preflight={preflight} selectedReferenceId={selectedReferenceId} setSelectedReferenceId={setSelectedReferenceId} referencePages={referencePages} setReferencePages={setReferencePages} crop={crop} setCrop={setCrop} extractReference={extractReference} selectedLayerId={selectedLayerId} setSelectedLayerId={setSelectedLayerId} setLayers={setLayers} editImage={() => setElement("references")} /></aside>
      <main className={`${mobileTab === "preview" ? "block" : "hidden"} min-w-0 rounded-2xl border border-zinc-800 bg-zinc-950/40 p-3 lg:block`}><div className="lg:sticky lg:top-20">{overlayReference && <div className="mb-3 flex flex-wrap gap-2" aria-label="Comparar com a referência">{([['overlay', 'Sobrepor'], ['side', 'Lado a lado'], ['difference', 'Diferenças']] as const).map(([value, label]) => <button type="button" key={value} className={compareMode === value ? primary : button} aria-pressed={compareMode === value} onClick={() => setCompareMode(value)}>{label}</button>)}</div>}<div className={compareMode === "side" && overlayReference ? "grid gap-3 xl:grid-cols-2" : ""}>{compareMode === "side" && overlayReference && <div className="overflow-hidden rounded-xl border border-zinc-700 bg-white"><PrivateReferencePage asset={overlayReference} page={referencePages[overlayReference.id] || 1} /></div>}<BrandLivePreview name={name} settings={effective} documentType={documentType} professionalData={professional.data || undefined} assets={assets.data?.items || []} selectedLayerId={selectedLayerId} onSelectLayer={id => { setSelectedLayerId(id); setElement("layers"); }} onClearSelection={() => setSelectedLayerId("")} onChangeLayer={changeLayer} showSafeArea={element === "layers" || element === "header" || element === "footer" || element === "paper"} referenceOverlay={overlayReference && compareMode !== "side" ? { assetId: overlayReference.id, page: referencePages[overlayReference.id] || 1, opacity: compareMode === "difference" ? 1 : overlayOpacity, blendMode: compareMode === "difference" ? "difference" : undefined } : undefined} /></div>{overlayReference && compareMode === "overlay" && <Field label={`Sobrepor referência (${Math.round(overlayOpacity * 100)}%)`}><input className="w-full" type="range" min="0" max="0.8" step="0.05" value={overlayOpacity} onChange={event => setOverlayOpacity(event.target.valueAsNumber)} /></Field>}{selectedLayerId && <button type="button" className={`${primary} sticky bottom-20 mt-3 w-full lg:hidden`} onClick={() => { setElement("layers"); setMobileTab("edit"); }}>Ajustar camada selecionada</button>}{documentType !== "general" && <p className="mt-3 text-center text-xs text-zinc-400">Esta variação herda a identidade geral. Os ajustes feitos em margens, cabeçalho e rodapé valem somente para {documentTypeLabels[documentType].toLocaleLowerCase("pt-BR")}.</p>}</div></main>
      <aside className={`${mobileTab === "ai" ? "block" : "hidden"} min-w-0 space-y-3 lg:block`}><section className="rounded-2xl border border-blue-900/70 bg-blue-950/15 p-4"><div className="flex items-center gap-2"><Sparkles className="text-blue-300" aria-hidden="true" size={19} /><h2 className="font-semibold">Assistente de design</h2></div><p className="mt-1 text-xs text-zinc-400">Converse sobre o elemento aberto. A IA propõe mudanças; você escolhe o que aplicar.</p>{!capabilities.ai_available && <p className="mt-3 text-sm text-amber-300">O provedor de IA ainda não está disponível.</p>}
        <div aria-live="polite" className="mt-4 space-y-3">{proposals.map(proposal => <ProposalCard key={proposal.id} proposal={proposal} current={effective} assets={assets.data?.items || []} setProposals={setProposals} apply={applyProposal} />)}{!proposals.length && <div className="rounded-xl border border-dashed border-zinc-700 p-3 text-sm text-zinc-400">Ex.: “Deixe o cabeçalho mais sóbrio e dê destaque à OAB sem aumentar a altura.”</div>}</div>
        <form onSubmit={askAi} className="mt-4 space-y-3">{selectedLayerId && <div className="rounded-lg border border-blue-800 bg-blue-950/30 p-2 text-xs text-blue-200">A IA atuará primeiro na camada “{settings.layout_layers.find(layer => layer.id === selectedLayerId)?.label}”. <button type="button" className="underline" onClick={() => setSelectedLayerId("")}>Usar a identidade inteira</button></div>}<Field label="Como a referência deve ser usada?"><select className={control} value={referenceIntent} disabled={!profile.can_edit} onChange={event => setReferenceIntent(event.target.value as ReferenceIntent)}><option value="inspire">Usar como inspiração</option><option value="modernize">Modernizar mantendo a essência</option><option value="reproduce">Reconstruir com a maior fidelidade possível</option></select></Field><p className="text-xs text-zinc-400">A IA separa faixas, linhas, logotipo, marca-d'água e contatos e reserva automaticamente a área do texto.</p>{selectedLayerId && <div className="flex flex-wrap gap-2"><button type="button" className={button} onClick={() => setBrief("Alinhe esta camada com precisão e preserve as demais.")}>Alinhar</button><button type="button" className={button} onClick={() => setBrief("Torne esta camada mais discreta, mantendo a legibilidade.")}>Mais discreta</button><button type="button" className={button} onClick={() => setBrief("Aproxime esta camada da referência anexada sem alterar as demais.")}>Aproximar da referência</button></div>}{referenceIds.length > 0 && <button type="button" className={`${primary} w-full`} disabled={busy || dirty || !capabilities.ai_available || !profile.can_edit} onClick={() => void requestAi("Reconstrua esta página como um timbrado editável com máxima fidelidade. Identifique faixas, linhas, logo, marca-d'água e cada contato do rodapé, vinculando os dados profissionais corretos. Meça o cabeçalho e o rodapé e preserve uma área segura para todo o texto.")}>{busy ? "Analisando a página…" : "Analisar página e montar identidade"}</button>}<Field label="Mensagem para a IA"><textarea className={control} rows={4} minLength={10} maxLength={4000} required value={brief} disabled={!profile.can_edit} onChange={event => setBrief(event.target.value)} placeholder={`O que deseja mudar em ${editorAreas.find(area => area.id === element)?.label.toLocaleLowerCase("pt-BR") || "identidade"}?`} /></Field>
          {!!assets.data?.items.filter(asset => asset.kind === "reference").length && <fieldset><legend className="text-xs text-zinc-400">Referências anexadas (até 3)</legend>{assets.data.items.filter(asset => asset.kind === "reference").map(asset => <div key={asset.id} className="rounded-lg border border-zinc-800 p-2"><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={referenceIds.includes(asset.id)} disabled={!referenceIds.includes(asset.id) && referenceIds.length >= 3} onChange={event => { setReferenceIds(current => event.target.checked ? [...current, asset.id] : current.filter(id => id !== asset.id)); if (event.target.checked) setSelectedReferenceId(asset.id); }} />{asset.filename}</label>{referenceIds.includes(asset.id) && asset.content_type === "application/pdf" && <Field label="Página que melhor representa o papel timbrado"><input className={control} type="number" min={1} max={Number(asset.analysis?.identified?.pages || 200)} value={referencePages[asset.id] || 1} onChange={event => setReferencePages(current => ({ ...current, [asset.id]: event.target.valueAsNumber || 1 }))} /></Field>}</div>)}</fieldset>}
          {capabilities.image_ai_available && <label className="flex min-h-11 items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={generateLogo} onChange={event => setGenerateLogo(event.target.checked)} /><span>Criar também uma proposta de símbolo original. Logotipos já existentes devem ser enviados no Cabeçalho.</span></label>}
          <button className={primary} disabled={busy || dirty || !capabilities.ai_available || !profile.can_edit}>{busy ? "Preparando sugestão…" : "Enviar e comparar"}</button>{dirty && <p className="text-xs text-amber-300">Aguarde o salvamento do rascunho antes de pedir uma sugestão.</p>}
        </form></section></aside>
    </div>
    {pdf && <PrivatePdfPreview blob={pdf} title={`PDF real · ${documentTypeLabels[documentType]}`} filename="previa-identidade.pdf" onClose={() => setPdf(null)} />}
    {referencePdf && <PrivatePdfPreview blob={referencePdf.blob} title="Referência original" filename={referencePdf.filename} onClose={() => setReferencePdf(null)} />}
  </div>;
}

function EditorControls({ element, scope, capabilities, settings, baseSettings, assets, professional, documentType, busy, change, toggleProfessional, kind, setKind, upload, openReference, preview, publish, approved, setApproved, dirty, versions, restoreVersion, preflight, selectedReferenceId, setSelectedReferenceId, referencePages, setReferencePages, crop, setCrop, extractReference, selectedLayerId, setSelectedLayerId, setLayers, editImage }: {
  element: EditorElement; scope: BrandProfile["scope"]; capabilities: BrandCapabilities; settings: BrandSettings; baseSettings: BrandSettings; assets: BrandAsset[]; professional: ProfessionalData | null; documentType: DocumentType; busy: boolean;
  change: <K extends keyof BrandSettings>(key: K, value: BrandSettings[K]) => void; toggleProfessional: (area: "header_fields" | "footer_fields", field: ProfessionalField) => void;
  kind: BrandAsset["kind"]; setKind: (kind: BrandAsset["kind"]) => void; upload: (file?: File, kind?: BrandAsset["kind"]) => Promise<void>; openReference: (asset: BrandAsset) => Promise<void>; preview: () => Promise<void>; publish: () => Promise<void>;
  approved: boolean; setApproved: (value: boolean) => void; dirty: boolean; versions: ReturnType<typeof useResource<Items<BrandVersion>>>;
  restoreVersion: (version: BrandVersion) => void; preflight: ReturnType<typeof brandPreflight>;
  selectedReferenceId: string; setSelectedReferenceId: (id: string) => void; referencePages: Record<string, number>; setReferencePages: Dispatch<SetStateAction<Record<string, number>>>;
  crop: Crop; setCrop: Dispatch<SetStateAction<Crop>>; extractReference: (asset: BrandAsset, kind: "logo" | "watermark" | "background") => Promise<void>;
  selectedLayerId: string; setSelectedLayerId: (id: string) => void; setLayers: (layers: BrandLayer[]) => void;
  editImage: () => void;
}) {
  const number = (key: keyof BrandSettings, min: number, max: number, step = 1) => <Field label={brandSettingLabels[key]}><input type="number" className={control} min={min} max={max} step={step} value={Number(settings[key])} disabled={busy} onChange={event => { if (Number.isFinite(event.target.valueAsNumber)) change(key, event.target.valueAsNumber as BrandSettings[typeof key]); }} /></Field>;
  const alignment = (key: "header_alignment" | "footer_alignment") => <Field label={brandSettingLabels[key]}><select className={control} value={settings[key]} disabled={busy} onChange={event => change(key, event.target.value as BrandSettings[typeof key])}>{alignments.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></Field>;
  const fieldPicker = (area: "header_fields" | "footer_fields") => <fieldset className="space-y-1"><legend className="text-sm font-medium text-zinc-300">Dados automáticos</legend>{professional?.fields.map(field => <label key={field.key} className="flex min-h-11 items-start gap-2 rounded-lg border border-zinc-800 p-2 text-sm"><input className="mt-1" type="checkbox" checked={settings[area].includes(field.key)} disabled={busy} onChange={() => toggleProfessional(area, field.key)} /><span><span className="block">{field.label}</span><span className={`block text-xs ${field.complete ? "text-zinc-400" : "text-amber-300"}`}>{field.value || "Não preenchido"} · {field.source}</span></span></label>)}</fieldset>;
  const assetSelect = (key: "logo_asset_id" | "watermark_asset_id" | "background_asset_id", assetKind: BrandAsset["kind"]) => <Field label={brandSettingLabels[key]}><select className={control} value={settings[key] || ""} disabled={busy} onChange={event => { const value = event.target.value || null; change(key, value); if (key === "background_asset_id" && !value && baseSettings.layout_mode === "exact") change("layout_mode", "structured"); }}><option value="">Sem imagem</option>{assets.filter(asset => asset.kind === assetKind).map(asset => <option key={asset.id} value={asset.id}>{asset.filename}</option>)}</select></Field>;
  const shared = documentType !== "general" && <p className="text-xs text-blue-300">Cores, fontes e imagens são compartilhadas por todas as variações. Margens, textos e dados podem ser ajustados somente para {documentTypeLabels[documentType].toLocaleLowerCase("pt-BR")}.</p>;
  const safeMargins = requiredBrandMargins(settings); const hasPreflightError = preflight.some(issue => issue.level === "error");
  return <section className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-900/25 p-4">
    <div><h2 className="font-semibold">{editorAreas.find(area => area.id === element)?.label}</h2>{shared}</div>
    {element === "identity" && <><div className="grid grid-cols-2 gap-3">{(["primary_color", "accent_color", "text_color", "paper_color"] as const).map(key => <Field key={key} label={brandSettingLabels[key]}><div className="flex items-center gap-2"><input type="color" className="h-11 w-14 rounded border border-zinc-700 bg-zinc-950 p-1" value={baseSettings[key]} disabled={busy} onChange={event => change(key, event.target.value)} /><span className="text-xs">{baseSettings[key]}</span></div></Field>)}</div>{(["heading_font_family", "font_family", "utility_font_family"] as const).map(key => <Field key={key} label={brandSettingLabels[key]}><select className={control} value={baseSettings[key]} disabled={busy} onChange={event => change(key, event.target.value as BrandSettings[typeof key])}>{capabilities.fonts.map(font => <option key={font}>{font}</option>)}</select></Field>)}</>}
    {element === "references" && <ReferenceTools assets={assets} busy={busy} dirty={dirty} kind={kind} setKind={setKind} upload={upload} openReference={openReference} change={change} selectedReferenceId={selectedReferenceId} setSelectedReferenceId={setSelectedReferenceId} referencePages={referencePages} setReferencePages={setReferencePages} crop={crop} setCrop={setCrop} extractReference={extractReference} />}
    {element === "layers" && <LayerEditor settings={baseSettings} assets={assets} professional={professional} busy={busy} selectedId={selectedLayerId} select={setSelectedLayerId} setLayers={setLayers} editImage={editImage} />}
    {element === "header" && <>{fieldPicker("header_fields")}<p className="text-xs text-zinc-400"><Link className="text-blue-300 underline" href="/dashboard/account">Editar dados profissionais e do escritório</Link>. {scope === "office" ? "Dados do advogado acompanham o responsável pelo processo." : "Ajustes abaixo valem só nesta identidade."}</p>{PROFESSIONAL_FIELDS.filter(field => settings.header_fields.includes(field) && (scope === "personal" || !personalFields.has(field))).map(field => <Field key={field} label={`Substituir ${professionalFieldLabels[field]} (opcional)`}><input className={control} value={baseSettings.professional_overrides[field] || ""} disabled={busy} onChange={event => change("professional_overrides", { ...baseSettings.professional_overrides, [field]: event.target.value })} /></Field>)}<Field label="Texto adicional"><textarea className={control} rows={3} value={settings.header_text} disabled={busy} onChange={event => change("header_text", event.target.value)} /></Field>{alignment("header_alignment")}{assetSelect("logo_asset_id", "logo")}<label className={`${button} w-full cursor-pointer gap-2`}><Upload aria-hidden="true" size={17} /> Enviar logotipo<input className="sr-only" type="file" accept=".png,.jpg,.jpeg" disabled={busy} onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; void upload(file, "logo"); }} /></label><div className="grid grid-cols-2 gap-3">{number("logo_width_mm", 10, 60)}{number("logo_top_mm", 0, 60, .5)}{number("header_font_size_pt", 6, 18, .5)}{number("header_letter_spacing_pt", 0, 5, .1)}{number("header_top_mm", 0, 60, .5)}</div><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.header_uppercase} disabled={busy} onChange={event => change("header_uppercase", event.target.checked)} />Cabeçalho em maiúsculas</label><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.header_divider} disabled={busy} onChange={event => change("header_divider", event.target.checked)} />Mostrar linha de separação</label>{settings.header_divider && <div className="grid grid-cols-2 gap-3">{number("header_divider_width_percent", 20, 100, 1)}{number("header_divider_thickness_pt", .25, 3, .25)}</div>}</>}
    {element === "body" && <>{number("body_size_pt", 9, 16, .5)}{number("heading_size_pt", 12, 28, .5)}{number("heading_letter_spacing_pt", 0, 3, .1)}{number("line_spacing", 1, 2, .05)}<label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.heading_uppercase} disabled={busy} onChange={event => change("heading_uppercase", event.target.checked)} />Usar títulos em maiúsculas</label><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.show_document_title} disabled={busy} onChange={event => change("show_document_title", event.target.checked)} />Mostrar título automático antes do conteúdo</label><p className="text-xs text-zinc-400">Desative o título automático quando a própria petição ou o timbrado já trouxer a abertura visual.</p></>}
    {element === "footer" && <>{fieldPicker("footer_fields")}<Field label="Texto adicional"><textarea className={control} rows={3} value={settings.footer_text} disabled={busy} onChange={event => change("footer_text", event.target.value)} /></Field>{alignment("footer_alignment")}<div className="grid grid-cols-2 gap-3">{number("footer_font_size_pt", 6, 18, .5)}{number("footer_letter_spacing_pt", 0, 5, .1)}{number("footer_bottom_mm", 0, 60, .5)}</div><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.footer_uppercase} disabled={busy} onChange={event => change("footer_uppercase", event.target.checked)} />Rodapé em maiúsculas</label><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.footer_divider} disabled={busy} onChange={event => change("footer_divider", event.target.checked)} />Mostrar linha de separação</label>{settings.footer_divider && <div className="grid grid-cols-2 gap-3">{number("footer_divider_width_percent", 20, 100, 1)}{number("footer_divider_thickness_pt", .25, 3, .25)}</div>}<label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={settings.page_numbers} disabled={busy} onChange={event => change("page_numbers", event.target.checked)} />Mostrar número da página</label></>}
    {element === "watermark" && <>{assetSelect("watermark_asset_id", "watermark")}<label className={`${button} w-full cursor-pointer gap-2`}><Upload aria-hidden="true" size={17} /> Enviar imagem da marca-d'água<input className="sr-only" type="file" accept=".png,.jpg,.jpeg" disabled={busy} onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; void upload(file, "watermark"); }} /></label><Field label="Texto da marca-d'água"><input className={control} maxLength={80} value={baseSettings.watermark_text} disabled={busy} onChange={event => change("watermark_text", event.target.value)} /></Field><div className="grid grid-cols-2 gap-3">{number("watermark_opacity", .03, .3, .01)}{number("watermark_width_mm", 30, 150)}{number("watermark_font_size_pt", 24, 180, 1)}{number("watermark_x_percent", 0, 100, 1)}{number("watermark_y_percent", 0, 100, 1)}</div><Field label="Orientação"><select className={control} value={settings.watermark_position} disabled={busy} onChange={event => change("watermark_position", event.target.value as BrandSettings["watermark_position"])}><option value="diagonal">Diagonal</option><option value="center">Sem rotação</option></select></Field>{settings.watermark_position === "diagonal" && number("watermark_rotation_deg", -90, 90, 1)}</>}
    {element === "paper" && <><Field label="Papel"><select className={control} value={baseSettings.paper_size} disabled={busy} onChange={event => change("paper_size", event.target.value as BrandSettings["paper_size"])}><option value="A4">A4</option><option value="LETTER">Carta</option></select></Field><Field label="Cor do papel"><div className="flex items-center gap-2"><input type="color" className="h-11 w-14 rounded border border-zinc-700 bg-zinc-950 p-1" value={baseSettings.paper_color} disabled={busy} onChange={event => change("paper_color", event.target.value)} /><span className="text-xs">{baseSettings.paper_color}</span></div></Field>{(settings.margin_top_mm < safeMargins.top || settings.margin_bottom_mm < safeMargins.bottom) && <div className="rounded-lg border border-amber-800 bg-amber-950/20 p-3 text-sm text-amber-200"><p>O desenho precisa de {safeMargins.top} mm no topo e {safeMargins.bottom} mm no rodapé para não cobrir o texto.</p>{safeMargins.top <= 80 && safeMargins.bottom <= 80 && <button type="button" className={`${button} mt-2`} onClick={() => { change("margin_top_mm", safeMargins.top); change("margin_bottom_mm", safeMargins.bottom); }}>Aplicar área segura</button>}</div>}<div className="grid grid-cols-2 gap-3">{number("margin_top_mm", 20, 80)}{number("margin_bottom_mm", 20, 80)}{number("margin_left_mm", 15, 50)}{number("margin_right_mm", 15, 50)}</div><Field label="Timbrado"><select className={control} value={settings.background_scope} disabled={busy} onChange={event => change("background_scope", event.target.value as BrandSettings["background_scope"])}><option value="all">Todas as páginas</option><option value="first">Somente primeira página</option></select></Field></>}
    {element === "publish" && <><p className="text-sm text-zinc-400">{dirty ? "Aguarde o salvamento do rascunho." : "Rascunho salvo e pronto para conferência."}</p><div className="space-y-2" aria-label="Verificação antes de publicar">{preflight.map(issue => <p key={issue.text} className={`rounded-lg border p-2 text-xs ${issue.level === "error" ? "border-rose-800 bg-rose-950/20 text-rose-200" : issue.level === "warning" ? "border-amber-800 bg-amber-950/20 text-amber-200" : "border-emerald-800 bg-emerald-950/20 text-emerald-200"}`}>{issue.level === "error" ? "Corrigir: " : issue.level === "warning" ? "Conferir: " : "Pronto: "}{issue.text}</p>)}</div><button type="button" className={button} disabled={busy || dirty || hasPreflightError || !capabilities.pdf_available} onClick={() => void preview()}><FileText aria-hidden="true" size={17} /> Gerar PDF real desta variação</button><label className="flex min-h-11 items-start gap-3 text-sm"><input className="mt-1" type="checkbox" checked={approved} disabled={dirty || busy || hasPreflightError} onChange={event => setApproved(event.target.checked)} /><span>Conferi dados profissionais, imagens e visual em todas as variações que pretendo usar.</span></label><button type="button" className={primary} disabled={busy || dirty || !approved || hasPreflightError} onClick={() => void publish()}><CheckCircle2 aria-hidden="true" size={17} /> Publicar nova versão</button><div className="border-t border-zinc-800 pt-3"><h3 className="text-sm font-medium">Versões publicadas</h3><State loading={versions.loading} error={versions.error} empty={!versions.data?.items.length} />{versions.data?.items.map(version => <div key={version.id} className="mt-2 flex items-center justify-between gap-2 rounded-lg border border-zinc-800 p-2"><p className="text-xs text-zinc-400">v{version.version} · {dateText(version.created_at)}</p><button type="button" className={button} disabled={busy} onClick={() => restoreVersion(version)}>Restaurar como rascunho</button></div>)}</div></>}
  </section>;
}

const layerIconLabels = { none: "Sem ícone", whatsapp: "WhatsApp", phone: "Telefone", email: "E-mail", location: "Localização", website: "Site" } as const;

function LayerEditor({ settings, assets, professional, busy, selectedId, select, setLayers, editImage }: {
  settings: BrandSettings; assets: BrandAsset[]; professional: ProfessionalData | null; busy: boolean;
  selectedId: string; select: (id: string) => void; setLayers: (layers: BrandLayer[]) => void; editImage: () => void;
}) {
  const layers = settings.layout_layers;
  const selected = layers.find(layer => layer.id === selectedId);
  const images = assets.filter(asset => ["logo", "logo_dark", "logo_mono", "watermark"].includes(asset.kind));
  const add = (kind: BrandLayer["kind"]) => {
    const id = `layer-${crypto.randomUUID()}`;
    const base: BrandLayer = {
      id, kind, role: kind === "icon_text" ? "contact" : kind === "image" ? "logo" : "decoration", label: kind === "rectangle" ? "Faixa" : kind === "line" ? "Linha" : kind === "image" ? "Imagem" : kind === "icon_text" ? "Contato" : "Texto",
      x_percent: 8, y_percent: kind === "icon_text" ? 90 : kind === "line" ? 88 : 5, width_percent: kind === "rectangle" ? 84 : kind === "icon_text" ? 30 : 40,
      height_percent: kind === "rectangle" ? 8 : kind === "line" ? 1 : 5, rotation_deg: 0, opacity: 1, z_index: layers.length,
      visible: true, locked: false, image_contrast: 1,
      page_scope: "all", color: settings.primary_color, asset_id: kind === "image" ? images[0]?.id || null : null,
      text: kind === "text" ? "Texto visual" : "", binding: kind === "icon_text" ? "professional_phone" : null,
      icon: kind === "icon_text" ? "whatsapp" : "none", font_family: settings.utility_font_family, font_size_pt: 8,
      font_weight: "normal", alignment: "left", letter_spacing_pt: 0, uppercase: false, line_thickness_pt: 1,
    };
    if (kind === "image" && !base.asset_id) return;
    setLayers([...layers, base]); select(id);
  };
  const update = (patch: Partial<BrandLayer>) => {
    if (!selected) return;
    const next = { ...selected, ...patch };
    next.width_percent = Math.max(1, Math.min(100, next.width_percent)); next.height_percent = Math.max(1, Math.min(100, next.height_percent));
    next.x_percent = Math.max(0, Math.min(100 - next.width_percent, next.x_percent)); next.y_percent = Math.max(0, Math.min(100 - next.height_percent, next.y_percent));
    setLayers(layers.map(layer => layer.id === selected.id ? next : layer));
  };
  const moveTo = (edge: "back" | "front") => selected && setLayers(moveBrandLayerToEdge(layers, selected.id, edge));
  const duplicate = () => { if (!selected) return; const copy = { ...selected, id: `layer-${crypto.randomUUID()}`, label: `${selected.label} — cópia`, z_index: Math.max(-1, ...layers.map(layer => layer.z_index)) + 1 }; setLayers([...layers, copy]); select(copy.id); };
  const numeric = (key: "x_percent" | "y_percent" | "width_percent" | "height_percent" | "opacity" | "image_contrast" | "rotation_deg" | "font_size_pt" | "letter_spacing_pt" | "line_thickness_pt", label: string, min: number, max: number, step = 1) => selected && <Field label={label}><input className={control} type="number" min={min} max={max} step={step} value={selected[key] ?? 1} disabled={busy || selected.locked} onChange={event => Number.isFinite(event.target.valueAsNumber) && update({ [key]: event.target.valueAsNumber })} /></Field>;
  return <div className="space-y-4">
    <p className="text-sm text-zinc-400">Selecione na folha ou na lista. Arraste, use as quatro alças para redimensionar e o ponto superior para girar. Setas movem com precisão.</p>
    <div className="grid grid-cols-2 gap-2">
      <button type="button" className={button} disabled={busy} onClick={() => add("rectangle")}><Plus aria-hidden="true" size={16} /> Faixa</button>
      <button type="button" className={button} disabled={busy} onClick={() => add("line")}><Plus aria-hidden="true" size={16} /> Linha</button>
      <button type="button" className={button} disabled={busy} onClick={() => add("text")}><Plus aria-hidden="true" size={16} /> Texto</button>
      <button type="button" className={button} disabled={busy} onClick={() => add("icon_text")}><Plus aria-hidden="true" size={16} /> Contato</button>
      <button type="button" className={`${button} col-span-2`} disabled={busy || !images.length} onClick={() => add("image")}><Plus aria-hidden="true" size={16} /> Logo ou imagem</button>
    </div>
    {!images.length && <p className="text-xs text-zinc-400">Envie ou extraia um logotipo/marca-d'água para adicionar uma camada de imagem.</p>}
    <div className="max-h-64 space-y-2 overflow-y-auto" aria-label="Lista de camadas">{[...layers].sort((a, b) => b.z_index - a.z_index).map(layer => <div key={layer.id} draggable={!busy && !layer.locked} onDragStart={event => event.dataTransfer.setData("text/plain", layer.id)} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const source = event.dataTransfer.getData("text/plain"); if (source) setLayers(reorderBrandLayer(layers, source, layer.id)); }} className={`flex min-h-12 items-center gap-1 rounded-lg border p-1 ${selectedId === layer.id ? "border-blue-500 bg-blue-950/20" : "border-zinc-800"}`}><GripVertical aria-hidden="true" size={16} className="shrink-0 text-zinc-500" /><button type="button" className="min-w-0 flex-1 px-1 text-left text-sm" onClick={() => select(selectedId === layer.id ? "" : layer.id)}><span className="block truncate">{layer.label}</span><span className="block text-xs text-zinc-400">{layer.kind === "icon_text" && layer.binding ? professionalFieldLabels[layer.binding] : layer.kind === "rectangle" ? "Faixa" : layer.kind === "line" ? "Linha" : layer.kind === "image" ? "Imagem" : "Texto"}</span></button><button type="button" className="grid h-10 w-10 place-items-center rounded hover:bg-zinc-800" aria-label={`${layer.visible === false ? "Mostrar" : "Ocultar"} ${layer.label}`} onClick={() => setLayers(layers.map(item => item.id === layer.id ? { ...item, visible: item.visible === false } : item))}>{layer.visible === false ? <EyeOff aria-hidden="true" size={16} /> : <Eye aria-hidden="true" size={16} />}</button><button type="button" className="grid h-10 w-10 place-items-center rounded hover:bg-zinc-800" aria-label={`${layer.locked ? "Desbloquear" : "Bloquear"} ${layer.label}`} onClick={() => setLayers(layers.map(item => item.id === layer.id ? { ...item, locked: !item.locked } : item))}>{layer.locked ? <Lock aria-hidden="true" size={16} /> : <Unlock aria-hidden="true" size={16} />}</button></div>)}</div>
    {!layers.length && <p className="rounded-lg border border-dashed border-zinc-700 p-3 text-sm text-zinc-400">A IA pode montar as camadas a partir da referência, ou você pode iniciar com os botões acima.</p>}
    {selected && <section className="space-y-3 rounded-xl border border-zinc-700 p-3" aria-label={`Configurar ${selected.label}`}>
      <div className="flex items-center justify-between gap-2"><strong className="text-sm">{selected.label}</strong><div className="flex gap-1"><button type="button" className={button} aria-label="Duplicar camada" disabled={busy} onClick={duplicate}><Copy aria-hidden="true" size={15} /></button><button type="button" className={button} aria-label="Excluir camada" disabled={busy} onClick={() => setLayers(layers.filter(layer => layer.id !== selected.id))}><Trash2 aria-hidden="true" size={15} /></button></div></div>
      <div className="grid grid-cols-2 gap-2"><button type="button" className={button} disabled={busy} onClick={() => moveTo("back")}><ArrowDown aria-hidden="true" size={15} /> Enviar ao fundo</button><button type="button" className={button} disabled={busy} onClick={() => moveTo("front")}><ArrowUp aria-hidden="true" size={15} /> Trazer à frente</button></div>
      <Field label="Nome da camada"><input className={control} maxLength={80} value={selected.label} disabled={busy} onChange={event => update({ label: event.target.value })} /></Field>
      {selected.kind === "image" && <><div className="grid grid-cols-3 gap-2">{images.map(asset => <button key={asset.id} type="button" className={`overflow-hidden rounded-lg border p-1 ${selected.asset_id === asset.id ? "border-blue-500" : "border-zinc-700"}`} onClick={() => update({ asset_id: asset.id })}><PrivateBrandImage asset={asset} alt={asset.filename} className="aspect-square w-full object-contain" /><span className="mt-1 block truncate text-[10px]">{asset.filename}</span></button>)}</div><button type="button" className={`${button} w-full`} onClick={editImage}>Refazer recorte ou remover fundo</button></>}
      {selected.kind === "text" && <Field label="Texto visual"><textarea className={control} rows={2} maxLength={500} value={selected.text} disabled={busy} onChange={event => update({ text: event.target.value })} /></Field>}
      {selected.kind === "icon_text" && <><Field label="Dado automático"><select className={control} value={selected.binding || ""} disabled={busy} onChange={event => update({ binding: event.target.value as ProfessionalField })}>{PROFESSIONAL_FIELDS.map(field => <option key={field} value={field}>{professionalFieldLabels[field]}{professional?.fields.find(item => item.key === field)?.complete ? "" : " — não preenchido"}</option>)}</select></Field><Field label="Símbolo"><select className={control} value={selected.icon} disabled={busy} onChange={event => update({ icon: event.target.value as BrandLayer["icon"] })}>{Object.entries(layerIconLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>{selected.icon !== "none" && <button type="button" className={button} disabled={busy} onClick={() => update({ icon: "none" })}>Remover somente o símbolo</button>}</>}
      <div className="grid grid-cols-2 gap-2"><button type="button" className={button} disabled={busy || selected.locked} onClick={() => update({ x_percent: (100 - selected.width_percent) / 2 })}>Centralizar horizontal</button><button type="button" className={button} disabled={busy || selected.locked} onClick={() => update({ y_percent: (100 - selected.height_percent) / 2 })}>Centralizar vertical</button></div>
      <div className="grid grid-cols-2 gap-2">{numeric("x_percent", "Esquerda (%)", 0, 100)}{numeric("y_percent", "Topo (%)", 0, 100)}{numeric("width_percent", "Largura (%)", 1, 100)}{numeric("height_percent", "Altura (%)", 1, 100)}{numeric("opacity", "Intensidade", 0, 1, .01)}{numeric("rotation_deg", "Rotação", -180, 180)}{selected.kind === "image" && numeric("image_contrast", "Contraste", .5, 3, .05)}</div>
      {selected.kind !== "image" && <Field label="Cor"><input type="color" className="h-11 w-full rounded border border-zinc-700 bg-zinc-950 p-1" value={selected.color} disabled={busy} onChange={event => update({ color: event.target.value })} /></Field>}
      {(selected.kind === "text" || selected.kind === "icon_text") && <><div className="grid grid-cols-2 gap-2">{numeric("font_size_pt", "Tamanho (pt)", 5, 40, .5)}{numeric("letter_spacing_pt", "Espaçamento", 0, 5, .1)}</div><Field label="Fonte"><select className={control} value={selected.font_family} disabled={busy} onChange={event => update({ font_family: event.target.value as BrandLayer["font_family"] })}>{BRAND_FONT_FAMILIES.map(font => <option key={font}>{font}</option>)}</select></Field></>}
      {selected.kind === "line" && numeric("line_thickness_pt", "Espessura (pt)", .25, 12, .25)}
      <Field label="Páginas"><select className={control} value={selected.page_scope} disabled={busy} onChange={event => update({ page_scope: event.target.value as BrandLayer["page_scope"] })}><option value="all">Todas</option><option value="first">Somente a primeira</option><option value="continuation">Da segunda em diante</option></select></Field>
    </section>}
  </div>;
}

function PrivateReferencePage({ asset, page }: { asset: BrandAsset; page: number }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let active = true; let objectUrl = "";
    apiBlob(`/branding/assets/${asset.id}/pages/${page}`).then(blob => {
      if (!active || !blob.type.startsWith("image/")) return;
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
    }).catch(() => setUrl(""));
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [asset.id, page]);
  return url ? <img src={url} alt={`Página ${page} de ${asset.filename}`} className="h-auto w-full" /> : <div className="grid aspect-[210/297] place-items-center text-sm text-zinc-400">Preparando página…</div>;
}

function ReferenceTools({ assets, busy, dirty, kind, setKind, upload, openReference, change, selectedReferenceId, setSelectedReferenceId, referencePages, setReferencePages, crop, setCrop, extractReference }: {
  assets: BrandAsset[]; busy: boolean; dirty: boolean; kind: BrandAsset["kind"]; setKind: (kind: BrandAsset["kind"]) => void;
  upload: (file?: File, kind?: BrandAsset["kind"]) => Promise<void>; openReference: (asset: BrandAsset) => Promise<void>;
  change: <K extends keyof BrandSettings>(key: K, value: BrandSettings[K]) => void; selectedReferenceId: string; setSelectedReferenceId: (id: string) => void;
  referencePages: Record<string, number>; setReferencePages: Dispatch<SetStateAction<Record<string, number>>>; crop: Crop; setCrop: Dispatch<SetStateAction<Crop>>;
  extractReference: (asset: BrandAsset, kind: "logo" | "watermark" | "background") => Promise<void>;
}) {
  const references = assets.filter(asset => asset.kind === "reference");
  const selected = references.find(asset => asset.id === selectedReferenceId) || references[0];
  useEffect(() => { if (!selectedReferenceId && references[0]) setSelectedReferenceId(references[0].id); }, [selectedReferenceId, references, setSelectedReferenceId]);
  const page = selected ? referencePages[selected.id] || 1 : 1;
  const pages = selected?.content_type === "application/pdf" ? Number(selected.analysis?.identified?.pages || 1) : 1;
  const visual = selected && selected.content_type !== "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  const updateCrop = (key: keyof Crop, value: number) => setCrop(current => {
    const next = { ...current, [key]: value };
    if (key === "x_percent") next.width_percent = Math.min(next.width_percent, 100 - value);
    if (key === "y_percent") next.height_percent = Math.min(next.height_percent, 100 - value);
    if (key === "width_percent") next.width_percent = Math.min(value, 100 - next.x_percent);
    if (key === "height_percent") next.height_percent = Math.min(value, 100 - next.y_percent);
    return next;
  });
  return <div className="space-y-4">
    <Field label="O que deseja anexar?"><select className={control} value={kind} disabled={busy} onChange={event => setKind(event.target.value as BrandAsset["kind"])}>{Object.entries(assetLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
    <label className={`${button} w-full cursor-pointer gap-2`}><Upload aria-hidden="true" size={17} /> Anexar arquivo<input className="sr-only" type="file" accept={kind === "reference" ? ".docx,.pdf,.png,.jpg,.jpeg" : ".png,.jpg,.jpeg"} disabled={busy} onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; void upload(file); }} /></label>
    <p className="text-xs text-zinc-400">PDF, Word, PNG ou JPEG · até 10 MB. A referência só vira timbrado, logo ou marca-d'água após sua confirmação.</p>
    {references.length > 0 && <Field label="Referência em análise"><select className={control} value={selected?.id || ""} onChange={event => setSelectedReferenceId(event.target.value)}>{references.map(asset => <option key={asset.id} value={asset.id}>{asset.filename}</option>)}</select></Field>}
    {selected && <article className="space-y-3 rounded-xl border border-zinc-800 p-3">
      <div className="flex items-start justify-between gap-2"><div><p className="text-sm font-medium">{selected.filename}</p><p className="text-xs text-zinc-400">{pages} {pages === 1 ? "página" : "páginas"}</p></div><div className="flex gap-2">{selected.content_type === "application/pdf" && <button className={button} type="button" onClick={() => void openReference(selected)}>Abrir PDF</button>}<Action run={() => download(`/branding/assets/${selected.id}/download`, selected.filename)}>Baixar</Action></div></div>
      {visual && <>
        {pages > 1 && <div className="flex items-end gap-2"><button type="button" className={button} disabled={page <= 1} onClick={() => setReferencePages(current => ({ ...current, [selected.id]: page - 1 }))}>Anterior</button><Field label="Página"><input className={control} type="number" min={1} max={pages} value={page} onChange={event => setReferencePages(current => ({ ...current, [selected.id]: Math.max(1, Math.min(pages, event.target.valueAsNumber || 1)) }))} /></Field><button type="button" className={button} disabled={page >= pages} onClick={() => setReferencePages(current => ({ ...current, [selected.id]: page + 1 }))}>Próxima</button></div>}
        <div className="relative overflow-hidden rounded-lg border border-zinc-700 bg-white"><PrivateReferencePage asset={selected} page={page} /><span aria-hidden="true" className="pointer-events-none absolute border-2 border-blue-500 bg-blue-500/10" style={{ left: `${crop.x_percent}%`, top: `${crop.y_percent}%`, width: `${crop.width_percent}%`, height: `${crop.height_percent}%` }} /></div>
        <fieldset><legend className="mb-2 text-sm font-medium">Área para extrair logo ou marca-d'água</legend><div className="grid grid-cols-2 gap-2">{([['x_percent', 'Esquerda'], ['y_percent', 'Topo'], ['width_percent', 'Largura'], ['height_percent', 'Altura']] as [keyof Crop, string][]).map(([key, label]) => <Field key={key} label={`${label} (%)`}><input className={control} type="number" min={key.includes("width") || key.includes("height") ? 1 : 0} max={100} value={crop[key]} onChange={event => updateCrop(key, event.target.valueAsNumber || 0)} /></Field>)}</div></fieldset>
        <div className="grid gap-2"><button type="button" className={primary} disabled={busy || dirty} onClick={() => void extractReference(selected, "background")}>Usar página inteira como timbrado fiel</button><div className="grid grid-cols-2 gap-2"><button type="button" className={button} disabled={busy || dirty} onClick={() => void extractReference(selected, "logo")}>Extrair logotipo</button><button type="button" className={button} disabled={busy || dirty} onClick={() => void extractReference(selected, "watermark")}>Extrair marca-d'água</button></div></div>
        {dirty && <p className="text-xs text-amber-300">Aguarde o salvamento do rascunho antes de extrair.</p>}
      </>}
      {selected.analysis?.warnings?.map(warning => <p key={warning} className="text-xs text-amber-300">{warning}</p>)}
      {Object.keys(identifiedBrandSettings(selected.analysis?.identified || {})).length > 0 && <button className={button} type="button" onClick={() => Object.entries(identifiedBrandSettings(selected.analysis.identified)).forEach(([key, value]) => change(key as keyof BrandSettings, value as never))}>Aplicar metadados confiáveis</button>}
    </article>}
    {!references.length && <p className="rounded-lg border border-dashed border-zinc-700 p-3 text-sm text-zinc-400">Anexe uma referência para escolher a página, comparar e extrair seus elementos.</p>}
  </div>;
}

function ProposalCard({ proposal, current, assets, setProposals, apply }: { proposal: Proposal; current: BrandSettings; assets: BrandAsset[]; setProposals: Dispatch<SetStateAction<Proposal[]>>; apply: (proposal: Proposal) => void }) {
  const display = (key: keyof BrandSettings, value: BrandSettings[keyof BrandSettings]) => key === "layout_layers" ? `${(value as BrandLayer[]).length} camadas editáveis` : key.endsWith("_asset_id") ? (assets.find(asset => asset.id === value)?.filename || (value ? "Imagem" : "Sem imagem")) : Array.isArray(value) ? value.map(item => professionalFieldLabels[item as ProfessionalField] || item).join(", ") : typeof value === "boolean" ? (value ? "Sim" : "Não") : String(value ?? "—");
  return <article className="rounded-xl border border-blue-900 bg-zinc-950/60 p-3"><div className="flex items-center justify-between gap-2"><p className="text-sm font-medium">Sugestão para revisão</p>{proposal.refinement_passes === 2 && <span className="rounded-full bg-blue-950 px-2 py-1 text-[11px] text-blue-200">2 comparações visuais</span>}</div>{proposal.observations?.map(item => <p key={item} className="mt-1 text-xs text-zinc-300">{item}</p>)}{proposal.warnings?.map(item => <p key={item} className="mt-1 text-xs text-amber-300">{item}</p>)}{!proposal.changes.length && <p className="mt-3 rounded-lg border border-amber-800 bg-amber-950/20 p-2 text-xs text-amber-200">A IA não encontrou alterações compatíveis com o editor. Tente indicar outra página da referência ou extrair separadamente o logotipo e a marca-d'água.</p>}<div className="mt-3 max-h-64 space-y-2 overflow-y-auto">{proposal.changes.map(key => <label key={key} className="block rounded-lg border border-zinc-800 p-2 text-xs"><span className="flex gap-2"><input type="checkbox" checked={proposal.selected.includes(key)} onChange={event => setProposals(list => list.map(item => item.id === proposal.id ? { ...item, selected: event.target.checked ? [...item.selected, key] : item.selected.filter(field => field !== key) } : item))} /><strong>{brandSettingLabels[key]}</strong></span><span className="mt-1 block text-zinc-500">Atual: {display(key, current[key])}</span><span className="block text-blue-200">Proposto: {display(key, proposal.settings[key])}</span></label>)}</div><div className="mt-3 flex flex-wrap gap-2">{!!proposal.changes.length && <><button type="button" className={primary} disabled={!proposal.selected.length} onClick={() => apply(proposal)}>Aplicar selecionados</button><button type="button" className={button} onClick={() => setProposals(list => list.map(item => item.id === proposal.id ? { ...item, selected: proposal.changes } : item))}>Selecionar tudo</button></>}<button type="button" className={button} onClick={() => setProposals(list => list.filter(item => item.id !== proposal.id))}>Descartar</button></div></article>;
}
