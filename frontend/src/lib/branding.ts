export const BRAND_FONT_FAMILIES = [
  "Liberation Serif", "Liberation Sans", "Liberation Mono",
  "DejaVu Serif", "DejaVu Sans", "DejaVu Sans Mono",
  "Noto Serif", "Noto Sans", "Noto Mono", "Carlito", "Caladea", "Lato", "Tinos",
] as const;

export type BrandFontFamily = (typeof BRAND_FONT_FAMILIES)[number];
export const DOCUMENT_TYPES = ["general", "petition", "contract", "power_of_attorney", "notice", "correspondence"] as const;
export type DocumentType = (typeof DOCUMENT_TYPES)[number];
export const documentTypeLabels: Record<DocumentType, string> = {
  general: "Geral", petition: "Petição", contract: "Contrato", power_of_attorney: "Procuração",
  notice: "Notificação", correspondence: "Correspondência",
};

export const PROFESSIONAL_FIELDS = [
  "professional_name", "oab", "professional_email", "professional_phone", "professional_address",
  "office_name", "office_email", "office_phone", "office_address", "website",
] as const;
export type ProfessionalField = (typeof PROFESSIONAL_FIELDS)[number];
export type BrandLayerKind = "rectangle" | "line" | "image" | "text" | "icon_text";
export type BrandLayerIcon = "none" | "whatsapp" | "phone" | "email" | "location" | "website";
export type BrandLayer = {
  id: string; kind: BrandLayerKind; role: "decoration" | "logo" | "watermark" | "heading" | "contact"; label: string;
  x_percent: number; y_percent: number; width_percent: number; height_percent: number; rotation_deg: number; opacity: number;
  visible: boolean; locked: boolean; image_contrast: number;
  z_index: number; page_scope: "first" | "all" | "continuation"; color: string; asset_id: string | null;
  text: string; binding: ProfessionalField | null; icon: BrandLayerIcon; font_family: BrandFontFamily; font_size_pt: number;
  font_weight: "normal" | "bold"; alignment: "left" | "center" | "right"; letter_spacing_pt: number; uppercase: boolean; line_thickness_pt: number;
};
export const professionalFieldLabels: Record<ProfessionalField, string> = {
  professional_name: "Nome profissional", oab: "OAB", professional_email: "E-mail profissional",
  professional_phone: "Telefone profissional", professional_address: "Endereço profissional",
  office_name: "Nome do escritório", office_email: "E-mail do escritório", office_phone: "Telefone do escritório",
  office_address: "Endereço do escritório", website: "Site",
};

export type BrandSettings = {
  font_family: BrandFontFamily; heading_font_family: BrandFontFamily; utility_font_family: BrandFontFamily;
  body_size_pt: number; heading_size_pt: number; heading_letter_spacing_pt: number; heading_uppercase: boolean;
  line_spacing: number; primary_color: string; accent_color: string; text_color: string; paper_color: string; paper_size: "A4" | "LETTER";
  layout_mode: "structured" | "reconstructed" | "composed" | "exact"; background_asset_id: string | null; background_scope: "first" | "all"; show_document_title: boolean;
  margin_top_mm: number; margin_bottom_mm: number; margin_left_mm: number; margin_right_mm: number;
  header_text: string; footer_text: string; header_alignment: "left" | "center" | "right";
  footer_alignment: "left" | "center" | "right"; header_divider: boolean; footer_divider: boolean;
  header_font_size_pt: number; footer_font_size_pt: number; header_letter_spacing_pt: number; footer_letter_spacing_pt: number;
  header_uppercase: boolean; footer_uppercase: boolean; header_top_mm: number; footer_bottom_mm: number;
  header_divider_thickness_pt: number; footer_divider_thickness_pt: number; header_divider_width_percent: number; footer_divider_width_percent: number;
  different_first_page: boolean; first_header_text: string;
  page_numbers: boolean; logo_asset_id: string | null; logo_dark_asset_id: string | null;
  logo_mono_asset_id: string | null; logo_width_mm: number; watermark_asset_id: string | null;
  logo_top_mm: number;
  watermark_text: string; watermark_opacity: number; watermark_position: "center" | "diagonal"; watermark_rotation_deg: number;
  watermark_width_mm: number; header_fields: ProfessionalField[]; footer_fields: ProfessionalField[];
  watermark_x_percent: number; watermark_y_percent: number; watermark_font_size_pt: number;
  professional_overrides: Partial<Record<ProfessionalField, string>>;
  layout_layers: BrandLayer[];
};

export type BrandVariantSettings = Partial<Pick<BrandSettings,
  "margin_top_mm" | "margin_bottom_mm" | "margin_left_mm" | "margin_right_mm" |
  "header_text" | "footer_text" | "header_alignment" | "footer_alignment" |
  "header_divider" | "footer_divider" | "different_first_page" | "first_header_text" | "page_numbers" | "logo_width_mm" |
  "watermark_opacity" | "watermark_position" | "watermark_rotation_deg" | "watermark_width_mm" | "header_fields" | "footer_fields" | "background_scope" | "show_document_title"
>>;
export type BrandVariants = Partial<Record<Exclude<DocumentType, "general">, BrandVariantSettings>>;
export type BrandProfile = {
  id: string; name: string; scope: "personal" | "office"; owner_user_id: string | null;
  revision: number; settings: BrandSettings; variants: BrandVariants; published_version: number | null;
  archived_at: string | null; can_edit: boolean;
};
export type BrandCapabilities = { fonts: BrandFontFamily[]; pdf_available: boolean; ai_available: boolean; image_ai_available: boolean };
export type BrandAsset = {
  id: string; filename: string; kind: "reference" | "logo" | "logo_dark" | "logo_mono" | "watermark" | "background";
  content_type: string;
  analysis: { identified: Record<string, unknown>; estimated: Record<string, unknown>; warnings: string[] };
  size?: number; stored_externally?: boolean;
};
export type BrandVersion = { id: string; version: number; settings: BrandSettings; variants: BrandVariants; created_at: string };
export type ProfessionalData = { fields: { key: ProfessionalField; label: string; value: string; source: string; complete: boolean }[] };
export type DocumentExport = { id: string; document_version: number; brand_version: number; document_type: DocumentType; created_at: string; sha256_pdf: string; sha256_docx: string };

export const defaultBrandSettings: BrandSettings = {
  font_family: "Liberation Serif", heading_font_family: "Liberation Sans", utility_font_family: "Liberation Sans",
  body_size_pt: 12, heading_size_pt: 16, heading_letter_spacing_pt: 0, heading_uppercase: false,
  line_spacing: 1.5, primary_color: "#17324D", accent_color: "#8B6F47", text_color: "#202020", paper_color: "#FFFFFF", paper_size: "A4",
  layout_mode: "structured", background_asset_id: null, background_scope: "all", show_document_title: true,
  margin_top_mm: 30, margin_bottom_mm: 25, margin_left_mm: 30, margin_right_mm: 20,
  header_text: "", footer_text: "", header_alignment: "left", footer_alignment: "center", header_divider: true, footer_divider: true,
  header_font_size_pt: 9, footer_font_size_pt: 9, header_letter_spacing_pt: 0, footer_letter_spacing_pt: 0,
  header_uppercase: false, footer_uppercase: false, header_top_mm: 10, footer_bottom_mm: 8,
  header_divider_thickness_pt: .75, footer_divider_thickness_pt: .75, header_divider_width_percent: 100, footer_divider_width_percent: 100,
  different_first_page: false, first_header_text: "", page_numbers: true,
  logo_asset_id: null, logo_dark_asset_id: null, logo_mono_asset_id: null, logo_width_mm: 30, logo_top_mm: 8,
  watermark_asset_id: null, watermark_text: "", watermark_opacity: 0.12, watermark_position: "diagonal", watermark_rotation_deg: 35, watermark_width_mm: 100,
  watermark_x_percent: 50, watermark_y_percent: 50, watermark_font_size_pt: 100,
  header_fields: ["professional_name", "oab"],
  footer_fields: ["office_name", "professional_address", "professional_phone", "professional_email"],
  professional_overrides: {},
  layout_layers: [],
};

export const brandSettingLabels: Record<keyof BrandSettings, string> = {
  font_family: "Fonte do texto", heading_font_family: "Fonte dos títulos", utility_font_family: "Fonte dos dados auxiliares",
  body_size_pt: "Texto (pt)", heading_size_pt: "Títulos (pt)", heading_letter_spacing_pt: "Espaçamento dos títulos (pt)", heading_uppercase: "Títulos em maiúsculas",
  line_spacing: "Entrelinhas", primary_color: "Cor principal", accent_color: "Cor de destaque", text_color: "Cor do texto", paper_color: "Cor do papel", paper_size: "Papel",
  layout_mode: "Modo de composição", background_asset_id: "Fundo fiel", background_scope: "Páginas com timbrado", show_document_title: "Título automático",
  margin_top_mm: "Margem superior (mm)", margin_bottom_mm: "Margem inferior (mm)", margin_left_mm: "Margem esquerda (mm)", margin_right_mm: "Margem direita (mm)",
  header_text: "Texto adicional do cabeçalho", footer_text: "Texto adicional do rodapé", header_alignment: "Alinhamento do cabeçalho", footer_alignment: "Alinhamento do rodapé", header_divider: "Linha no cabeçalho", footer_divider: "Linha no rodapé",
  header_font_size_pt: "Cabeçalho (pt)", footer_font_size_pt: "Rodapé (pt)", header_letter_spacing_pt: "Espaçamento do cabeçalho", footer_letter_spacing_pt: "Espaçamento do rodapé",
  header_uppercase: "Cabeçalho em maiúsculas", footer_uppercase: "Rodapé em maiúsculas", header_top_mm: "Posição superior do cabeçalho", footer_bottom_mm: "Posição inferior do rodapé",
  header_divider_thickness_pt: "Espessura da linha superior", footer_divider_thickness_pt: "Espessura da linha inferior", header_divider_width_percent: "Largura da linha superior", footer_divider_width_percent: "Largura da linha inferior",
  different_first_page: "Primeira página diferente", first_header_text: "Cabeçalho da primeira página", page_numbers: "Numerar páginas",
  logo_asset_id: "Logotipo principal", logo_dark_asset_id: "Variação para fundo escuro", logo_mono_asset_id: "Variação monocromática",
  logo_width_mm: "Largura do logotipo (mm)", logo_top_mm: "Posição superior do logotipo", watermark_asset_id: "Imagem da marca-d'água", watermark_text: "Texto da marca-d'água",
  watermark_opacity: "Opacidade da marca-d'água", watermark_position: "Posição da marca-d'água", watermark_rotation_deg: "Rotação da marca-d'água", watermark_width_mm: "Largura da marca-d'água (mm)",
  watermark_x_percent: "Posição horizontal da marca-d'água", watermark_y_percent: "Posição vertical da marca-d'água", watermark_font_size_pt: "Tamanho da marca-d'água",
  header_fields: "Dados no cabeçalho", footer_fields: "Dados no rodapé", professional_overrides: "Ajustes desta identidade", layout_layers: "Camadas editáveis",
};

export function effectiveBrandSettings(settings: BrandSettings, variants: BrandVariants, type: DocumentType): BrandSettings {
  return type === "general" ? settings : { ...settings, ...(variants[type] || {}) };
}

export function materializeBrandText(settings: BrandSettings, data?: ProfessionalData): BrandSettings {
  const values = Object.fromEntries((data?.fields || []).map(field => [field.key, settings.professional_overrides[field.key] || field.value]));
  const lines = (keys: ProfessionalField[], custom: string) => [...keys.map(key => values[key]).filter(Boolean), custom].filter(Boolean).join("\n");
  return { ...settings, header_text: lines(settings.header_fields, settings.header_text), footer_text: lines(settings.footer_fields, settings.footer_text),
    layout_layers: settings.layout_layers.map(layer => layer.binding ? { ...layer, text: values[layer.binding] || "Dado ainda não cadastrado" } : layer) };
}

export function moveBrandLayerToEdge(layers: BrandLayer[], selectedId: string, edge: "back" | "front"): BrandLayer[] {
  const selected = layers.find(layer => layer.id === selectedId);
  if (!selected) return layers;
  const rest = layers.filter(layer => layer.id !== selectedId).sort((a, b) => a.z_index - b.z_index);
  return (edge === "back" ? [selected, ...rest] : [...rest, selected]).map((layer, z_index) => ({ ...layer, z_index }));
}

export function reorderBrandLayer(layers: BrandLayer[], sourceId: string, targetId: string): BrandLayer[] {
  if (sourceId === targetId) return layers;
  const ordered = [...layers].sort((a, b) => a.z_index - b.z_index);
  const source = ordered.findIndex(layer => layer.id === sourceId);
  const target = ordered.findIndex(layer => layer.id === targetId);
  if (source < 0 || target < 0) return layers;
  const [item] = ordered.splice(source, 1);
  ordered.splice(target, 0, item);
  return ordered.map((layer, z_index) => ({ ...layer, z_index }));
}

export function requiredBrandMargins(settings: BrandSettings) {
  let top = settings.margin_top_mm; let bottom = settings.margin_bottom_mm;
  if (settings.layout_mode !== "composed") return { top, bottom };
  const paperHeight = settings.paper_size === "A4" ? 297 : 279.4;
  let headerBottom: number | undefined; let footerTop: number | undefined;
  for (const layer of settings.layout_layers) {
    if (layer.visible === false || layer.role === "watermark") continue;
    if (layer.y_percent < 35 && layer.y_percent + layer.height_percent <= 50) headerBottom = Math.max(headerBottom || 0, layer.y_percent + layer.height_percent);
    if (layer.y_percent >= 55) footerTop = Math.min(footerTop ?? 100, layer.y_percent);
  }
  if (headerBottom !== undefined) top = Math.max(top, Math.ceil(headerBottom * paperHeight / 100 + 4));
  if (footerTop !== undefined) bottom = Math.max(bottom, Math.ceil((100 - footerTop) * paperHeight / 100 + 4));
  return { top, bottom };
}

export type BrandPreflightIssue = { level: "error" | "warning" | "ok"; text: string };
export function brandPreflight(settings: BrandSettings, assets: BrandAsset[], professional?: ProfessionalData | null): BrandPreflightIssue[] {
  const issues: BrandPreflightIssue[] = [];
  const margins = requiredBrandMargins(settings);
  if (margins.top > 80 || margins.bottom > 80) issues.push({ level: "error", text: "Cabeçalho ou rodapé alto demais: reduza as camadas para liberar a área do texto." });
  else if (settings.margin_top_mm < margins.top || settings.margin_bottom_mm < margins.bottom) issues.push({ level: "error", text: `Ajuste a área segura para ${margins.top} mm no topo e ${margins.bottom} mm no rodapé.` });
  const assetIds = new Set(assets.map(asset => asset.id));
  if (settings.layout_mode === "composed" && settings.layout_layers.some(layer => layer.visible !== false && layer.kind === "image" && (!layer.asset_id || !assetIds.has(layer.asset_id)))) issues.push({ level: "error", text: "Existe uma imagem visível ausente ou sem acesso." });
  if (settings.layout_layers.some(layer => layer.visible !== false && layer.opacity <= .02)) issues.push({ level: "warning", text: "Uma camada está praticamente invisível; confira a intensidade." });
  if (settings.layout_layers.some(layer => layer.visible === false)) issues.push({ level: "warning", text: "Existem camadas ocultas; elas não aparecerão nos documentos publicados." });
  const completed = new Set((professional?.fields || []).filter(field => field.complete).map(field => field.key));
  if (settings.layout_layers.some(layer => layer.visible !== false && !!layer.binding && !completed.has(layer.binding))) issues.push({ level: "error", text: "Complete os dados profissionais usados nas camadas automáticas." });
  if (!issues.length) issues.push({ level: "ok", text: "Imagens, dados e área segura estão prontos para a prévia final." });
  return issues;
}

// Reference metadata is untrusted. Only primitive visual tokens are candidates for manual review.
export function identifiedBrandSettings(identified: Record<string, unknown>): Partial<BrandSettings> {
  const scalarKeys = new Set<keyof BrandSettings>([
    "font_family", "heading_font_family", "utility_font_family", "body_size_pt", "heading_size_pt", "heading_letter_spacing_pt", "heading_uppercase", "line_spacing", "primary_color", "accent_color", "text_color",
    "paper_size", "margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "header_text", "footer_text",
    "header_alignment", "footer_alignment", "header_divider", "footer_divider", "different_first_page", "first_header_text", "page_numbers", "logo_width_mm",
    "watermark_text", "watermark_opacity", "watermark_position", "watermark_rotation_deg", "watermark_width_mm",
  ]);
  const candidates = Object.fromEntries(Object.entries(identified).filter(([key, value]) => {
    if (!scalarKeys.has(key as keyof BrandSettings)) return false;
    return typeof value === typeof defaultBrandSettings[key as keyof BrandSettings];
  })) as Partial<BrandSettings>;
  if (Array.isArray(identified.fonts) && identified.fonts.length === 1 && BRAND_FONT_FAMILIES.includes(identified.fonts[0])) candidates.font_family = identified.fonts[0];
  const margins = identified.margins_mm;
  if (margins && typeof margins === "object" && !Array.isArray(margins)) {
    for (const side of ["top", "bottom", "left", "right"] as const) {
      const value = (margins as Record<string, unknown>)[side];
      if (typeof value === "number" && Number.isFinite(value) && value >= (["top", "bottom"].includes(side) ? 20 : 15) && value <= (["top", "bottom"].includes(side) ? 80 : 50)) candidates[`margin_${side}_mm`] = value;
    }
  }
  for (const key of ["header_text", "footer_text"] as const) {
    const texts = identified[key];
    if (Array.isArray(texts) && texts.length === 1 && typeof texts[0] === "string" && texts[0].length <= 500) candidates[key] = texts[0];
  }
  return candidates;
}

export function exportFilename(title: string, format: "pdf" | "docx") {
  return `${title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").trim().slice(0, 140) || "documento"}.${format}`;
}
