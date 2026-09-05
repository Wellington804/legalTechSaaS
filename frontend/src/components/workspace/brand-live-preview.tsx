"use client";
import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { Globe2, Mail, MapPin, MessageCircle, Phone, Sparkles, Trash2 } from "lucide-react";
import { apiBlob } from "@/lib/api-client";
import {
  BRAND_FONT_FAMILIES, documentTypeLabels, materializeBrandText, type BrandAsset, type BrandFontFamily,
  type BrandLayer, type BrandSettings, type DocumentType, type ProfessionalData,
} from "@/lib/branding";

const alignments = { left: "text-left", center: "text-center", right: "text-right" } as const;
const serifFamilies = new Set(["Liberation Serif", "DejaVu Serif", "DejaVu Serif Condensed", "Noto Serif", "Noto Serif Display", "Caladea", "Cambria", "Tinos", "Times New Roman"]);
const monoFamilies = new Set(["Liberation Mono", "DejaVu Sans Mono", "Noto Mono", "Noto Sans Mono", "Cousine", "Courier New"]);
const family = (name: string) => {
  const safe = BRAND_FONT_FAMILIES.includes(name as BrandFontFamily) ? name : "Liberation Serif";
  const fallback = monoFamilies.has(safe) ? "ui-monospace, Consolas, monospace" : serifFamilies.has(safe) ? "ui-serif, Georgia, serif" : "ui-sans-serif, Arial, sans-serif";
  return `"${safe}", ${fallback}`;
};
const samples: Record<DocumentType, { title: string; paragraphs: string[] }> = {
  general: { title: "Documento jurídico", paragraphs: ["Conteúdo do documento produzido no LexFlow.", "Revise todos os dados antes de exportar."] },
  petition: { title: "Excelentíssimo Senhor Doutor Juiz de Direito", paragraphs: ["Processo nº 0000000-00.0000.0.00.0000", "A parte, por seu advogado, apresenta a presente manifestação."] },
  contract: { title: "Contrato de prestação de serviços", paragraphs: ["Pelo presente instrumento particular, as partes ajustam as condições descritas neste documento.", "As cláusulas devem ser revisadas para o caso concreto."] },
  power_of_attorney: { title: "Procuração", paragraphs: ["O outorgante nomeia seu advogado para os fins expressamente descritos.", "Os poderes especiais devem ser conferidos pelo cliente."] },
  notice: { title: "Notificação extrajudicial", paragraphs: ["O destinatário fica formalmente cientificado dos fatos descritos.", "Prazo e consequências dependem de conferência jurídica."] },
  correspondence: { title: "Correspondência profissional", paragraphs: ["Prezado(a),", "Encaminhamos esta comunicação para acompanhamento e providências."] },
};

export function PrivateBrandImage({ asset, endpoint, alt, className, style, fallback = null }: { asset?: BrandAsset; endpoint?: string; alt: string; className: string; style?: CSSProperties; fallback?: ReactNode }) {
  const [url, setUrl] = useState(""); const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true; let objectUrl = ""; setUrl(""); setFailed(false);
    const path = endpoint || (asset ? `/branding/assets/${asset.id}/download?inline=true` : "");
    if (!path) { setFailed(true); return; }
    apiBlob(path).then(blob => {
      if (!active || !blob.type.startsWith("image/")) { if (active) setFailed(true); return; }
      objectUrl = URL.createObjectURL(blob); setUrl(objectUrl);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [asset, endpoint]);
  return url ? <img src={url} alt={alt} className={className} style={style} /> : failed ? fallback : null;
}

const contactIcons = { whatsapp: MessageCircle, phone: Phone, email: Mail, location: MapPin, website: Globe2 } as const;
function LayerContent({ layer, assets, compact }: { layer: BrandLayer; assets: BrandAsset[]; compact: boolean }) {
  if (layer.kind === "rectangle") return <span className="absolute inset-0" style={{ backgroundColor: layer.color }} />;
  if (layer.kind === "line") return <span className="absolute left-0 right-0 top-1/2" style={{ borderTop: `${Math.max(1, layer.line_thickness_pt * (compact ? .5 : .8))}px solid ${layer.color}` }} />;
  if (layer.kind === "image") return <PrivateBrandImage asset={assets.find(asset => asset.id === layer.asset_id)} alt={layer.label} className="h-full w-full object-contain" style={{ filter: `contrast(${layer.image_contrast ?? 1})` }} fallback={<span className="grid h-full w-full place-items-center bg-rose-100/80 text-[7px] text-rose-900">Imagem indisponível</span>} />;
  const Icon = layer.icon === "none" ? null : contactIcons[layer.icon];
  return <span className="flex h-full w-full items-center gap-[4%] whitespace-pre-line" style={{ color: layer.color, fontFamily: family(layer.font_family), fontSize: `${Math.max(4, layer.font_size_pt * (compact ? .32 : .52))}px`, fontWeight: layer.font_weight, letterSpacing: `${layer.letter_spacing_pt}px`, textAlign: layer.alignment, textTransform: layer.uppercase ? "uppercase" : undefined, justifyContent: layer.alignment === "center" ? "center" : layer.alignment === "right" ? "flex-end" : "flex-start" }}>
    {Icon && <Icon aria-hidden="true" className="h-[1.35em] w-[1.35em] shrink-0" strokeWidth={1.8} />}{layer.text}
  </span>;
}

export function BrandLivePreview({ name, settings, documentType = "general", professionalData, assets = [], compact = false, referenceOverlay, selectedLayerId, onSelectLayer, onClearSelection, onChangeLayer, onDeleteLayer, showSafeArea = false, showPjeGuide = false, onIsolateAsset, zoom = 100, onZoomChange }: {
  name: string; settings: BrandSettings; documentType?: DocumentType; professionalData?: ProfessionalData; assets?: BrandAsset[]; compact?: boolean;
  referenceOverlay?: { assetId: string; page: number; opacity: number; blendMode?: CSSProperties["mixBlendMode"] };
  selectedLayerId?: string; onSelectLayer?: (id: string) => void; onClearSelection?: () => void; onChangeLayer?: (layer: BrandLayer) => void; onDeleteLayer?: (id: string) => void; showSafeArea?: boolean; showPjeGuide?: boolean; onIsolateAsset?: (assetId: string) => Promise<void>; zoom?: number;
  onZoomChange?: (updater: number | ((current: number) => number)) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = containerRef.current;
    if (!el || compact || !onZoomChange) return;
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const step = e.ctrlKey ? 5 : 10;
      const change = e.deltaY < 0 ? step : -step;
      onZoomChange(current => Math.max(40, Math.min(250, current + change)));
    };
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [compact, onZoomChange]);
  const tokens = materializeBrandText(settings, professionalData); const sample = samples[documentType] || samples.general;
  const logo = assets.find(asset => asset.id === tokens.logo_asset_id); const watermark = assets.find(asset => asset.id === tokens.watermark_asset_id); const background = assets.find(asset => asset.id === tokens.background_asset_id);
  const watermarkTransform = tokens.watermark_position === "diagonal" ? `translate(-50%, -50%) rotate(${-tokens.watermark_rotation_deg}deg)` : "translate(-50%, -50%)";
  const exact = tokens.layout_mode === "exact"; const composed = tokens.layout_mode === "composed"; const [guides, setGuides] = useState({ x: false, y: false });
  const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));
  const startEdit = (event: ReactPointerEvent<HTMLElement>, layer: BrandLayer, mode: "move" | "nw" | "ne" | "sw" | "se" | "rotate" = "move") => {
    if (!onChangeLayer || compact || layer.locked) return;
    event.preventDefault(); event.stopPropagation(); onSelectLayer?.(layer.id);
    (event.currentTarget.closest("[data-brand-layer]") as HTMLElement | null)?.focus({ preventScroll: true });
    const paper = event.currentTarget.closest("[data-brand-paper]")?.getBoundingClientRect(); if (!paper) return;
    const origin = { x: event.clientX, y: event.clientY, left: layer.x_percent, top: layer.y_percent, width: layer.width_percent, height: layer.height_percent };
    const move = (pointer: PointerEvent) => {
      const dx = (pointer.clientX - origin.x) / paper.width * 100; const dy = (pointer.clientY - origin.y) / paper.height * 100;
      if (mode === "rotate") {
        const centerX = paper.left + (origin.left + origin.width / 2) * paper.width / 100; const centerY = paper.top + (origin.top + origin.height / 2) * paper.height / 100;
        const raw = Math.round(Math.atan2(pointer.clientY - centerY, pointer.clientX - centerX) * 180 / Math.PI + 90);
        onChangeLayer({ ...layer, rotation_deg: ((raw + 180) % 360 + 360) % 360 - 180 }); return;
      }
      if (mode !== "move") {
        let left = origin.left; let top = origin.top; let width = origin.width; let height = origin.height;
        if (mode.includes("e")) width = clamp(origin.width + dx, 1, 100 - origin.left);
        if (mode.includes("s")) height = clamp(origin.height + dy, 1, 100 - origin.top);
        if (mode.includes("w")) { left = clamp(origin.left + dx, 0, origin.left + origin.width - 1); width = origin.width + origin.left - left; }
        if (mode.includes("n")) { top = clamp(origin.top + dy, 0, origin.top + origin.height - 1); height = origin.height + origin.top - top; }
        onChangeLayer({ ...layer, x_percent: left, y_percent: top, width_percent: width, height_percent: height }); return;
      }
      let left = clamp(origin.left + dx, 0, 100 - layer.width_percent); let top = clamp(origin.top + dy, 0, 100 - layer.height_percent);
      const snapX = Math.abs(left + layer.width_percent / 2 - 50) < 1; const snapY = Math.abs(top + layer.height_percent / 2 - 50) < 1;
      if (snapX) left = 50 - layer.width_percent / 2; if (snapY) top = 50 - layer.height_percent / 2;
      setGuides({ x: snapX, y: snapY }); onChangeLayer({ ...layer, x_percent: left, y_percent: top });
    };
    const stop = () => { setGuides({ x: false, y: false }); window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", stop, { once: true });
  };
  const keyboardMove = (event: KeyboardEvent<HTMLDivElement>, layer: BrandLayer) => {
    if (event.key === "Escape") { onClearSelection?.(); return; }
    if (event.key === "Delete" || event.key === "Backspace") {
      if (!layer.locked && onDeleteLayer) { event.preventDefault(); onDeleteLayer(layer.id); }
      return;
    }
    if (!onChangeLayer || layer.locked) return;
    const amount = event.shiftKey ? 2 : .5; let x = layer.x_percent; let y = layer.y_percent;
    if (event.key === "ArrowLeft") x -= amount; else if (event.key === "ArrowRight") x += amount; else if (event.key === "ArrowUp") y -= amount; else if (event.key === "ArrowDown") y += amount; else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectLayer?.(layer.id); return; } else return;
    event.preventDefault(); onChangeLayer({ ...layer, x_percent: clamp(x, 0, 100 - layer.width_percent), y_percent: clamp(y, 0, 100 - layer.height_percent) });
  };
  return <section aria-label={`Pré-visualização da identidade para ${documentTypeLabels[documentType]}`} className="min-w-0 space-y-2">
    {!compact && <div><h3 className="text-sm font-semibold">Documento em tempo real</h3><p className="text-xs text-zinc-400">Amostra visual de {documentTypeLabels[documentType].toLocaleLowerCase("pt-BR")}. Confira também o PDF real.</p></div>}
    <div ref={containerRef} className={compact ? "" : "overflow-x-auto overflow-y-visible pb-4 pt-1 transition-transform"}>
    <div className={`relative mx-auto aspect-[210/297] ${compact ? "w-full max-w-[15rem]" : ""}`} style={compact ? undefined : { width: `${zoom}%`, maxWidth: `${36 * zoom / 100}rem` }}>
    <div data-brand-paper onPointerDown={() => onClearSelection?.()} className="paper-shadow-3d absolute left-0 top-0 h-full w-full overflow-hidden text-zinc-900 shadow-2xl rounded-sm ring-1 ring-black/5"
      style={{ fontFamily: family(tokens.font_family), color: tokens.text_color, backgroundColor: tokens.paper_color, padding: `${Math.min(tokens.margin_top_mm / 2.97, 28)}% ${Math.min(tokens.margin_right_mm / 2.1, 24)}% ${Math.min(tokens.margin_bottom_mm / 2.97, 28)}% ${Math.min(tokens.margin_left_mm / 2.1, 24)}%`, width: compact ? "100%" : `${10000 / zoom}%`, height: compact ? "100%" : `${10000 / zoom}%`, transform: compact ? undefined : `scale(${zoom / 100})`, transformOrigin: "top left" }}>
      {exact && background && <PrivateBrandImage asset={background} alt="Fundo fiel do papel timbrado" className="pointer-events-none absolute inset-0 h-full w-full object-fill" />}
      {!exact && !composed && <header className={`absolute left-[8%] right-[8%] min-h-[9%] pb-2 whitespace-pre-line ${alignments[tokens.header_alignment]}`} style={{ top: `${(logo ? tokens.logo_top_mm : tokens.header_top_mm) / 2.97}%`, borderColor: tokens.accent_color, fontFamily: family(tokens.utility_font_family), fontSize: `${Math.max(5, tokens.header_font_size_pt * (compact ? .42 : .6))}px`, letterSpacing: `${tokens.header_letter_spacing_pt}px`, textTransform: tokens.header_uppercase ? "uppercase" : undefined }}>
        <PrivateBrandImage asset={logo} alt="Logotipo selecionado" className={`mb-1 max-h-12 max-w-[45%] object-contain ${tokens.header_alignment === "center" ? "mx-auto" : tokens.header_alignment === "right" ? "ml-auto" : ""}`} />
        <div>{tokens.header_text || name}</div>{tokens.header_divider && <span className={`mt-2 block ${tokens.header_alignment === "center" ? "mx-auto" : tokens.header_alignment === "right" ? "ml-auto" : ""}`} style={{ width: `${tokens.header_divider_width_percent}%`, borderBottom: `${Math.max(1, tokens.header_divider_thickness_pt)}px solid ${tokens.accent_color}` }} />}
      </header>}
      {!exact && !composed && (tokens.watermark_text || watermark) && <div aria-hidden="true" className="pointer-events-none absolute w-[72%] text-center font-semibold" style={{ left: `${tokens.watermark_x_percent}%`, top: `${tokens.watermark_y_percent}%`, color: tokens.primary_color, opacity: tokens.watermark_opacity, transform: watermarkTransform, fontSize: `${Math.max(14, tokens.watermark_font_size_pt * (compact ? .18 : .28))}px` }}>{watermark ? <PrivateBrandImage asset={watermark} alt="" className="mx-auto max-h-40 max-w-full object-contain" /> : tokens.watermark_text}</div>}
      {showSafeArea && !compact && <div aria-hidden="true" className="pointer-events-none absolute border border-dashed border-emerald-600/70" style={{ left: `${tokens.margin_left_mm / 2.1}%`, right: `${tokens.margin_right_mm / 2.1}%`, top: `${tokens.margin_top_mm / 2.97}%`, bottom: `${tokens.margin_bottom_mm / 2.97}%`, zIndex: 110 }}><span className="absolute left-1 top-1 rounded bg-emerald-700/90 px-1 text-[7px] text-white">Área segura do texto</span></div>}
      {showPjeGuide && !compact && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-0 top-0 border-2 border-dashed border-rose-500/80 bg-rose-500/10 flex flex-col items-end p-1 shadow-sm"
          style={{ width: "28.5%", height: "10.1%", zIndex: 125 }}
        >
          <span className="rounded bg-rose-700/95 px-1 py-0.5 text-[6px] font-semibold text-white tracking-wider uppercase">
            Protocolo PJe / Tribunais
          </span>
          <span className="text-[5px] text-rose-800 font-bold mt-0.5">Área reservada (30x60mm)</span>
        </div>
      )}
      {guides.x && <span aria-hidden="true" className="pointer-events-none absolute bottom-0 left-1/2 top-0 border-l border-blue-500" style={{ zIndex: 119 }} />}{guides.y && <span aria-hidden="true" className="pointer-events-none absolute left-0 right-0 top-1/2 border-t border-blue-500" style={{ zIndex: 119 }} />}
      {composed && (tokens.layout_layers || []).filter(layer => layer.page_scope !== "continuation" && layer.visible !== false).sort((a, b) => a.z_index - b.z_index).map(layer => <div key={layer.id}
        data-brand-layer={layer.id}
        role={onSelectLayer && !compact ? "button" : undefined} tabIndex={onSelectLayer && !compact ? 0 : undefined} aria-label={onSelectLayer && !compact ? `Editar ${layer.label}${layer.locked ? " (bloqueada)" : ""}` : undefined}
        onClick={event => { event.stopPropagation(); onSelectLayer?.(layer.id); }} onKeyDown={event => keyboardMove(event, layer)} onPointerDown={event => startEdit(event, layer)}
        className={`absolute ${onSelectLayer && !compact ? layer.locked ? "cursor-default" : "cursor-move touch-none" : "pointer-events-none"} ${selectedLayerId === layer.id ? "outline outline-2 outline-blue-500 outline-offset-1" : ""}`}
        style={{ left: `${layer.x_percent}%`, top: `${layer.y_percent}%`, width: `${layer.width_percent}%`, height: `${layer.height_percent}%`, opacity: layer.opacity, transform: `rotate(${layer.rotation_deg}deg)`, zIndex: layer.z_index }}>
        <LayerContent layer={layer} assets={assets} compact={compact} />
        {selectedLayerId === layer.id && onChangeLayer && !compact && !layer.locked && <>{(["nw", "ne", "sw", "se"] as const).map(handle => <span key={handle} aria-hidden="true" onPointerDown={event => startEdit(event, layer, handle)} className={`absolute h-4 w-4 rounded-full border-2 border-white bg-blue-600 shadow touch-none ${handle.includes("n") ? "-top-2" : "-bottom-2"} ${handle.includes("w") ? "-left-2" : "-right-2"} ${handle === "nw" || handle === "se" ? "cursor-nwse-resize" : "cursor-nesw-resize"}`} />)}<span aria-hidden="true" onPointerDown={event => startEdit(event, layer, "rotate")} className="absolute -top-8 left-1/2 h-4 w-4 -translate-x-1/2 cursor-grab rounded-full border-2 border-white bg-amber-500 shadow touch-none" /></>}
      </div>)}

      {/* Contextual Floating Toolbar for Selected Layer */}
      {(() => {
        const activeLayer = (tokens.layout_layers || []).find(l => l.id === selectedLayerId);
        if (!activeLayer || !onChangeLayer || compact || activeLayer.locked) return null;
        const placeBelow = activeLayer.y_percent < 12;
        return (
          <div
            className="absolute z-[160] flex flex-wrap items-center gap-1.5 rounded-xl border border-zinc-700/80 bg-zinc-900/95 px-2.5 py-1.5 shadow-2xl backdrop-blur-md text-zinc-200 text-xs transition-all pointer-events-auto"
            style={{
              left: `${Math.min(60, Math.max(2, activeLayer.x_percent))}%`,
              top: placeBelow
                ? `${activeLayer.y_percent + activeLayer.height_percent + 1.5}%`
                : `${activeLayer.y_percent - 1.5}%`,
              transform: placeBelow ? "none" : "translateY(-100%)",
            }}
            onPointerDown={e => e.stopPropagation()}
          >
            <span className="font-semibold text-[11px] text-blue-400 max-w-[8rem] truncate border-r border-zinc-700 pr-1.5">
              {activeLayer.label || "Camada"}
            </span>

            {activeLayer.kind === "image" && (
              <>
                {activeLayer.asset_id && onIsolateAsset && (
                  <button
                    type="button"
                    className="px-2 py-0.5 rounded text-[11px] bg-blue-600 hover:bg-blue-500 text-white font-medium transition flex items-center gap-1 shadow-sm"
                    onClick={() => onIsolateAsset(activeLayer.asset_id!)}
                    title="Remover fundo branco e tornar transparente"
                  >
                    <Sparkles size={12} /> Transparência
                  </button>
                )}
                <div className="flex items-center gap-1 pl-1 border-l border-zinc-800">
                  <span className="text-[10px] text-zinc-400">Opacidade</span>
                  <input
                    type="range"
                    min="0.05"
                    max="1"
                    step="0.05"
                    className="w-12 h-1 accent-blue-500 cursor-pointer"
                    value={activeLayer.opacity}
                    onChange={e => onChangeLayer({ ...activeLayer, opacity: e.target.valueAsNumber })}
                  />
                </div>
              </>
            )}

            {(activeLayer.kind === "text" || activeLayer.kind === "icon_text") && (
              <>
                <input
                  type="color"
                  className="h-5 w-6 rounded border border-zinc-700 bg-transparent p-0 cursor-pointer"
                  value={activeLayer.color}
                  onChange={e => onChangeLayer({ ...activeLayer, color: e.target.value })}
                  title="Cor do texto"
                />
                <div className="flex items-center gap-0.5 border-l border-zinc-800 pl-1">
                  <button
                    type="button"
                    className="px-1.5 py-0.5 rounded text-[11px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                    onClick={() => onChangeLayer({ ...activeLayer, font_size_pt: Math.max(5, activeLayer.font_size_pt - 0.5) })}
                  >
                    A-
                  </button>
                  <span className="text-[10px] font-mono px-0.5">{activeLayer.font_size_pt}pt</span>
                  <button
                    type="button"
                    className="px-1.5 py-0.5 rounded text-[11px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                    onClick={() => onChangeLayer({ ...activeLayer, font_size_pt: Math.min(36, activeLayer.font_size_pt + 0.5) })}
                  >
                    A+
                  </button>
                </div>
              </>
            )}

            {activeLayer.kind === "line" && (
              <>
                <input
                  type="color"
                  className="h-5 w-6 rounded border border-zinc-700 bg-transparent p-0 cursor-pointer"
                  value={activeLayer.color}
                  onChange={e => onChangeLayer({ ...activeLayer, color: e.target.value })}
                  title="Cor da linha"
                />
                <div className="flex items-center gap-1 pl-1 border-l border-zinc-800">
                  <span className="text-[10px] text-zinc-400">Espessura</span>
                  <input
                    type="range"
                    min="0.25"
                    max="6"
                    step="0.25"
                    className="w-12 h-1 accent-blue-500 cursor-pointer"
                    value={activeLayer.line_thickness_pt}
                    onChange={e => onChangeLayer({ ...activeLayer, line_thickness_pt: e.target.valueAsNumber })}
                  />
                </div>
              </>
            )}

            <button
              type="button"
              className="px-1.5 py-0.5 rounded text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition"
              onClick={() => onChangeLayer({ ...activeLayer, x_percent: 50 - activeLayer.width_percent / 2 })}
              title="Centralizar horizontalmente na página"
            >
              Centralizar
            </button>

            {onDeleteLayer && (
              <button
                type="button"
                className="p-1 rounded text-rose-400 hover:text-rose-200 hover:bg-rose-950/40 transition ml-0.5"
                onClick={() => onDeleteLayer(activeLayer.id)}
                title="Excluir camada"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        );
      })()}

      <main style={{ fontSize: `${Math.max(6, tokens.body_size_pt * (compact ? .48 : .65))}px`, lineHeight: tokens.line_spacing }}><p className="mb-[5%] text-right text-[0.8em]">Cidade, 2 de setembro de 2026.</p>{tokens.show_document_title && <h4 className={`mb-[8%] text-center font-semibold ${tokens.heading_uppercase ? "uppercase" : ""}`} style={{ color: tokens.primary_color, fontFamily: family(tokens.heading_font_family), letterSpacing: `${tokens.heading_letter_spacing_pt}px`, fontSize: `${Math.max(8, tokens.heading_size_pt * (compact ? .52 : .72))}px` }}>{sample?.title || "Documento jurídico"}</h4>}{(sample?.paragraphs || []).map(paragraph => <p key={paragraph} className="mb-[5%] text-justify">{paragraph}</p>)}<div className="mt-[10%] space-y-[5%]"><div className="h-px bg-zinc-200" /><div className="h-px w-5/6 bg-zinc-200" /><div className="h-px w-4/6 bg-zinc-200" /></div></main>
      {!exact && !composed && <footer className={`absolute left-[8%] right-[8%] pt-2 whitespace-pre-line ${alignments[tokens.footer_alignment]}`} style={{ bottom: `${tokens.footer_bottom_mm / 2.97}%`, borderColor: tokens.accent_color, fontFamily: family(tokens.utility_font_family), fontSize: `${Math.max(5, tokens.footer_font_size_pt * (compact ? .38 : .55))}px`, letterSpacing: `${tokens.footer_letter_spacing_pt}px`, textTransform: tokens.footer_uppercase ? "uppercase" : undefined }}>{tokens.footer_divider && <span className={`mb-2 block ${tokens.footer_alignment === "center" ? "mx-auto" : tokens.footer_alignment === "right" ? "ml-auto" : ""}`} style={{ width: `${tokens.footer_divider_width_percent}%`, borderTop: `${Math.max(1, tokens.footer_divider_thickness_pt)}px solid ${tokens.accent_color}` }} />}{tokens.footer_text || "Informações profissionais"}{tokens.page_numbers && <span className="float-right">1</span>}</footer>}
      {composed && tokens.page_numbers && <span className="absolute bottom-[1.5%] right-[2%] text-[7px]">1</span>}{exact && tokens.page_numbers && <span className="absolute bottom-[2%] right-[3%] text-[7px]">1</span>}
      {!!referenceOverlay?.opacity && <PrivateBrandImage endpoint={`/branding/assets/${referenceOverlay.assetId}/pages/${referenceOverlay.page}`} alt="Comparação com a referência" className="pointer-events-none absolute inset-0 h-full w-full object-fill" style={{ opacity: referenceOverlay.opacity, mixBlendMode: referenceOverlay.blendMode }} />}
    </div>
    </div>
    </div>
  </section>;
}
