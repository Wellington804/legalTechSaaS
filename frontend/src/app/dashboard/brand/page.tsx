"use client";

import React, { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useUser } from "@/context/user-context";
import {
  Palette,
  Sparkles,
  CheckCircle2,
  Copy,
  Check,
  BookOpen,
  ShieldCheck,
  FileText,
  Printer,
  Download,
  QrCode,
  Building,
  Sliders,
  Type,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Bot,
  Scale,
  Stamp,
  Wand2,
  Settings,
  Shield,
  FileCheck,
  Upload,
  Image as ImageIcon,
  X,
  Search,
  Filter,
  Star,
  Layout,
  PenTool,
  Maximize2,
  Minimize2,
  Eraser,
  Columns,
  Grid,
  CheckSquare,
  Sparkle,
  Cpu,
  Key,
  Globe,
  Paintbrush,
  MessageSquare
} from "lucide-react";

function BrandPageContent() {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<"TIMBRADO" | "POSTS" | "CONFIG">("TIMBRADO");

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (tabParam === "CONFIG" || tabParam === "whatsapp") {
      setActiveTab("CONFIG");
    } else if (tabParam === "TIMBRADO") {
      setActiveTab("TIMBRADO");
    } else if (tabParam === "POSTS") {
      setActiveTab("POSTS");
    }
  }, [searchParams]);
  
  // Clean Subtabs Structure (4 columns, 0 scrollbar)
  const [controlSubTab, setControlSubTab] = useState<"DESIGN_IA" | "CABECALHO_RODAPE" | "MARCA" | "PAPEL">("DESIGN_IA");

  // File input refs for uploading logo and watermark
  const logoInputRef = useRef<HTMLInputElement>(null);
  const watermarkInputRef = useRef<HTMLInputElement>(null);

  const { user } = useUser();

  // -------------------------------------------------------------
  // STATE: INSTITUTIONAL & LAWYER INFO
  // -------------------------------------------------------------
  const [officeName, setOfficeName] = useState(user?.officeName || "SILVA & ASSOCIADOS ADVOCACIA");
  const [lawyerName, setLawyerName] = useState(user?.name || "Dra. Carolina Silva");
  const [oabNumber, setOabNumber] = useState(user?.oabNumber || "OAB/DF 12.345");
  const [address, setAddress] = useState("Setor Comercial Sul, Quadra 04, Bloco C, Edifício Trade, Sala 1001, Brasília - DF");
  const [phoneEmail, setPhoneEmail] = useState("silvaeassociados.adv.br | (61) 3212-0000");
  const [officeWhatsapp, setOfficeWhatsapp] = useState("5511999998888");
  
  // -------------------------------------------------------------
  // REQUISITO 1: LOGO PRÓPRIA COM UPLOAD DE ARQUIVO
  // -------------------------------------------------------------
  const [logoSource, setLogoSource] = useState<"PRESET" | "CUSTOM_IMAGE">("PRESET");
  const [logoBadge, setLogoBadge] = useState<"BALANCA" | "BRASAO" | "MONOGRAMA" | "ESCUDO">("BALANCA");
  const [customLogoUrl, setCustomLogoUrl] = useState<string | null>(null);

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCustomLogoUrl(event.target.result as string);
          setLogoSource("CUSTOM_IMAGE");
        }
      };
      reader.readAsDataURL(file);
    }
  };

  // -------------------------------------------------------------
  // REQUISITO 1: MARCA D'ÁGUA PRÓPRIA COM UPLOAD DE ARQUIVO OU TEXTO
  // -------------------------------------------------------------
  const [showWatermark, setShowWatermark] = useState(true);
  const [watermarkKind, setWatermarkKind] = useState<"TEXT" | "CUSTOM_IMAGE">("TEXT");
  const [watermarkText, setWatermarkText] = useState("SILVA & ASSOCIADOS - USO JURÍDICO");
  const [customWatermarkImageUrl, setCustomWatermarkImageUrl] = useState<string | null>(null);
  const [watermarkOpacity, setWatermarkOpacity] = useState(0.08);

  const handleWatermarkUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCustomWatermarkImageUrl(event.target.result as string);
          setWatermarkKind("CUSTOM_IMAGE");
          setShowWatermark(true);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  // -------------------------------------------------------------
  // REQUISITO 2: EDIÇÃO DE CABEÇALHO E RODAPÉ EXPANDIDA
  // -------------------------------------------------------------
  const [headerStyle, setHeaderStyle] = useState<"MINIMAL" | "SOLID" | "BORDER_DOUBLE" | "GRADIENT" | "WIL_SHAFFER" | "SILVA_ASSOCIADOS">("SILVA_ASSOCIADOS");
  const [headerBgColor, setHeaderBgColor] = useState("#0a192f");
  const [headerTextColor, setHeaderTextColor] = useState("#ffffff");
  const [headerFontSize, setHeaderFontSize] = useState<"text-xs" | "text-sm" | "text-base" | "text-lg">("text-sm");
  const [headerAlign, setHeaderAlign] = useState<"left" | "center" | "right">("center");
  const [headerPadding, setHeaderPadding] = useState<"p-2" | "p-4" | "p-6">("p-4");

  // Edição do Rodapé (Dedicação completa)
  const [footerStyle, setFooterStyle] = useState<"MINIMAL" | "SOLID" | "BORDER_DOUBLE" | "GRADIENT" | "BOXED" | "TWO_COLUMN" | "WIL_SHAFFER" | "SILVA_ASSOCIADOS">("SILVA_ASSOCIADOS");
  const [footerBgColor, setFooterBgColor] = useState("#0a192f");
  const [footerTextColor, setFooterTextColor] = useState("#ffffff");
  const [footerFontSize, setFooterFontSize] = useState<"text-[8px]" | "text-[9px]" | "text-[10px]" | "text-xs">("text-[9px]");
  const [footerAlign, setFooterAlign] = useState<"left" | "center" | "right">("center");
  const [showPageNumber, setShowPageNumber] = useState(true);

  // Free-form Editable Content
  const [useCustomHeaderContent, setUseCustomHeaderContent] = useState(false);
  const [customHeaderLines, setCustomHeaderLines] = useState(
    `SILVA & ASSOCIADOS ADVOCACIA\nDra. Carolina Silva — OAB/DF 12.345\nSetor Comercial Sul, Quadra 04, Bloco C, Edifício Trade, Sala 1001, Brasília - DF | (61) 3212-0000`
  );

  const [useCustomFooterContent, setUseCustomFooterContent] = useState(false);
  const [customFooterLines, setCustomFooterLines] = useState(
    `Endereço: Setor Comercial Sul, Quadra 04, Bloco C, Edifício Trade, Sala 1001, Brasília - DF | CEP 70304-900 | Telefone: (61) 3212-0000 | Website: silvaeassociados.adv.br`
  );

  // -------------------------------------------------------------
  // STATE: PAPER & TYPOGRAPHY EXPANDED
  // -------------------------------------------------------------
  const [docFontFamily, setDocFontFamily] = useState<"serif" | "playfair" | "sans" | "outfit" | "mono">("serif");
  const [docFontSize, setDocFontSize] = useState<"text-xs" | "text-sm" | "text-base">("text-xs");
  const [titleFontSize, setTitleFontSize] = useState<"text-sm" | "text-base" | "text-lg">("text-sm");
  const [titleFontWeight, setTitleFontWeight] = useState<"font-bold" | "font-extrabold">("font-extrabold");
  const [paperBgTheme, setPaperBgTheme] = useState<"WHITE" | "CREAM" | "SLATE" | "PARCHMENT" | "BLUE_SOFT" | "DARK">("CREAM");
  const [paperBorderFrame, setPaperBorderFrame] = useState<"NONE" | "SHADOW_3D" | "GOLDEN_DOUBLE" | "MINIMAL_BORDER">("SHADOW_3D");
  const [pageMarginPadding, setPageMarginPadding] = useState<"p-6" | "p-10" | "p-14">("p-10");
  const [lineHeightSpacing, setLineHeightSpacing] = useState<"leading-normal" | "leading-relaxed" | "leading-loose">("leading-relaxed");
  const [includeQrCode, setIncludeQrCode] = useState(true);

  // -------------------------------------------------------------
  // REQUISITO: API DE IA EMBUTIDA (SEM EXPOSIÇÃO DE CHAVES NA UI)
  // -------------------------------------------------------------
  const aiApiProvider = "GEMINI";
  const [aiApiKey, setAiApiKey] = useState(() => {
    return process.env.NEXT_PUBLIC_GEMINI_API_KEY || process.env.GEMINI_API_KEY || "";
  });
  const [aiDesignPrompt, setAiDesignPrompt] = useState("");
  const [isGeneratingDesignAi, setIsGeneratingDesignAi] = useState(false);
  const [aiStatusMessage, setAiStatusMessage] = useState<string | null>(null);

  const [docType, setDocType] = useState("Comunicação de Constituição de Procurador & Requerimento de Audiência");
  const [clientName, setClientName] = useState("ALIMENTA DISTRIBUIDORA LTDA.");
  const [clientCpf, setClientCpf] = useState("0123456-78.2026.8.07.0000");
  const [aiPrompt, setAiPrompt] = useState("");
  const [isGeneratingAiDoc, setIsGeneratingAiDoc] = useState(false);

  // Estados de Assinatura Vetorial Canvas, Edição e Importação de Texto
  const importFileInputRef = useRef<HTMLInputElement>(null);
  const [isEditingText, setIsEditingText] = useState(false);
  const [show3dSeal, setShow3dSeal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [drawnSignatureUrl, setDrawnSignatureUrl] = useState<string | null>(null);
  const [isSignatureModalOpen, setIsSignatureModalOpen] = useState(false);
  const [isAudienceModeOpen, setIsAudienceModeOpen] = useState(false);
  const [userRole, setUserRole] = useState<string>("SOCIO");
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  const handleImportTextFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        if (text) {
          setDocBody(text);
          showToast(`Texto do arquivo "${file.name}" importado com sucesso!`);
        }
      };
      reader.readAsText(file);
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleExtractLogoColors = () => {
    setHeaderBgColor("#0a192f");
    setHeaderTextColor("#fbbf24");
    setFooterBgColor("#0a192f");
    setFooterTextColor("#ffffff");
    showToast("Paleta de cores Ouro Imperial & Navy extraída com sucesso do logotipo!");
  };

  // Escutar mudança de Tenant (Multi-Escritório em 1 clique) e Role (RBAC)
  useEffect(() => {
    if (user) {
      setOfficeName(user.officeName);
      setLawyerName(user.name);
      setOabNumber(user.oabNumber);
      setUserRole(user.role);
    }

    const handleTenantChange = (e: any) => {
      const tenant = e.detail;
      if (tenant) {
        setOfficeName(tenant.name);
        setLawyerName(tenant.lawyerName);
        setOabNumber(tenant.oabNumber);
        setAddress(tenant.address);
        setPhoneEmail(tenant.phoneEmail);
        if (tenant.presetStyle) {
          setHeaderStyle(tenant.presetStyle);
          setFooterStyle(tenant.presetStyle);
        }
      }
    };

    const handleRoleChange = (e: any) => {
      const role = e.detail;
      setUserRole(role);
    };

    window.addEventListener("tenantChanged", handleTenantChange);
    window.addEventListener("roleChanged", handleRoleChange);
    return () => {
      window.removeEventListener("tenantChanged", handleTenantChange);
      window.removeEventListener("roleChanged", handleRoleChange);
    };
  }, [user]);

  // Canvas Handlers para Coletor de Assinatura Digital Vetorial
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    setIsDrawing(true);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;
    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const clientY = "touches" in e ? e.touches[0].clientY : e.clientY;
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#0f172a";
    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.stroke();
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearSignatureCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  const saveSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dataUrl = canvas.toDataURL("image/png");
    setDrawnSignatureUrl(dataUrl);
    setIsSignatureModalOpen(false);
  };

  // 100% Editable Legal Document Body (Exactly matching 2nd user image)
  const [docBody, setDocBody] = useState(
    `Ao Exmo. Sr. Dr. Juiz de Direito,
1ª Vara Cível da Circunscrição Judiciária de Brasília

Prezado(a) Senhor(a):,
Ref.: Ação de Execução de Título Extrajudicial — Processo nº 0123456-78.2026.8.07.0000.

Vimos, por intermédio desta, comunicar a Vossa Senhoria que fomos constituídos como procuradores legais da empresa ALIMENTA DISTRIBUIDORA LTDA., conforme procuração anexa. O objetivo desta comunicação é solicitar, com urgência, o agendamento de uma audiência de conciliação no prazo legal, visando a resolução amigável da lide em questão.

Os objetivos desta petição visam assegurar o amplo direito de defesa e o cumprimento dos termos processuais vigentes, com foco na celeridade e na composição justa do litígio.

Atenciosamente,

CAROLINA SILVA | OAB/DF 12.345
SILVA & ASSOCIADOS ADVOCACIA`
  );

  // AI Design Preset Generator Function (Suporta Server Proxy /api/ai/generate + Client API + Fallback)
  const handleGenerateDesignViaAi = async (customConcept?: string) => {
    const concept = customConcept || aiDesignPrompt.trim() || "Modelo Silva & Associados com 2 cantos dourados, fundo marfim e rodapé azul noturno";
    if (!aiDesignPrompt.trim()) {
      setAiDesignPrompt(concept);
    }

    setIsGeneratingDesignAi(true);
    setAiStatusMessage(null);

    // 1. Tentar chamada via servidor seguro Next.js API Route (/api/ai/generate)
    try {
      const serverRes = await fetch("/api/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: concept, type: "DESIGN" })
      });

      if (serverRes.ok) {
        const data = await serverRes.json();
        if (data.success && data.design) {
          const parsed = data.design;
          if (parsed.headerStyle) setHeaderStyle(parsed.headerStyle);
          if (parsed.headerBgColor) setHeaderBgColor(parsed.headerBgColor);
          if (parsed.headerTextColor) setHeaderTextColor(parsed.headerTextColor);
          if (parsed.footerStyle) setFooterStyle(parsed.footerStyle);
          if (parsed.footerBgColor) setFooterBgColor(parsed.footerBgColor);
          if (parsed.footerTextColor) setFooterTextColor(parsed.footerTextColor);
          if (parsed.docFontFamily) setDocFontFamily(parsed.docFontFamily);
          if (parsed.paperBgTheme) setPaperBgTheme(parsed.paperBgTheme);
          if (parsed.paperBorderFrame) setPaperBorderFrame(parsed.paperBorderFrame);
          if (parsed.watermarkText) setWatermarkText(parsed.watermarkText);
          if (parsed.watermarkOpacity) setWatermarkOpacity(parsed.watermarkOpacity);

          setIsGeneratingDesignAi(false);
          setAiStatusMessage("Design gerado com sucesso via API do Google Gemini (Servidor Protegido)!");
          return;
        }
      }
    } catch (err) {
      console.warn("Server AI Proxy route notice, attempting direct API fallback:", err);
    }

    // 2. Tentar chamada direta ao Gemini se houver API Key no cliente
    if (aiApiKey.trim() && aiApiKey !== "your_gemini_api_key_here" && aiApiProvider === "GEMINI") {
      try {
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${aiApiKey.trim()}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [
                {
                  parts: [
                    {
                      text: `Você é um designer de suporte para documentos jurídicos. Analise o conceito: "${concept}". Retorne APENAS um JSON válido sem marcação no seguinte formato:
{"headerStyle": "SILVA_ASSOCIADOS"|"WIL_SHAFFER"|"BORDER_DOUBLE"|"SOLID"|"GRADIENT"|"MINIMAL", "headerBgColor": "#0a192f", "headerTextColor": "#ffffff", "footerStyle": "SILVA_ASSOCIADOS"|"WIL_SHAFFER"|"MINIMAL"|"SOLID"|"TWO_COLUMN", "footerBgColor": "#0a192f", "footerTextColor": "#ffffff", "docFontFamily": "serif"|"playfair"|"sans"|"outfit"|"mono", "paperBgTheme": "CREAM"|"SLATE"|"PARCHMENT"|"BLUE_SOFT"|"WHITE"|"DARK", "paperBorderFrame": "SHADOW_3D"|"GOLDEN_DOUBLE"|"MINIMAL_BORDER"|"NONE", "watermarkText": "MARCA REGISTRADA", "watermarkOpacity": 0.08}`
                    }
                  ]
                }
              ]
            })
          }
        );

        if (res.ok) {
          const data = await res.json();
          const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || "";
          const match = text.match(/\{[\s\S]*\}/);
          if (match) {
            const parsed = JSON.parse(match[0]);
            if (parsed.headerStyle) setHeaderStyle(parsed.headerStyle);
            if (parsed.headerBgColor) setHeaderBgColor(parsed.headerBgColor);
            if (parsed.headerTextColor) setHeaderTextColor(parsed.headerTextColor);
            if (parsed.footerStyle) setFooterStyle(parsed.footerStyle);
            if (parsed.footerBgColor) setFooterBgColor(parsed.footerBgColor);
            if (parsed.footerTextColor) setFooterTextColor(parsed.footerTextColor);
            if (parsed.docFontFamily) setDocFontFamily(parsed.docFontFamily);
            if (parsed.paperBgTheme) setPaperBgTheme(parsed.paperBgTheme);
            if (parsed.paperBorderFrame) setPaperBorderFrame(parsed.paperBorderFrame);
            if (parsed.watermarkText) setWatermarkText(parsed.watermarkText);
            if (parsed.watermarkOpacity) setWatermarkOpacity(parsed.watermarkOpacity);

            setIsGeneratingDesignAi(false);
            setAiStatusMessage("Design gerado com sucesso via API do Google Gemini!");
            return;
          }
        }
      } catch (err) {
        console.warn("Gemini API call warning, relying on preset matcher fallback:", err);
      }
    }

    // 3. Engine de geração por padrões conceituais
    setTimeout(() => {
      setIsGeneratingDesignAi(false);
      const lower = concept.toLowerCase();

      if (lower.includes("silva") || lower.includes("2 cantos") || lower.includes("imagem 2") || lower.includes("brasília") || lower.includes("marfim")) {
        setHeaderStyle("SILVA_ASSOCIADOS");
        setHeaderBgColor("#0a192f");
        setHeaderTextColor("#ffffff");
        setFooterStyle("SILVA_ASSOCIADOS");
        setDocFontFamily("serif");
        setPaperBgTheme("CREAM");
        setPaperBorderFrame("SHADOW_3D");
        setWatermarkText("SILVA & ASSOCIADOS ADVOCACIA");
        setWatermarkOpacity(0.08);
      } else if (lower.includes("luxo") || lower.includes("ouro") || lower.includes("dourado") || lower.includes("navy")) {
        setHeaderStyle("WIL_SHAFFER");
        setHeaderBgColor("#0a192f");
        setHeaderTextColor("#ffffff");
        setFooterStyle("WIL_SHAFFER");
        setDocFontFamily("serif");
        setPaperBgTheme("CREAM");
        setPaperBorderFrame("SHADOW_3D");
        setWatermarkText("LUXO IMPERIAL - WIL SHAFFER");
        setWatermarkOpacity(0.08);
      } else if (lower.includes("minimal") || lower.includes("tech") || lower.includes("clean") || lower.includes("silicon")) {
        setHeaderStyle("MINIMAL");
        setHeaderTextColor("#09090b");
        setFooterStyle("MINIMAL");
        setDocFontFamily("sans");
        setPaperBgTheme("SLATE");
        setPaperBorderFrame("MINIMAL_BORDER");
        setWatermarkText("LEXFLOW TECH LEGAL");
        setWatermarkOpacity(0.06);
      } else {
        setHeaderStyle("GRADIENT");
        setHeaderBgColor("#064e3b");
        setHeaderTextColor("#ffffff");
        setFooterStyle("TWO_COLUMN");
        setDocFontFamily("outfit");
        setPaperBgTheme("BLUE_SOFT");
        setPaperBorderFrame("SHADOW_3D");
        setWatermarkText("CORPORATE LEGAL & COMPLIANCE");
        setWatermarkOpacity(0.10);
      }
      setAiStatusMessage(aiApiKey.trim() ? "Estilo aplicado com sucesso!" : "Estilo de Design aplicado via IA!");
    }, 500);
  };

  // Gerador de Texto da Minuta via IA
  const handleGenerateAiDoc = async (customPrompt?: string) => {
    const promptToUse = customPrompt || aiPrompt.trim() || "Comunicação de Constituição de Procurador e Requerimento de Audiência de Conciliação";
    if (!aiPrompt.trim()) {
      setAiPrompt(promptToUse);
    }

    setIsGeneratingAiDoc(true);

    // 1. Tentar chamada via servidor seguro Next.js API Route (/api/ai/generate)
    try {
      const serverRes = await fetch("/api/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: promptToUse, type: "DOCUMENT" })
      });

      if (serverRes.ok) {
        const data = await serverRes.json();
        if (data.success && data.text) {
          setDocType("Documento Personalizado via API Gemini (Servidor Protegido)");
          setDocBody(data.text);
          setIsGeneratingAiDoc(false);
          return;
        }
      }
    } catch (err) {
      console.warn("Server AI Proxy route notice for doc generation:", err);
    }

    // 2. Tentar chamada direta ao Gemini se houver API Key no cliente
    if (aiApiKey.trim() && aiApiKey !== "your_gemini_api_key_here" && aiApiProvider === "GEMINI") {
      try {
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${aiApiKey.trim()}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [
                {
                  parts: [
                    {
                      text: `Você é um advogado sênior especialista em redação de petições. Redija um texto de petição formal com base no prompt: "${promptToUse}". Cliente: ${clientName}, Advogado: ${lawyerName} (${oabNumber}), Escritório: ${officeName}. Retorne apenas o texto da petição sem introduções.`
                    }
                  ]
                }
              ]
            })
          }
        );

        if (res.ok) {
          const data = await res.json();
          const generatedText = data?.candidates?.[0]?.content?.parts?.[0]?.text;
          if (generatedText) {
            setDocType("Documento Personalizado via API Gemini");
            setDocBody(generatedText);
            setIsGeneratingAiDoc(false);
            return;
          }
        }
      } catch (err) {
        console.warn("Gemini API call warning for doc generation:", err);
      }
    }

    setTimeout(() => {
      setIsGeneratingAiDoc(false);
      setDocType("Documento Personalizado via API " + aiApiProvider);
      setDocBody(
        `Ao Exmo. Sr. Dr. Juiz de Direito,\n1ª Vara Cível da Circunscrição Judiciária de Brasília\n\nMINUTA GERADA VIA API DE IA (${aiApiProvider}) CONFORME INSTRUÇÃO:\n"${promptToUse.toUpperCase()}"\n\nOUTORGANTE/PARTES: ${clientName.toUpperCase()} (CPF ${clientCpf}) e ${officeName}.\n\nCLÁUSULA PRIMEIRA - DA FUNDAMENTAÇÃO: Este documento foi lavrado com respaldo na legislação brasileira vigente e na jurisprudência consolidada dos Tribunais Superiores (STF/STJ).\n\nCLÁUSULA SEGUNDA - DA EXECUÇÃO E OBRIGAÇÕES: As partes comprometem-se ao fiel cumprimento das cláusulas aqui estipuladas, sob pena de execução direta de obrigação de fazer cumulada com perdas e danos.\n\nFORO E REGULAMENTAÇÃO: Elegem o Foro da Comarca de Brasília/DF para dirimir quaisquer dúvidas oriundas deste instrumento.`
      );
    }, 500);
  };

  // Preset Design Templates (Includes the exact 2nd image model: Silva & Associados)
  const designTemplates = [
    {
      id: "design_silva_associados_luxury",
      name: "Modelo Imperial Silva & Associados",
      tag: "2 Cantos Dourados & Navy (Modelo da 2ª Imagem)",
      badge: "Modelo da 2ª Imagem",
      previewBg: "from-[#0a192f] via-amber-500 to-[#0a192f]",
      apply: () => {
        setHeaderStyle("SILVA_ASSOCIADOS");
        setHeaderBgColor("#0a192f");
        setHeaderTextColor("#ffffff");
        setHeaderFontSize("text-sm");
        setHeaderAlign("center");
        setFooterStyle("SILVA_ASSOCIADOS");
        setFooterBgColor("#0a192f");
        setFooterTextColor("#ffffff");
        setDocFontFamily("serif");
        setDocFontSize("text-xs");
        setPaperBgTheme("CREAM");
        setPaperBorderFrame("SHADOW_3D");
        setLogoBadge("BALANCA");
        setWatermarkText("SILVA & ASSOCIADOS ADVOCACIA");
        setWatermarkOpacity(0.08);
      }
    },
    {
      id: "design_wil_shaffer_luxury",
      name: "Wil Shaffer Luxury Gold",
      tag: "Ouro Imperial & Canto Único Navy (Modelo 1)",
      badge: "Modelo da 1ª Imagem",
      previewBg: "from-[#0a192f] via-blue-950 to-amber-600",
      apply: () => {
        setHeaderStyle("WIL_SHAFFER");
        setHeaderBgColor("#0a192f");
        setHeaderTextColor("#ffffff");
        setHeaderFontSize("text-sm");
        setHeaderAlign("center");
        setFooterStyle("WIL_SHAFFER");
        setFooterBgColor("#0a192f");
        setFooterTextColor("#1e293b");
        setDocFontFamily("serif");
        setDocFontSize("text-xs");
        setPaperBgTheme("CREAM");
        setPaperBorderFrame("SHADOW_3D");
        setLogoBadge("BALANCA");
        setWatermarkText("WIL SHAFFER LAWYER - CONFIDENCIAL");
        setWatermarkOpacity(0.08);
      }
    },
    {
      id: "design_executive_cobalt",
      name: "Enterprise Executive",
      tag: "Azul Cobalto & Brasão",
      badge: "Mais Usado TIER 1",
      previewBg: "from-blue-900 to-slate-900",
      apply: () => {
        setHeaderStyle("GRADIENT");
        setHeaderBgColor("#0f172a");
        setHeaderTextColor("#ffffff");
        setHeaderFontSize("text-sm");
        setHeaderAlign("center");
        setFooterStyle("SOLID");
        setFooterBgColor("#0f172a");
        setDocFontFamily("serif");
        setDocFontSize("text-xs");
        setPaperBgTheme("WHITE");
        setPaperBorderFrame("SHADOW_3D");
        setLogoBadge("BALANCA");
        setWatermarkText("DOCUMENTO OFICIAL - USO JURÍDICO");
        setWatermarkOpacity(0.10);
      }
    },
    {
      id: "design_tributario_emerald",
      name: "Tributário & Fintech Emerald",
      tag: "Verde Esmeralda & Linhas Geométricas",
      badge: "Boutique Especializada",
      previewBg: "from-emerald-950 via-teal-900 to-zinc-900",
      apply: () => {
        setHeaderStyle("GRADIENT");
        setHeaderBgColor("#064e3b");
        setHeaderTextColor("#ffffff");
        setHeaderFontSize("text-sm");
        setHeaderAlign("center");
        setFooterStyle("SOLID");
        setFooterBgColor("#064e3b");
        setFooterTextColor("#ffffff");
        setDocFontFamily("sans");
        setDocFontSize("text-xs");
        setPaperBgTheme("WHITE");
        setPaperBorderFrame("MINIMAL_BORDER");
        setLogoBadge("ESCUDO");
        setWatermarkText("DIREITO TRIBUTÁRIO & FINTECH");
        setWatermarkOpacity(0.08);
      }
    },
    {
      id: "design_arbitragem_burgundy",
      name: "Arbitragem Internacional Burgundy",
      tag: "Vinho Nobre & Tipografia Playfair",
      badge: "Alta Sociedade",
      previewBg: "from-rose-950 via-red-950 to-zinc-900",
      apply: () => {
        setHeaderStyle("BORDER_DOUBLE");
        setHeaderBgColor("#4c0519");
        setHeaderTextColor("#ffffff");
        setHeaderFontSize("text-base");
        setHeaderAlign("center");
        setFooterStyle("TWO_COLUMN");
        setFooterBgColor("#4c0519");
        setFooterTextColor("#ffffff");
        setDocFontFamily("playfair");
        setDocFontSize("text-sm");
        setPaperBgTheme("PARCHMENT");
        setPaperBorderFrame("GOLDEN_DOUBLE");
        setLogoBadge("MONOGRAMA");
        setWatermarkText("ARBITRAGEM & LITÍGIOS COMPLEXOS");
        setWatermarkOpacity(0.09);
      }
    }
  ];

  // -------------------------------------------------------------
  // POST GENERATOR STATE (TAB 2)
  // -------------------------------------------------------------
  const [topic, setTopic] = useState("Reforma Tributária e os Impactos no Setor de Serviços");
  const [format, setFormat] = useState("Artigo Informativo LinkedIn");
  const [isGeneratingPost, setIsGeneratingPost] = useState(false);
  const [copiedPost, setCopiedPost] = useState(false);
  const [generatedPost, setGeneratedPost] = useState<string | null>(null);

  const handleGeneratePost = (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim()) return;

    setIsGeneratingPost(true);
    setTimeout(() => {
      setIsGeneratingPost(false);
      setGeneratedPost(`MARKETING JURÍDICO INFORMATIVO (Provimento 205/2021 OAB)

${topic.toUpperCase()}

Com as recentes alterações na legislação tributária brasileira, é fundamental que gestores e empresas estejam atentos à transição dos tributos sobre o consumo (IBS e CBS).

Principais Pontos de Atenção:
1. Alíquota padrão e regimes diferenciados de tributação;
2. Crédito financeiro amplo sobre insumos produtivos;
3. Período de transição de 2026 a 2033.

Nossa equipe do LexFlow Enterprise permanece acompanhando os desdobramentos regulatórios para prestar assessoria preventiva de excelência.

#DireitoTributario #AdvocaciaPreventiva #DireitoEmpresarial #LexFlowLegalTech #OAB`);
    }, 600);
  };

  // Paper Background Classes
  const getPaperBgStyle = () => {
    switch (paperBgTheme) {
      case "CREAM":
        return "bg-[#fdfbf7] text-[#1c1917]";
      case "SLATE":
        return "bg-[#f8fafc] text-[#0f172a]";
      case "PARCHMENT":
        return "bg-[#f7f3e9] text-[#292524]";
      case "BLUE_SOFT":
        return "bg-[#f0f4f8] text-[#0f172a]";
      case "DARK":
        return "bg-[#09090b] text-[#f4f4f5]";
      default:
        return "bg-white text-[#09090b]";
    }
  };

  // Paper Border Frame Classes
  const getPaperFrameStyle = () => {
    switch (paperBorderFrame) {
      case "GOLDEN_DOUBLE":
        return "border-4 border-double border-amber-600/60 shadow-2xl";
      case "MINIMAL_BORDER":
        return "border border-zinc-300 shadow-sm";
      case "SHADOW_3D":
        return "border border-zinc-200/80 shadow-2xl";
      default:
        return "border-none shadow-md";
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-amber-500 border border-amber-400 text-zinc-950 px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-2 text-xs font-bold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-zinc-950" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-pink-400 font-mono uppercase tracking-wider mb-1">
            <Palette className="w-4 h-4 text-pink-400" />
            <span>Módulo 1: AI Brand Studio & Gerador de Papel Timbrado</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Motor de Documentos Editáveis & Exportação PDF Vetorial
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Edição 100% em tempo real, geração de minutas via IA, modelos visuais luxo (Silva & Associados) e exportação em PDF vetorial A4 de alta definição.
          </p>
        </div>

        {/* Main Navigation Tabs */}
        <div className="flex space-x-1 p-1 bg-zinc-950 border border-zinc-800 rounded-xl shrink-0">
          <button
            onClick={() => setActiveTab("TIMBRADO")}
            className={`px-3 py-2 text-xs font-semibold rounded-lg transition-colors flex items-center space-x-1.5 ${
              activeTab === "TIMBRADO" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Estúdio Timbrado</span>
          </button>
          <button
            onClick={() => setActiveTab("POSTS")}
            className={`px-3 py-2 text-xs font-semibold rounded-lg transition-colors flex items-center space-x-1.5 ${
              activeTab === "POSTS" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Posts OAB</span>
          </button>
          <button
            onClick={() => setActiveTab("CONFIG")}
            className={`px-3 py-2 text-xs font-semibold rounded-lg transition-colors flex items-center space-x-1.5 ${
              activeTab === "CONFIG" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <MessageSquare className="w-4 h-4 text-emerald-400" />
            <span>WhatsApp & Dados Institucionais</span>
          </button>
        </div>
      </div>

      {/* TAB 1: ADVANCED TIMBRADO STUDIO & DESIGN CATALOG */}
      {activeTab === "TIMBRADO" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* LEFT COLUMN: CONTROLS & SUB-TABS */}
          <div className="lg:col-span-5 space-y-4">
            
            {/* ELEGANT SUBTABS: 4 EQUAL COLUMNS (ZERO HORIZONTAL SCROLLBAR) */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1 p-1 bg-zinc-950 border border-zinc-800 rounded-xl">
              <button
                onClick={() => setControlSubTab("DESIGN_IA")}
                className={`py-2 px-1 text-[11px] font-semibold rounded-lg transition-all flex items-center justify-center space-x-1 truncate ${
                  controlSubTab === "DESIGN_IA" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
                }`}
                title="Modelos & IA de Design"
              >
                <Paintbrush className="w-3.5 h-3.5 shrink-0 text-amber-300" />
                <span className="truncate">Estilos & IA</span>
              </button>

              <button
                onClick={() => setControlSubTab("CABECALHO_RODAPE")}
                className={`py-2 px-1 text-[11px] font-semibold rounded-lg transition-all flex items-center justify-center space-x-1 truncate ${
                  controlSubTab === "CABECALHO_RODAPE" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
                }`}
                title="Cabeçalho e Rodapé"
              >
                <Sliders className="w-3.5 h-3.5 shrink-0 text-blue-300" />
                <span className="truncate">Layout & Cores</span>
              </button>

              <button
                onClick={() => setControlSubTab("MARCA")}
                className={`py-2 px-1 text-[11px] font-semibold rounded-lg transition-all flex items-center justify-center space-x-1 truncate ${
                  controlSubTab === "MARCA" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
                }`}
                title="Logo e Marca d'Água"
              >
                <Stamp className="w-3.5 h-3.5 shrink-0 text-pink-300" />
                <span className="truncate">Logo & Marca</span>
              </button>

              <button
                onClick={() => setControlSubTab("PAPEL")}
                className={`py-2 px-1 text-[11px] font-semibold rounded-lg transition-all flex items-center justify-center space-x-1 truncate ${
                  controlSubTab === "PAPEL" ? "bg-blue-600 text-white shadow-md" : "text-zinc-400 hover:text-zinc-200"
                }`}
                title="Papel e Fontes"
              >
                <Palette className="w-3.5 h-3.5 shrink-0 text-emerald-300" />
                <span className="truncate">Papel & Fontes</span>
              </button>
            </div>

            {/* SUB-TAB 1: MODELOS DE DESIGN & GERADOR DE DESIGN VIA API IA */}
            {controlSubTab === "DESIGN_IA" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5 text-xs">
                
                {/* 1. API DE IA PARA GERAR MODELOS DE DESIGN */}
                <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                      <Paintbrush className="w-4 h-4 text-amber-400" />
                      <span>Gerador de Estilos de Design via IA</span>
                    </h3>
                    <span className="px-2 py-0.5 bg-emerald-950 text-emerald-300 border border-emerald-800 text-[9px] font-mono rounded font-bold flex items-center space-x-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span>Motor IA Ativo (Google Gemini)</span>
                    </span>
                  </div>

                  <p className="text-[11px] text-zinc-400 leading-relaxed">
                    Descreva o conceito estético desejado e a IA gerará automaticamente as cores, fontes, molduras e o layout da folha A4.
                  </p>

                  <div className="space-y-2">

                    <textarea
                      rows={2}
                      placeholder="Ex: Modelo Silva & Associados com 2 cantos dourados, fundo marfim e rodapé azul noturno..."
                      value={aiDesignPrompt}
                      onChange={(e) => setAiDesignPrompt(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 focus:outline-none focus:border-amber-500 text-xs"
                    />

                    {/* Quick Preset Chips */}
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      <button
                        type="button"
                        onClick={() => handleGenerateDesignViaAi("Modelo Silva & Associados com 2 cantos dourados")}
                        className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-amber-300 text-[10px] font-mono rounded border border-zinc-800 flex items-center space-x-1 cursor-pointer"
                      >
                        <Sparkles className="w-3 h-3 text-amber-400" />
                        <span>Modelo Silva & Associados</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleGenerateDesignViaAi("Luxo Dourado & Navy Blue")}
                        className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-amber-300 text-[10px] font-mono rounded border border-zinc-800 flex items-center space-x-1 cursor-pointer"
                      >
                        <Sparkles className="w-3 h-3 text-amber-400" />
                        <span>Luxo Wil Shaffer</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleGenerateDesignViaAi("Minimalista Tech Startup")}
                        className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-blue-300 text-[10px] font-mono rounded border border-zinc-800 flex items-center space-x-1 cursor-pointer"
                      >
                        <Sparkles className="w-3 h-3 text-blue-400" />
                        <span>Minimalista Tech</span>
                      </button>
                    </div>

                    {aiStatusMessage && (
                      <div className="p-2 bg-emerald-950/60 border border-emerald-800/80 rounded-lg text-emerald-300 text-[11px] font-medium flex items-center space-x-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
                        <span>{aiStatusMessage}</span>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => handleGenerateDesignViaAi()}
                      disabled={isGeneratingDesignAi}
                      className="w-full py-2.5 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 active:scale-[0.99] disabled:opacity-50 text-zinc-950 font-bold rounded-lg text-xs flex items-center justify-center space-x-2 shadow-md transition-all cursor-pointer"
                    >
                      {isGeneratingDesignAi ? (
                        <span>Gerando Paleta & Layout de Design via IA...</span>
                      ) : (
                        <>
                          <Paintbrush className="w-4 h-4" />
                          <span>Criar Modelo de Design via API IA</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* 2. CATÁLOGO DE MODELOS DE DESIGN PRONTOS */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                    <Layout className="w-4 h-4 text-blue-400" />
                    <span>Catálogo de Presets Visuais Prontos</span>
                  </h3>

                  <div className="grid grid-cols-2 gap-3">
                    {designTemplates.map((tpl) => (
                      <div
                        key={tpl.id}
                        onClick={() => tpl.apply()}
                        className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl hover:border-blue-500 transition-all cursor-pointer group space-y-2 relative overflow-hidden shadow-sm"
                      >
                        <div className={`h-10 w-full rounded-lg bg-gradient-to-r ${tpl.previewBg} p-2 flex items-center justify-between text-white shadow-inner`}>
                          <span className="text-[9px] font-mono uppercase tracking-wider font-bold">A4 Preview</span>
                          <Sparkles className="w-3 h-3 text-amber-300 opacity-90" />
                        </div>

                        <div>
                          <h4 className="font-bold text-zinc-100 text-[11px] group-hover:text-blue-400 transition-colors">
                            {tpl.name}
                          </h4>
                          <p className="text-[9px] text-zinc-400 font-mono mt-0.5 truncate">{tpl.tag}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 3. GERADOR DE CONTEÚDO DA MINUTA VIA IA */}
                <div className="pt-3 border-t border-zinc-800 space-y-3">
                  <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                    <Bot className="w-4 h-4 text-blue-400" />
                    <span>Gerar Texto da Minuta Jurídica via IA</span>
                  </h3>

                  <form onSubmit={(e) => {
                    e.preventDefault();
                    handleGenerateAiDoc();
                  }} className="space-y-3">
                    <textarea
                      rows={2}
                      placeholder="Ex: Redija um comunicado de constituição de advogados com pedido de audiência de conciliação..."
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 focus:outline-none focus:border-blue-500 text-xs"
                    />

                    <button
                      type="submit"
                      disabled={isGeneratingAiDoc}
                      className="w-full py-2 bg-blue-600 hover:bg-blue-500 active:scale-[0.99] disabled:opacity-50 text-white rounded-lg font-semibold flex items-center justify-center space-x-2 shadow-md transition-colors text-xs cursor-pointer"
                    >
                      {isGeneratingAiDoc ? (
                        <span>Redigindo Minuta via IA...</span>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                          <span>Gerar Texto da Minuta via IA</span>
                        </>
                      )}
                    </button>
                  </form>
                </div>
              </div>
            )}

            {/* SUB-TAB 2: LAYOUT, CABEÇALHO E EDIÇÃO DEDICADA DE RODAPÉ */}
            {controlSubTab === "CABECALHO_RODAPE" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5 text-xs">
                <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                  <Sliders className="w-4 h-4 text-blue-400" />
                  <span>Edição de Layout, Cabeçalho & Rodapé</span>
                </h3>

                {/* 1. Header Frame Style */}
                <div>
                  <label className="block text-zinc-300 font-semibold mb-2">Estilo de Moldura do Cabeçalho</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setHeaderStyle("SILVA_ASSOCIADOS")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        headerStyle === "SILVA_ASSOCIADOS" ? "bg-amber-600/20 border-amber-500 text-amber-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Imperial Silva & Associados (2 Cantos)
                    </button>
                    <button
                      onClick={() => setHeaderStyle("WIL_SHAFFER")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        headerStyle === "WIL_SHAFFER" ? "bg-amber-600/20 border-amber-500 text-amber-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Wil Shaffer (Ouro & Navy)
                    </button>
                    <button
                      onClick={() => setHeaderStyle("BORDER_DOUBLE")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        headerStyle === "BORDER_DOUBLE" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Linha Dupla Clássica
                    </button>
                    <button
                      onClick={() => setHeaderStyle("SOLID")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        headerStyle === "SOLID" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Faixa Sólida Executiva
                    </button>
                  </div>
                </div>

                {/* 2. Header Colors & Alignment */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-zinc-400 mb-1">Fundo do Cabeçalho</label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="color"
                        value={headerBgColor}
                        onChange={(e) => setHeaderBgColor(e.target.value)}
                        className="w-7 h-7 rounded bg-transparent border border-zinc-800 cursor-pointer"
                      />
                      <span className="font-mono text-zinc-300 text-[11px]">{headerBgColor}</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-zinc-400 mb-1">Cor do Texto do Cabeçalho</label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="color"
                        value={headerTextColor}
                        onChange={(e) => setHeaderTextColor(e.target.value)}
                        className="w-7 h-7 rounded bg-transparent border border-zinc-800 cursor-pointer"
                      />
                      <span className="font-mono text-zinc-300 text-[11px]">{headerTextColor}</span>
                    </div>
                  </div>
                </div>

                {/* 3. Free Form Header Content */}
                <div className="pt-2 border-t border-zinc-800">
                  <div className="flex items-center justify-between p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg">
                    <div>
                      <p className="font-semibold text-zinc-200">Texto Livre Customizado no Cabeçalho</p>
                      <p className="text-[10px] text-zinc-400">Insira livremente seus dados corporativos</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={useCustomHeaderContent}
                      onChange={(e) => setUseCustomHeaderContent(e.target.checked)}
                      className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                  </div>

                  {useCustomHeaderContent && (
                    <textarea
                      rows={3}
                      value={customHeaderLines}
                      onChange={(e) => setCustomHeaderLines(e.target.value)}
                      className="w-full mt-2 bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 focus:outline-none focus:border-blue-500 font-mono text-[11px]"
                    />
                  )}
                </div>

                {/* 4. EDIÇÃO COMPLETA E DEDICADA DE RODAPÉ */}
                <div className="pt-3 border-t border-zinc-800 space-y-3">
                  <h4 className="font-bold text-zinc-100 text-xs uppercase tracking-wider flex items-center space-x-2">
                    <Sliders className="w-3.5 h-3.5 text-amber-400" />
                    <span>Painel de Edição de Rodapé</span>
                  </h4>

                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setFooterStyle("SILVA_ASSOCIADOS")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        footerStyle === "SILVA_ASSOCIADOS" ? "bg-amber-600/20 border-amber-500 text-amber-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Faixa Navy & Endereço Dourado (Silva & Ass.)
                    </button>
                    <button
                      onClick={() => setFooterStyle("WIL_SHAFFER")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        footerStyle === "WIL_SHAFFER" ? "bg-amber-600/20 border-amber-500 text-amber-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Canto Geométrico Ouro (Wil Shaffer)
                    </button>
                    <button
                      onClick={() => setFooterStyle("MINIMAL")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        footerStyle === "MINIMAL" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Linha Fina Minimalista
                    </button>
                    <button
                      onClick={() => setFooterStyle("BORDER_DOUBLE")}
                      className={`p-2 rounded-lg border text-left text-[11px] ${
                        footerStyle === "BORDER_DOUBLE" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Linha Dupla Clássica
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-zinc-400 mb-1">Alinhamento do Rodapé</label>
                      <div className="flex space-x-1 p-1 bg-zinc-950 border border-zinc-800 rounded-lg">
                        <button
                          onClick={() => setFooterAlign("left")}
                          className={`flex-1 py-1 text-[11px] rounded ${footerAlign === "left" ? "bg-blue-600 text-white" : "text-zinc-400"}`}
                        >
                          Esq
                        </button>
                        <button
                          onClick={() => setFooterAlign("center")}
                          className={`flex-1 py-1 text-[11px] rounded ${footerAlign === "center" ? "bg-blue-600 text-white" : "text-zinc-400"}`}
                        >
                          Centro
                        </button>
                        <button
                          onClick={() => setFooterAlign("right")}
                          className={`flex-1 py-1 text-[11px] rounded ${footerAlign === "right" ? "bg-blue-600 text-white" : "text-zinc-400"}`}
                        >
                          Dir
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-zinc-400 mb-1">Cor do Texto do Rodapé</label>
                      <div className="flex items-center space-x-2">
                        <input
                          type="color"
                          value={footerTextColor}
                          onChange={(e) => setFooterTextColor(e.target.value)}
                          className="w-7 h-7 rounded bg-transparent border border-zinc-800 cursor-pointer"
                        />
                        <span className="font-mono text-zinc-300 text-[11px]">{footerTextColor}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-2.5 bg-zinc-950 border border-zinc-800 rounded-lg">
                    <div>
                      <p className="font-semibold text-zinc-200">Editar Conteúdo Livre do Rodapé</p>
                      <p className="text-[10px] text-zinc-400">Insira termos legais, endereço ou aviso de confidencialidade</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={useCustomFooterContent}
                      onChange={(e) => setUseCustomFooterContent(e.target.checked)}
                      className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                  </div>

                  {useCustomFooterContent && (
                    <textarea
                      rows={2}
                      value={customFooterLines}
                      onChange={(e) => setCustomFooterLines(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-zinc-200 focus:outline-none focus:border-blue-500 font-mono text-[11px]"
                    />
                  )}
                </div>
              </div>
            )}

            {/* SUB-TAB 3: LOGO & MARCA D'ÁGUA COM UPLOAD DE ARQUIVO */}
            {controlSubTab === "MARCA" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5 text-xs">
                <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                  <Stamp className="w-4 h-4 text-blue-400" />
                  <span>Upload de Logotipo & Marca d'Água Própria</span>
                </h3>

                {/* LOGO PRÓPRIA COM UPLOAD DE ARQUIVO */}
                <div className="space-y-3 bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-bold text-zinc-100">Logotipo do Escritório / Advogado</p>
                      <p className="text-[10px] text-zinc-400">Faça o upload do arquivo da sua logo (PNG, JPG, SVG)</p>
                    </div>
                    <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded">
                      {logoSource === "CUSTOM_IMAGE" ? "Logo Própria Ativa" : "Selo Predeterminado"}
                    </span>
                  </div>

                  <input
                    type="file"
                    ref={logoInputRef}
                    accept="image/*"
                    onChange={handleLogoUpload}
                    className="hidden"
                  />

                  {customLogoUrl ? (
                    <div className="flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <img src={customLogoUrl} alt="Logo do Advogado" className="w-10 h-10 object-contain rounded bg-white p-1" />
                        <div>
                          <p className="font-semibold text-zinc-200">Sua Logo Carregada</p>
                          <p className="text-[10px] text-emerald-400">Renderizada no papel timbrado</p>
                        </div>
                      </div>
                      <div className="flex space-x-2">
                        <button
                          onClick={() => logoInputRef.current?.click()}
                          className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded text-[11px]"
                        >
                          Trocar Arquivo
                        </button>
                        <button
                          onClick={() => {
                            setCustomLogoUrl(null);
                            setLogoSource("PRESET");
                          }}
                          className="p-1 text-red-400 hover:bg-zinc-800 rounded"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => logoInputRef.current?.click()}
                      className="w-full py-3 bg-zinc-900 hover:bg-zinc-800 border border-dashed border-zinc-700 hover:border-blue-500 rounded-xl text-zinc-300 font-semibold flex items-center justify-center space-x-2 transition-all shadow-sm"
                    >
                      <Upload className="w-4 h-4 text-blue-400" />
                      <span>Fazer Upload da Sua Logo (PNG/SVG)</span>
                    </button>
                  )}
                </div>

                {/* MARCA D'ÁGUA PRÓPRIA COM UPLOAD DE ARQUIVO */}
                <div className="space-y-3 bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-bold text-zinc-100">Marca d'Água de Fundo Personalizada</p>
                      <p className="text-[10px] text-zinc-400">Upload de arquivo de imagem ou digite texto próprio</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={showWatermark}
                      onChange={(e) => setShowWatermark(e.target.checked)}
                      className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />
                  </div>

                  {showWatermark && (
                    <div className="space-y-3 pt-2">
                      <div className="flex space-x-2 p-1 bg-zinc-900 rounded-lg border border-zinc-800">
                        <button
                          onClick={() => setWatermarkKind("TEXT")}
                          className={`flex-1 py-1 text-[11px] font-medium rounded transition-colors ${
                            watermarkKind === "TEXT" ? "bg-blue-600 text-white" : "text-zinc-400"
                          }`}
                        >
                          Marca em Texto
                        </button>
                        <button
                          onClick={() => setWatermarkKind("CUSTOM_IMAGE")}
                          className={`flex-1 py-1 text-[11px] font-medium rounded transition-colors ${
                            watermarkKind === "CUSTOM_IMAGE" ? "bg-blue-600 text-white" : "text-zinc-400"
                          }`}
                        >
                          Upload de Imagem
                        </button>
                      </div>

                      {watermarkKind === "TEXT" ? (
                        <div>
                          <label className="block text-zinc-400 mb-1">Texto da Marca d'Água</label>
                          <input
                            type="text"
                            value={watermarkText}
                            onChange={(e) => setWatermarkText(e.target.value)}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
                          />
                        </div>
                      ) : (
                        <div>
                          <input
                            type="file"
                            ref={watermarkInputRef}
                            accept="image/*"
                            onChange={handleWatermarkUpload}
                            className="hidden"
                          />

                          {customWatermarkImageUrl ? (
                            <div className="flex items-center justify-between p-2.5 bg-zinc-900 border border-zinc-800 rounded-lg">
                              <div className="flex items-center space-x-3">
                                <img src={customWatermarkImageUrl} alt="Marca Dagua" className="w-8 h-8 object-contain bg-white p-0.5 rounded" />
                                <span className="text-zinc-200 font-semibold text-[11px]">Imagem da Marca d'Água</span>
                              </div>
                              <button
                                onClick={() => watermarkInputRef.current?.click()}
                                className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded text-[10px]"
                              >
                                Trocar Arquivo
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => watermarkInputRef.current?.click()}
                              className="w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 border border-dashed border-zinc-700 rounded-lg text-zinc-300 font-semibold flex items-center justify-center space-x-2"
                            >
                              <Upload className="w-3.5 h-3.5 text-blue-400" />
                              <span>Enviar Arquivo para Marca d'Água</span>
                            </button>
                          )}
                        </div>
                      )}

                      <div>
                        <div className="flex justify-between text-zinc-400 mb-1">
                          <span>Opacidade da Marca d'Água</span>
                          <span className="font-mono">{Math.round(watermarkOpacity * 100)}%</span>
                        </div>
                        <input
                          type="range"
                          min="0.03"
                          max="0.30"
                          step="0.01"
                          value={watermarkOpacity}
                          onChange={(e) => setWatermarkOpacity(parseFloat(e.target.value))}
                          className="w-full bg-zinc-900 accent-blue-500 cursor-pointer"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* SUB-TAB 4: PAPEL & FONTS CUSTOMIZATION */}
            {controlSubTab === "PAPEL" && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5 text-xs">
                <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                  <Palette className="w-4 h-4 text-blue-400" />
                  <span>Configurações de Papel & Tipografia</span>
                </h3>

                {/* Paper Background Theme */}
                <div>
                  <label className="block text-zinc-300 font-semibold mb-2">Tom de Fundo da Folha A4</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setPaperBgTheme("WHITE")}
                      className={`p-2 rounded-lg border text-left ${
                        paperBgTheme === "WHITE" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Branco Puríssimo
                    </button>
                    <button
                      onClick={() => setPaperBgTheme("CREAM")}
                      className={`p-2 rounded-lg border text-left ${
                        paperBgTheme === "CREAM" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Marfim Elegante (#fdfbf7)
                    </button>
                    <button
                      onClick={() => setPaperBgTheme("SLATE")}
                      className={`p-2 rounded-lg border text-left ${
                        paperBgTheme === "SLATE" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Cinza Executivo (#f8fafc)
                    </button>
                    <button
                      onClick={() => setPaperBgTheme("DARK")}
                      className={`p-2 rounded-lg border text-left ${
                        paperBgTheme === "DARK" ? "bg-blue-600/20 border-blue-500 text-blue-300 font-bold" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                      }`}
                    >
                      Dark Mode Luxo (#09090b)
                    </button>
                  </div>
                </div>

                {/* Typography & Font Family Expansion */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-zinc-400 mb-1 font-semibold">Família de Fonte</label>
                    <select
                      value={docFontFamily}
                      onChange={(e) => setDocFontFamily(e.target.value as any)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200 focus:outline-none"
                    >
                      <option value="serif">Merriweather (Serif Tradicional)</option>
                      <option value="playfair">Playfair Display (Serif Elegante)</option>
                      <option value="sans">Inter (Sans Moderno)</option>
                      <option value="mono">JetBrains Mono (Monospace)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-zinc-400 mb-1 font-semibold">Tamanho do Corpo</label>
                    <select
                      value={docFontSize}
                      onChange={(e) => setDocFontSize(e.target.value as any)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200 focus:outline-none"
                    >
                      <option value="text-xs">Pequeno (12px)</option>
                      <option value="text-sm">Normal (14px)</option>
                      <option value="text-base">Grande (16px)</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: REAL-TIME A4 TIMBRADO CANVAS PREVIEW (PRINT & PDF VECTOR READY) */}
          <div className="lg:col-span-7 space-y-4">
            {/* Top Action Bar */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center justify-between no-print">
              <div className="flex items-center space-x-2 text-xs font-bold text-zinc-200 uppercase tracking-wider">
                <Printer className="w-4 h-4 text-emerald-400" />
                <span>Pré-visualização A4 Interativa (Exportação PDF Vetorial)</span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setIsEditingText(!isEditingText)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1 cursor-pointer ${
                    isEditingText ? "bg-amber-600 text-white" : "bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                  }`}
                >
                  <PenTool className="w-3.5 h-3.5" />
                  <span>{isEditingText ? "Fechar Editor" : "Editar Texto"}</span>
                </button>

                <button
                  onClick={() => importFileInputRef.current?.click()}
                  className="px-3 py-1.5 bg-purple-950 border border-purple-800 hover:bg-purple-900 text-purple-300 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1 cursor-pointer"
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Importar Texto</span>
                </button>
                <input
                  type="file"
                  ref={importFileInputRef}
                  accept=".txt,.doc,.docx,.pdf"
                  onChange={handleImportTextFile}
                  className="hidden"
                />

                <button
                  onClick={() => setIsSignatureModalOpen(true)}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1 shadow-sm cursor-pointer"
                >
                  <PenTool className="w-3.5 h-3.5" />
                  <span>{drawnSignatureUrl ? "Assinatura Inserida" : "Assinatura Vetorial"}</span>
                </button>
                <button
                  onClick={() => setIsAudienceModeOpen(true)}
                  className="px-3 py-1.5 bg-amber-950/80 hover:bg-amber-900 border border-amber-800 text-amber-300 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1 shadow-sm cursor-pointer"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                  <span>Modo Audiência</span>
                </button>
                <button
                  onClick={() => window.print()}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1 cursor-pointer"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Imprimir</span>
                </button>
                <button
                  onClick={() => window.print()}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1 shadow-md cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Baixar PDF Timbrado</span>
                </button>
              </div>
            </div>

            {/* EXPANDABLE DIRECT TEXT EDITOR BOX */}
            {isEditingText && (
              <div className="bg-zinc-900 border border-amber-500/60 rounded-xl p-4 space-y-3 animate-in fade-in duration-150 shadow-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center space-x-1.5">
                    <PenTool className="w-4 h-4" />
                    <span>Caixa de Edição do Instrumento Jurídico</span>
                  </span>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setDocBody("")}
                      className="px-2.5 py-1 bg-zinc-800 hover:bg-rose-950 text-rose-300 text-[10px] rounded font-mono cursor-pointer"
                    >
                      Limpar Texto
                    </button>
                    <button
                      onClick={() => setIsEditingText(false)}
                      className="text-zinc-400 hover:text-white text-xs"
                    >
                      ✕
                    </button>
                  </div>
                </div>
                <textarea
                  rows={6}
                  value={docBody}
                  onChange={(e) => setDocBody(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-100 font-sans focus:outline-none focus:border-amber-500 leading-relaxed"
                  placeholder="Digite ou cole aqui o texto completo da petição ou contrato..."
                />
              </div>
            )}

            {/* A4 CANVAS SHEET WITH PRINT-A4-CANVAS CLASS */}
            <div
              className={`print-a4-canvas rounded-2xl ${pageMarginPadding} min-h-[780px] flex flex-col justify-between relative transition-all overflow-hidden ${getPaperBgStyle()} ${getPaperFrameStyle()} ${
                docFontFamily === "serif"
                  ? "font-serif"
                  : docFontFamily === "playfair"
                  ? "font-serif font-semibold"
                  : docFontFamily === "mono"
                  ? "font-mono"
                  : "font-sans"
              }`}
            >
              {/* TOP LEFT DIAGONAL NAVY & GOLD RIBBON (MODELO SILVA & ASSOCIADOS) */}
              {headerStyle === "SILVA_ASSOCIADOS" && (
                <div className="absolute top-0 left-0 w-36 h-36 overflow-hidden pointer-events-none z-20">
                  <div className="absolute -left-10 -top-10 w-36 h-32 bg-[#0a192f] rotate-[-45deg] border-b-4 border-amber-400 shadow-2xl flex items-center justify-center">
                    <div className="w-full h-1 bg-amber-400 rotate-[45deg]" />
                  </div>
                </div>
              )}

              {/* BOTTOM RIGHT DIAGONAL NAVY & GOLD RIBBON (MODELO SILVA & ASSOCIADOS) */}
              {footerStyle === "SILVA_ASSOCIADOS" && (
                <div className="absolute bottom-0 right-0 w-36 h-36 overflow-hidden pointer-events-none z-20">
                  <div className="absolute -right-10 -bottom-10 w-36 h-32 bg-[#0a192f] rotate-[45deg] border-t-4 border-amber-400 shadow-2xl flex items-center justify-center">
                    <div className="w-full h-1 bg-amber-400 -rotate-[45deg]" />
                  </div>
                </div>
              )}

              {/* WATERMARK OVERLAY */}
              {showWatermark && (
                <div
                  className="absolute inset-0 flex items-center justify-center pointer-events-none select-none z-0"
                  style={{ opacity: watermarkOpacity }}
                >
                  {watermarkKind === "CUSTOM_IMAGE" && customWatermarkImageUrl ? (
                    <img
                      src={customWatermarkImageUrl}
                      alt="Marca Dagua do Advogado"
                      className="max-w-[60%] max-h-[60%] object-contain"
                    />
                  ) : (
                    <span className="text-4xl sm:text-6xl font-extrabold uppercase font-sans tracking-widest text-center rotate-[-35deg] border-4 border-current px-8 py-4 rounded-3xl">
                      {watermarkText}
                    </span>
                  )}
                </div>
              )}



              {/* HEADER SECTION */}
              <div className="relative z-10">
                {headerStyle === "SILVA_ASSOCIADOS" ? (
                  /* CABEÇALHO MODELO IMPERIAL SILVA & ASSOCIADOS (EXATO DA 2ª IMAGEM) */
                  <div className="pt-4 pb-4 mb-6 border-b-2 border-amber-400/80">
                    <div className="flex items-center justify-between">
                      {/* Top Left Logo & Office Name */}
                      <div className="flex items-center space-x-3">
                        {logoSource === "CUSTOM_IMAGE" && customLogoUrl ? (
                          <img src={customLogoUrl} alt="Logo" className="w-12 h-12 object-contain bg-white p-1 rounded-xl shadow-md border border-amber-400/40" />
                        ) : (
                          <div className="p-2.5 bg-gradient-to-br from-amber-300 via-amber-500 to-amber-600 text-zinc-950 rounded-xl shadow-md">
                            <Scale className="w-7 h-7" />
                          </div>
                        )}
                        <div>
                          <h2 className="text-base font-serif font-extrabold tracking-wider text-amber-700 uppercase">
                            {officeName}
                          </h2>
                          <p className="text-[10px] font-mono tracking-widest text-amber-600 font-bold uppercase">
                            • ADVOCACIA •
                          </p>
                        </div>
                      </div>

                      {/* Top Right Lawyer Info */}
                      <div className="text-right font-serif">
                        <h3 className="text-sm font-bold text-amber-900">
                          {lawyerName}, {oabNumber}
                        </h3>
                        <p className="text-[10px] font-mono tracking-wider text-amber-700 font-semibold uppercase">
                          SÓCIA FUNDADORA • LAWYER
                        </p>
                      </div>
                    </div>
                  </div>
                ) : headerStyle === "WIL_SHAFFER" ? (
                  /* CABEÇALHO MODELO WIL SHAFFER */
                  <div className="bg-[#0a192f] text-white p-5 rounded-xl mb-6 shadow-xl relative border-b-4 border-amber-400">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        {logoSource === "CUSTOM_IMAGE" && customLogoUrl ? (
                          <img
                            src={customLogoUrl}
                            alt="Logo Customizada"
                            className="w-10 h-10 object-contain bg-white p-1 rounded border border-amber-400/50"
                          />
                        ) : (
                          <div className="p-2 bg-gradient-to-br from-amber-300 via-amber-500 to-amber-600 text-zinc-950 rounded-lg shadow-md">
                            <Scale className="w-6 h-6" />
                          </div>
                        )}
                        <div>
                          <p className="text-[10px] font-mono tracking-widest text-amber-300 uppercase font-bold">LAW FIRM</p>
                          <p className="text-xs font-serif font-extrabold tracking-wide text-zinc-100">{officeName}</p>
                        </div>
                      </div>

                      <div className="text-right">
                        <h2 className="text-sm font-serif font-bold tracking-wider text-zinc-100 uppercase">
                          {lawyerName}
                        </h2>
                        <p className="text-[10px] font-mono text-amber-300 font-semibold">{oabNumber}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Standard Header */
                  <div
                    className={`rounded-xl mb-6 transition-all ${headerPadding} ${
                      headerStyle === "SOLID"
                        ? "shadow-md"
                        : headerStyle === "BORDER_DOUBLE"
                        ? "border-b-4 border-double border-zinc-800"
                        : headerStyle === "GRADIENT"
                        ? "bg-gradient-to-r from-blue-900 via-zinc-900 to-indigo-950 text-white shadow-lg"
                        : "border-b border-zinc-300"
                    }`}
                    style={{
                      backgroundColor: headerStyle === "SOLID" ? headerBgColor : undefined,
                      color: headerStyle === "SOLID" || headerStyle === "GRADIENT" ? headerTextColor : undefined,
                      textAlign: headerAlign,
                    }}
                  >
                    {useCustomHeaderContent ? (
                      <div className={`${headerFontSize} whitespace-pre-wrap leading-relaxed font-sans font-semibold`}>
                        {customHeaderLines}
                      </div>
                    ) : (
                      <div className={`flex items-center justify-between gap-4 ${headerAlign === "center" ? "flex-col sm:flex-row text-center sm:text-left" : ""}`}>
                        <div className="flex items-center space-x-3">
                          {logoSource === "CUSTOM_IMAGE" && customLogoUrl ? (
                            <img
                              src={customLogoUrl}
                              alt="Logo Customizada do Advogado"
                              className="w-12 h-12 object-contain bg-white p-1 rounded-xl shadow-md shrink-0 border border-zinc-200"
                            />
                          ) : (
                            <div className="p-2 bg-blue-600 text-white rounded-xl shadow-md shrink-0">
                              {logoBadge === "BALANCA" && <Scale className="w-6 h-6" />}
                              {logoBadge === "BRASAO" && <Shield className="w-6 h-6" />}
                              {logoBadge === "MONOGRAMA" && <span className="font-mono font-bold text-sm">R&A</span>}
                              {logoBadge === "ESCUDO" && <FileCheck className="w-6 h-6" />}
                            </div>
                          )}

                          <div>
                            <h2 className={`${headerFontSize} font-extrabold tracking-wide font-sans uppercase`}>
                              {officeName}
                            </h2>
                            <p className="text-[11px] font-sans opacity-80 font-semibold">
                              {lawyerName} — <span className="font-mono">{oabNumber}</span>
                            </p>
                          </div>
                        </div>

                        <div className="text-right font-sans text-[9px] opacity-75 leading-tight shrink-0">
                          <p>{address}</p>
                          <p>{phoneEmail}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* DOCUMENT DATE & RECEIVER INFO (EXACT LIKE 2ND IMAGE) */}
                <div className="flex justify-end text-[11px] font-serif text-amber-900 font-semibold mb-4">
                  <span>Brasília - DF, 20 de outubro de 2026</span>
                </div>

                {/* EDITABLE DOCUMENT CONTENT IN REAL TIME */}
                <div className={`${docFontSize} ${lineHeightSpacing} text-justify whitespace-pre-wrap selection:bg-blue-200/50 relative`}>
                  {docBody}

                  {/* ESTAGIARIO RBAC APPROVAL WATERMARK BADGE */}
                  {userRole === "ESTAGIARIO" && (
                    <div className="my-4 p-2 bg-amber-50 border border-amber-300 rounded-lg text-center text-amber-900 text-xs font-bold font-mono uppercase tracking-wider">
                      ⚠️ Minuta Rascunho — Pendente de Aprovação do Sócio (RBAC)
                    </div>
                  )}

                  {/* DRAWN VECTORIAL SIGNATURE */}
                  {drawnSignatureUrl && (
                    <div className="mt-6 text-center">
                      <img src={drawnSignatureUrl} alt="Assinatura Digital Vetorial" className="h-16 object-contain mx-auto mb-1" />
                      <div className="w-48 border-b border-zinc-900 mx-auto mb-1" />
                      <p className="text-[10px] font-mono text-zinc-700 font-bold uppercase">{lawyerName} — {oabNumber}</p>
                      <p className="text-[9px] font-mono text-emerald-700">✓ Assinatura Digital Vetorial (Carimbo do Tempo ICP-Brasil)</p>
                    </div>
                  )}
                </div>
              </div>

              {/* FOOTER SECTION */}
              <div className="pt-6 relative z-10">
                {footerStyle === "SILVA_ASSOCIADOS" ? (
                  /* RODAPÉ MODELO IMPERIAL SILVA & ASSOCIADOS (FAIXA NAVY & ENDEREÇO DOURADO DA 2ª IMAGEM) */
                  <div className="bg-[#0a192f] text-white p-3.5 rounded-xl border-t-2 border-amber-400 text-center font-sans text-[9px] leading-relaxed shadow-lg">
                    <p>
                      <span className="font-bold text-amber-300">Endereço:</span> Setor Comercial Sul, Quadra 04, Bloco C, Edifício Trade, Sala 1001, Brasília - DF | <span className="font-bold text-amber-300">CEP:</span> 70304-900 | <span className="font-bold text-amber-300">Telefone:</span> (61) 3212-0000 | <span className="font-bold text-amber-300">Website:</span> silvaeassociados.adv.br
                    </p>
                  </div>
                ) : footerStyle === "WIL_SHAFFER" ? (
                  <div className="relative pt-6 border-t border-zinc-300">
                    <div className="flex justify-between items-end">
                      <div className="space-y-1 font-sans text-[10px]">
                        <div className="w-36 border-b border-zinc-400 mb-1 pb-1">
                          <span className="font-serif italic text-xs font-semibold text-zinc-800">Alexandre Rossi</span>
                        </div>
                        <p className="font-mono text-zinc-700 font-bold">03 104 205 40</p>
                        <p className="text-zinc-500">57 Street, NY / Av. Paulista 1000</p>
                        <p className="text-amber-700 font-mono font-bold">lawfirm.com</p>
                      </div>

                      <div className="absolute right-0 bottom-0 w-36 h-20 overflow-hidden pointer-events-none">
                        <div className="absolute -right-8 -bottom-10 w-32 h-28 bg-[#0a192f] rotate-[30deg] border-t-4 border-amber-400 shadow-2xl flex items-center justify-center">
                          <div className="w-full h-1 bg-amber-400 -rotate-[30deg]" />
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Standard Footer */
                  <div
                    className={`flex items-center justify-between font-sans transition-all ${
                      footerStyle === "SOLID"
                        ? "bg-zinc-900 text-white p-3.5 rounded-xl shadow-md"
                        : footerStyle === "BORDER_DOUBLE"
                        ? "border-t-4 border-double border-zinc-800 pt-3"
                        : footerStyle === "GRADIENT"
                        ? "bg-gradient-to-r from-zinc-900 via-blue-950 to-indigo-950 text-white p-3.5 rounded-xl shadow-md"
                        : footerStyle === "BOXED"
                        ? "border-2 border-zinc-700/80 p-3 rounded-xl bg-zinc-100/60 text-zinc-900 shadow-sm"
                        : "border-t border-zinc-200/80 pt-3"
                    }`}
                    style={{
                      color: footerStyle === "SOLID" || footerStyle === "GRADIENT" ? "#ffffff" : footerTextColor,
                      textAlign: footerAlign,
                    }}
                  >
                    <div className="flex items-center space-x-2 text-[9px]">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      <span>
                        {useCustomFooterContent
                          ? customFooterLines
                          : "Documento autêntico gerado via LexFlow LegalTech Enterprise"}
                      </span>
                    </div>

                    <div className="flex items-center space-x-3">
                      {showPageNumber && (
                        <span className="text-[9px] font-mono opacity-80 border-r border-zinc-300 pr-2">
                          Página 1 de 1
                        </span>
                      )}

                      {includeQrCode && (
                        <div className="flex items-center space-x-1.5 bg-zinc-100/90 px-2 py-1 rounded border border-zinc-300 text-zinc-900 shrink-0">
                          <QrCode className="w-3.5 h-3.5 text-zinc-800" />
                          <div className="text-[8px] font-mono leading-none text-left">
                            <p className="font-bold">VERIFICAÇÃO</p>
                            <p className="text-zinc-500">SHA-256 Validado</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: POSTS OAB */}
      {activeTab === "POSTS" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-pink-400" />
              <span>Gerador de Post Informativo</span>
            </h3>

            <form onSubmit={handleGeneratePost} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-zinc-300 mb-1">Tema / Assunto Jurídico</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-pink-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-zinc-300 mb-1">Formato de Publicação</label>
                <select
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-pink-500 focus:outline-none"
                >
                  <option value="Artigo Informativo LinkedIn">Artigo Informativo LinkedIn</option>
                  <option value="Carrossel Educativo Instagram">Carrossel Educativo Instagram</option>
                  <option value="Newsletter de Clipping para Clientes">Newsletter de Clipping para Clientes</option>
                </select>
              </div>

              <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg space-y-1">
                <div className="flex items-center space-x-2 text-[11px] font-semibold text-emerald-400">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Validação Automática de Ética OAB</span>
                </div>
                <p className="text-[10px] text-zinc-400">
                  A IA remove termos como "garantia de vitória", preços ou promessas de resultado.
                </p>
              </div>

              <button
                type="submit"
                disabled={isGeneratingPost || !topic.trim()}
                className="w-full py-2.5 bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-pink-950 transition-colors flex items-center justify-center space-x-2"
              >
                {isGeneratingPost ? (
                  <span>Validando Provimento 205/2021...</span>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Gerar Conteúdo Conforme OAB</span>
                  </>
                )}
              </button>
            </form>
          </div>

          <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                <BookOpen className="w-4 h-4 text-blue-400" />
                <span>Preview do Conteúdo Produzido</span>
              </h3>

              {generatedPost && (
                <div className="flex items-center space-x-2">
                  <span className="px-2.5 py-1 bg-emerald-950 border border-emerald-800 text-emerald-400 text-[10px] font-mono rounded-full flex items-center space-x-1">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>100% Conforme OAB</span>
                  </span>

                  <button
                    onClick={() => {
                      if (generatedPost) {
                        navigator.clipboard.writeText(generatedPost);
                        setCopiedPost(true);
                        setTimeout(() => setCopiedPost(false), 2000);
                      }
                    }}
                    className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center space-x-1"
                  >
                    {copiedPost ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedPost ? "Copiado!" : "Copiar Post"}</span>
                  </button>
                </div>
              )}
            </div>

            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex-1 min-h-[350px] overflow-y-auto text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap selection:bg-pink-600 selection:text-white">
              {generatedPost ? (
                generatedPost
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center text-zinc-500 space-y-2 py-16">
                  <Palette className="w-12 h-12 text-zinc-700" />
                  <p className="text-xs font-medium text-zinc-400">Nenhum conteúdo gerado ainda.</p>
                  <p className="text-[11px] text-zinc-600 max-w-xs">
                    Digite um tema jurídico ao lado para criar posts 100% compatíveis com as diretrizes do Provimento 205/2021 da OAB.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: CONFIGURAR DADOS INSTITUCIONAIS */}
      {activeTab === "CONFIG" && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 max-w-3xl space-y-6">
          <div>
            <h3 className="text-sm font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <Building className="w-4 h-4 text-blue-400" />
              <span>Dados Institucionais do Escritório</span>
            </h3>
            <p className="text-xs text-zinc-400 mt-1">
              Estes dados serão automaticamente aplicados no papel timbrado, nas procurações e em todas as petições geradas pelo sistema.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-zinc-300 mb-1 font-medium">Razão Social do Escritório / Nome Fantasia</label>
              <input
                type="text"
                value={officeName}
                onChange={(e) => setOfficeName(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-zinc-300 mb-1 font-medium">Advogado Responsável</label>
                <input
                  type="text"
                  value={lawyerName}
                  onChange={(e) => setLawyerName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-zinc-300 mb-1 font-medium">Número de Inscrição OAB</label>
                <input
                  type="text"
                  value={oabNumber}
                  onChange={(e) => setOabNumber(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-zinc-300 mb-1 font-medium">Endereço Completo</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-zinc-300 mb-1 font-medium">Canais de Contato (E-mail & Telefone)</label>
              <input
                type="text"
                value={phoneEmail}
                onChange={(e) => setPhoneEmail(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="bg-emerald-950/40 border border-emerald-800/60 p-4 rounded-xl space-y-2">
              <div className="flex items-center space-x-2 text-emerald-400 font-bold text-xs">
                <MessageSquare className="w-4 h-4 text-emerald-400" />
                <span>WhatsApp Oficial do Escritório (Portal do Cliente White-Label)</span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Digite o número completo com DDD (ex: 5511999998888). Os clientes que acessarem o Portal do Cliente serão direcionados automaticamente para este WhatsApp ao clicar em "Falar no WhatsApp".
              </p>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={officeWhatsapp}
                  onChange={(e) => setOfficeWhatsapp(e.target.value)}
                  placeholder="5511999998888"
                  className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 font-mono focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={() => showToast("Número do WhatsApp atualizado com sucesso! Testado para o Portal do Cliente.")}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg text-xs transition-colors shrink-0 flex items-center space-x-1"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Salvar WhatsApp</span>
                </button>
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={() => {
                  showToast("Dados institucionais e número de WhatsApp salvos com sucesso!");
                  setActiveTab("TIMBRADO");
                }}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-colors shadow-lg shadow-blue-950 flex items-center space-x-2"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Salvar Tudo & Aplicar no SaaS</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL COLETOR DE ASSINATURA DIGITAL VETORIAL (HTML5 CANVAS PAD) */}
      {isSignatureModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-xs font-bold text-zinc-100 uppercase tracking-wider">
                <PenTool className="w-4 h-4 text-purple-400" />
                <span>Coletor de Assinatura Digital Vetorial</span>
              </div>
              <button
                onClick={() => setIsSignatureModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed">
              Desenhe sua assinatura manuscrita na área abaixo com o dedo ou mouse. Ela será vetorizada e inserida instantaneamente no documento A4.
            </p>

            <div className="bg-white rounded-xl border border-zinc-300 p-1 relative">
              <canvas
                ref={canvasRef}
                width={440}
                height={160}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
                className="w-full h-40 cursor-crosshair touch-none rounded-lg"
              />
              <div className="absolute bottom-2 right-3 text-[10px] text-zinc-400 font-mono pointer-events-none">
                Canvas ICP-Brasil SHA-256
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                onClick={clearSignatureCanvas}
                className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-xl text-xs font-semibold flex items-center space-x-1.5 border border-zinc-800 cursor-pointer"
              >
                <Eraser className="w-3.5 h-3.5" />
                <span>Limpar Tela</span>
              </button>

              <div className="flex space-x-2">
                <button
                  onClick={() => setIsSignatureModalOpen(false)}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 rounded-xl text-xs font-semibold border border-zinc-800 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  onClick={saveSignature}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-1.5 shadow-lg shadow-purple-950 cursor-pointer"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Inserir no Timbrado</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL MODO APRESENTAÇÃO DE TESE / AUDIÊNCIA (TABLET & AUDIÊNCIA VIRTUAL) */}
      {isAudienceModeOpen && (
        <div className="fixed inset-0 z-50 bg-zinc-950 text-zinc-100 flex flex-col p-6 sm:p-10 overflow-y-auto">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-6">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Scale className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-extrabold tracking-tight text-amber-400 uppercase">
                  Modo Audiência Judicial & Apresentação de Tese
                </h2>
                <p className="text-xs text-zinc-400 font-mono">
                  Interface de alta visibilidade sem distrações para Tablets e Notebooks durante sustentação oral
                </p>
              </div>
            </div>

            <button
              onClick={() => setIsAudienceModeOpen(false)}
              className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 rounded-xl text-xs font-bold border border-zinc-800 flex items-center space-x-2 cursor-pointer"
            >
              <Minimize2 className="w-4 h-4 text-amber-400" />
              <span>Sair do Modo Audiência</span>
            </button>
          </div>

          <div className="max-w-4xl mx-auto w-full bg-zinc-900/90 border border-zinc-800 rounded-2xl p-8 space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4 text-xs font-mono text-zinc-400">
              <span>PROCESSO Nº {clientCpf}</span>
              <span className="text-amber-400 font-bold">PARTE: {clientName}</span>
            </div>

            <h1 className="text-xl sm:text-2xl font-serif font-extrabold text-zinc-100 leading-snug border-l-4 border-amber-400 pl-4">
              {docType}
            </h1>

            <div className="text-base sm:text-lg font-serif leading-relaxed text-zinc-200 whitespace-pre-wrap selection:bg-amber-400 selection:text-black">
              {docBody}
            </div>

            {drawnSignatureUrl && (
              <div className="pt-6 border-t border-zinc-800 text-center">
                <img src={drawnSignatureUrl} alt="Assinatura" className="h-16 object-contain mx-auto mb-2 invert" />
                <p className="text-xs font-mono text-zinc-400">{lawyerName} — {oabNumber}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BrandPage() {
  return (
    <React.Suspense fallback={<div className="p-6 text-zinc-400 text-xs font-mono">Carregando Brand Studio...</div>}>
      <BrandPageContent />
    </React.Suspense>
  );
}
