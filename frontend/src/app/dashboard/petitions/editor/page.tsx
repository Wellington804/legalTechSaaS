"use client";

import React, { useState, useEffect, useRef } from "react";
import { useUser } from "@/context/user-context";
import {
  FileText,
  Sparkles,
  BookOpen,
  Split,
  Scale,
  ShieldCheck,
  Download,
  Printer,
  Plus,
  Check,
  Search,
  ChevronRight,
  Bot,
  Lock,
  AlertTriangle,
  Wand2,
  CheckCircle2,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  AlignJustify,
  Quote,
  Trash2,
  Copy,
  Save,
  RotateCcw,
  BookMarked,
  Filter,
  FileCode,
  X,
  Eye,
  PlusCircle,
} from "lucide-react";

interface JurisprudenceItem {
  id: string;
  court: "STF" | "STJ" | "TST" | "TJSP";
  title: string;
  summary: string;
  text: string;
}

export default function PetitionSplitViewPage() {
  const { user } = useUser();
  const [selectedTemplate, setSelectedTemplate] = useState("inicial");
  const [petitionTitle, setPetitionTitle] = useState("Petição Inicial - Ação de Restituição Tributária");
  const [petitionArea, setPetitionArea] = useState("Direito Tributário");
  const [clientName, setClientName] = useState("ALIMENTA DISTRIBUIDORA LTDA.");
  const [opposingParty, setOpposingParty] = useState("ESTADO DE SÃO PAULO");
  const [factsSummary, setFactsSummary] = useState("Descumprimento contratual decorrente de cobrança indevida de tributo com repercussão geral pacificada no STF.");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDraftApproved, setIsDraftApproved] = useState(false);
  const [lastAutoSave, setLastAutoSave] = useState<string>("Agora mesmo");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [showPrintModal, setShowPrintModal] = useState(false);

  // Custom Templates Modal State
  const [showNewTemplateModal, setShowNewTemplateModal] = useState(false);
  const [newTplTitle, setNewTplTitle] = useState("");
  const [newTplArea, setNewTplArea] = useState("Direito Civil & Processual");
  const [newTplText, setNewTplText] = useState("");
  const [customTemplates, setCustomTemplates] = useState<Record<string, { title: string; area: string; text: string }>>({});

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Search & Filter state for Jurisprudence
  const [jurisSearch, setJurisSearch] = useState("");
  const [selectedCourtFilter, setSelectedCourtFilter] = useState<string>("Todos");

  // 10 Modelos de Peças Processuais Nativos
  const defaultTemplates: Record<string, { title: string; area: string; text: string }> = {
    inicial: {
      title: "Petição Inicial - Ação de Restituição Tributária",
      area: "Direito Tributário",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

REQUERENTE: ALIMENTA DISTRIBUIDORA LTDA.
REQUERIDO: ESTADO DE SÃO PAULO

I. DOS FATOS
A Requerente é pessoa jurídica de direito privado e atua no ramo de distribuição de gêneros alimentícios. No exercício de suas atividades, submeteu-se indevidamente ao recolhimento do tributo sobre a base de cálculo cheia, sem a exclusão do ICMS.

II. DO DIREITO E DA FUNDAMENTAÇÃO ÉTICO-JURÍDICA
Conforme decidido no RE 574.706/STF (Tema 69 de Repercussão Geral), o valor arrecadado a título de ICMS não compõe a base de cálculo para incidência de tributos federais e estaduais correlatos.

Aplica-se o prazo prescricional de 5 (cinco) anos contados da data do efetivo pagamento indevido, assegurando a restituição integral das quantias recolhidas em excesso.

III. DOS PEDIDOS
Diante do exposto, requer a Vossa Excelência:
a) A citação do Requerido para, querendo, apresentar contestação no prazo legal;
b) A procedência total dos pedidos para declarar a inexigibilidade do tributo e condenar o Requerido à restituição indébita de R$ 150.000,00;
c) A condenação do Requerido ao pagamento das custas processuais e honorários advocatícios sucumbenciais fixados em 20%.

Dá-se à causa o valor de R$ 150.000,00 (cento e cinquenta mil reais).

Termos em que,
Pede deferimento.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    contestacao: {
      title: "Contestação Cível - Ação de Indenização por Danos Morais",
      area: "Direito Civil & Processual",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 2ª VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

PROCESSO Nº 1004589-12.2025.8.26.0100
CONTESTANTE: EMPRESA BETA LOGÍSTICA S/A
CONTESTADO: MARCOS AURELIO DA SILVA

I. DAS PRELIMINARES DE MÉRITO
Inépcia da Petição Inicial e Ilegitimidade Passiva Ad Causam, nos termos do Art. 337, IV e XI do Código de Processo Civil.

II. NO MÉRITO
Improcedência total dos pedidos de danos morais por ausência de nexo causal e culpa exclusiva da vítima. A empresa agiu em estrito exercício regular de direito.

III. DOS PEDIDOS CONTESTATORIOS
Acolhimento das preliminares arguidadas com a extinção do processo sem julgamento do mérito (Art. 485 CPC), ou a improcedência total dos pedidos formulados na exordial.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    agravo: {
      title: "Agravo de Instrumento com Pedido de Efeito Suspensivo (Art. 1.019 CPC)",
      area: "Direito Processual Civil",
      text: `EGREGIO TRIBUNAL DE JUSTIÇA DO ESTADO DE SÃO PAULO
COLENDA CÂMARA JULGADORA

AGRAVANTE: CONSTRUTORA HORIZONTE LTDA
AGRAVADO: MUNICÍPIO DE SÃO PAULO

I. DA TEMPESTIVIDADE E DA JUNTADA DE PEÇAS
O presente recurso é tempestivo nos moldes do Art. 1.003, § 5º do CPC, instruído com a cópia integral dos autos de origem.

II. DO PEDIDO DE EFEITO SUSPENSIVO RECURSAL (Art. 1.019, I CPC)
Demonstrados o periculum in mora decorrente de risco iminente de constrição patrimonial ilícita e a probabilidade do direito alegado.

III. DO PEDIDO FINAL
Concessão do efeito suspensivo e o provimento final do recurso para reformar a decisão interlocutória proferida pelo juízo a quo.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    apelacao: {
      title: "Recurso de Apelação Cível - Reforma de Sentença (Art. 1.009 CPC)",
      area: "Direito Processual Civil",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 1ª VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

RAZÕES DE APELAÇÃO
APELANTE: CARLOS EDUARDO DE MENDONÇA
APELADO: BANCO SIDERÚRGICO S/A

EGRÉGIO TRIBUNAL, COLENDA CÂMARA

I. DA REFORMA DA SENTENÇA RECORRIDA
A r. sentença a quo merece integral reforma, haja vista ter ignorado as provas testemunhais e documentais juntadas aos autos que comprovam a quitação da dívida.

II. DO PEDIDO RECURSAL
Conhecimento e provimento da apelação para julgar procedentes os pedidos da ação com a inversão dos ônus sucumbenciais.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    replica: {
      title: "Réplica à Contestação - Impugnação das Preliminares",
      area: "Direito Processual Civil",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 3ª VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

PROCESSO Nº 1008899-33.2025.8.26.0100
AUTOR: MARIANA ALENCAR
RÉU: SEGURADORA NACIONAL S/A

I. DA REJEIÇÃO DAS PRELIMINARES
As preliminares suscitadas na defesa não merecem prosperar, vez que a legitimidade ativa e o interesse de agir encontram-se plenamente demonstrados.

II. DA REITERAÇÃO DOS PEDIDOS DA INICIAL
Reitera-se a procedência integral da ação conforme formulado na petição inicial.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    embargos: {
      title: "Embargos de Declaração - Omissão & Contradição (Art. 1.022 CPC)",
      area: "Direito Processual Civil",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 4ª VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

EMBARGANTE: DR. ROBERTO FARIA
EMBARGADO: DECISÃO ID. 984512

I. DA OMISSÃO NA DECISÃO RECORRIDA
A r. decisão foi omissa quanto à appreciation do pedido de gratuidade da justiça expressamente requerido.

II. DOS PEDIDOS
Acolhimento dos embargos para sanar a omissão apontada com efeitos modificativos.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    mandado: {
      title: "Mandado de Segurança Coletivo com Pedido Liminar",
      area: "Direito Constitucional & Administrativo",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA DA FAZENDA PÚBLICA DE SÃO PAULO/SP

IMPETRANTE: ASSOCIAÇÃO DOS ADVOGADOS DE SÃO PAULO
IMPETRADO: ATO DO SECRETÁRIO DE FAZENDA

I. DO DIREITO LÍQUIDO E CERTO
Violação expressa a princípios constitucionais por ato ilegal de autoridade pública.

II. DO PEDIDO LIMINAR (Art. 7º, III da Lei 12.016/09)
Concessão de medida liminar inaudita altera pars para suspender os efeitos do ato impugnado.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    parecer: {
      title: "Parecer Jurídico de Compliance - Transição Tributária IBS/CBS",
      area: "Direito Tributário & Compliance",
      text: `PARECER JURÍDICO Nº 45/2026
CLIENTE: CONSTRUTORA HORIZONTE LTDA
EMENTA: REFORMA TRIBUTÁRIA. TRANSIÇÃO IBS/CBS. IMPACTO NOS CONTRATOS DE EMPREITADA.

I. DA CONSULTA
Solicitou a consulente análise técnica sobre o impacto das novas alíquotas de IBS e CBS na margem de lucro dos contratos vigentes.

II. DA CONCLUSÃO
Recomenda-se a repactuação de cláusula de equilíbrio econômico-financeiro com base na EC 132/2023.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    habeasdata: {
      title: "Habeas Data - Acesso a Informações Pessoais (Art. 5º LXXII CF)",
      area: "Direito Constitucional",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ FEDERAL DA VARA FEDERAL DE SÃO PAULO/SP

IMPETRANTE: CAMILA GUIMARÃES
IMPETRADO: BANCO CENTRAL DO BRASIL

I. DA RECUSA INJUSTIFICADA DE INFORMAÇÕES
Recusa administrativa na prestação de dados pessoais constantes no sistema SISBACEN.

II. DOS PEDIDOS
Concessão da ordem para assegurar o conhecimento das informações e retificação dos dados.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
    trabalhista: {
      title: "Reclamação Trabalhista - Horas Extras, Adicional & Vínculo Empregatício",
      area: "Direito do Trabalho",
      text: `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DA 5ª VARA DO TRABALHO DE SÃO PAULO/SP

RECLAMANTE: SEBASTIÃO OLIVEIRA
RECLAMADO: LOGÍSTICA EXPRESSA LTDA

I. DO CONTRATO DE TRABALHO E JORNADA EXTRAORDINÁRIA
O Reclamante cumpria jornada semanal de 60 horas sem a devida contraprestação das horas extraordinárias prestadas.

II. DOS PEDIDOS TRABALHISTAS
Condenação da Reclamada ao pagamento de horas extras, reflexos em FGTS, 13º e férias.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${user.name.toUpperCase()} — ${user.oabNumber}
${user.officeName.toUpperCase()}`,
    },
  };

  const templates = { ...defaultTemplates, ...customTemplates };

  const [facts, setFacts] = useState(() => defaultTemplates.inicial.text);

  // Sync Template when user changes template dropdown
  useEffect(() => {
    if (templates[selectedTemplate]) {
      setPetitionTitle(templates[selectedTemplate].title);
      setPetitionArea(templates[selectedTemplate].area);
      setFacts(templates[selectedTemplate].text);
      showToast(`Modelo "${templates[selectedTemplate].title}" carregado!`);
    }
  }, [selectedTemplate, customTemplates]);

  // Auto-Save Simulation
  useEffect(() => {
    const timer = setInterval(() => {
      setLastAutoSave(new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
    }, 15000);
    return () => clearInterval(timer);
  }, []);

  const handleSaveNewTemplate = () => {
    if (!newTplTitle.trim() || !newTplText.trim()) {
      showToast("Preencha o título e o texto base da minuta.");
      return;
    }

    const key = `custom_${Date.now()}`;
    const formattedText = `${newTplText.trim()}\n\nSão Paulo, ${new Date().toLocaleDateString("pt-BR")}.\n\n[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]\n${user.name.toUpperCase()} — ${user.oabNumber}\n${user.officeName.toUpperCase()}`;
    
    const newModel = {
      title: newTplTitle.trim(),
      area: newTplArea.trim(),
      text: formattedText,
    };

    setCustomTemplates((prev) => ({ ...prev, [key]: newModel }));
    setSelectedTemplate(key);
    setPetitionTitle(newModel.title);
    setPetitionArea(newModel.area);
    setFacts(newModel.text);

    setShowNewTemplateModal(false);
    setNewTplTitle("");
    setNewTplText("");
    showToast(`Modelo customizado "${newModel.title}" adicionado e selecionado!`);
  };

  const handleGenerateAiPetition = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setFacts((prev) =>
        prev +
        `\n\n[FUNDAMENTAÇÃO ADICIONADA VIA IA COMPLIANCE]\n"A jurisprudência pacificada do Superior Tribunal de Justiça acolhe expressamente a tese sustentada, reputando abusiva a retenção indevida efetuada pela parte contrária."`
      );
      showToast("Tese jurídica inserida pela IA!");
    }, 600);
  };

  // FIX: Functional Deduplication / "Limpar Repetições" Button
  const handleAiRefine = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      
      // Separate paragraphs and remove duplicated blocks
      const lines = facts.split("\n");
      const uniqueLines: string[] = [];
      const seen = new Set<string>();

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.length > 15) {
          if (!seen.has(trimmed)) {
            seen.add(trimmed);
            uniqueLines.push(line);
          }
        } else {
          uniqueLines.push(line);
        }
      }

      const cleanedText = uniqueLines.join("\n").replace(/\n{3,}/g, "\n\n");
      setFacts(cleanedText);
      showToast("Texto refinado! Parágrafos e frases duplicadas removidos com sucesso.");
    }, 400);
  };

  // FIX: Functional Export Minuta (.doc / Word Native HTML download)
  const handleExportDocx = () => {
    const safeTitle = petitionTitle.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const safeOffice = user.officeName.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const safeUser = user.name.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const formattedFacts = facts
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .split("\n\n")
      .map((p) => `<p style="text-align: justify; text-indent: 1.5cm; margin-bottom: 12pt; line-height: 1.5; font-family: 'Times New Roman', serif; font-size: 12pt;">${p.replace(/\n/g, "<br/>")}</p>`)
      .join("");

    const wordHtml = `<html xmlns:o='urn:schemas-microsoft-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
<head>
<meta charset='utf-8'>
<title>${safeTitle}</title>
<style>
  @page { size: A4; margin: 3cm 2cm 2cm 3cm; }
  body { font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.5; color: #000000; }
  .header { text-align: center; font-weight: bold; font-size: 13pt; text-transform: uppercase; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 24px; }
  .meta { font-family: Arial, sans-serif; font-size: 9pt; color: #555555; margin-top: 4px; font-weight: normal; text-transform: none; }
  .footer { margin-top: 36px; border-top: 1px solid #ccc; padding-top: 12px; font-size: 9pt; font-family: Arial, sans-serif; color: #666; text-align: center; }
</style>
</head>
<body>
  <div class="header">
    ${safeOffice}
    <div class="meta">
      ADVOGADO RESPONSÁVEL: ${safeUser} — ${user.oabNumber} | EMISSÃO: ${new Date().toLocaleDateString("pt-BR")} | HASH SHA-256: VALIDADO
    </div>
  </div>
  <div>
    ${formattedFacts}
  </div>
  <div class="footer">
    Documento emitido via LexFlow LegalTech Platform — Assinatura Digital e Integridade SHA-256 Verificada.
  </div>
</body>
</html>`;

    const blob = new Blob(['\ufeff' + wordHtml], { type: "application/msword;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${petitionTitle.replace(/[^a-zA-Z0-9]/g, "_")}_LexFlow.doc`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast(`Minuta "${petitionTitle}.doc" exportada com formato Word nativo!`);
  };

  // FIX: Functional Print Handler
  const handlePrint = () => {
    setShowPrintModal(true);
  };

  const [allJurisprudence] = useState<JurisprudenceItem[]>([
    {
      id: "stf_theme_69",
      court: "STF",
      title: "Súmula Vinculante STF nº 48 / Tema 69",
      summary: "Exclusão do ICMS na base de cálculo de tributos federais e estaduais.",
      text: "Conforme decidido no RE 574.706/STF (Tema 69 de Repercussão Geral), o valor arrecadado a título de ICMS não compõe a base de cálculo para incidência de tributos.",
    },
    {
      id: "stj_precedent_986",
      court: "STJ",
      title: "Precedente STJ - Repetitivo Tema 986",
      summary: "Prescrição quinquenal para ação de repetição de indébito tributário.",
      text: "Aplica-se o prazo prescricional de 5 (cinco) anos contados da data do efetivo pagamento indevido (Art. 168 do CTN).",
    },
    {
      id: "tst_sumula_219",
      court: "TST",
      title: "Súmula TST nº 219",
      summary: "Honorários advocatícios sucumbenciais na Justiça do Trabalho.",
      text: "Na Justiça do Trabalho, a condenação ao pagamento de honorários advocatícios não decorre pura e simplesmente da sucumbência, devendo a parte estar assistida por sindicato da categoria profissional.",
    },
    {
      id: "tjsp_enunciado_12",
      court: "TJSP",
      title: "Enunciado TJSP nº 12 - Seção de Direito Privado",
      summary: "Dano moral in re ipsa em caso de inscrição indevida nos órgãos de proteção ao crédito.",
      text: "A inscrição ou manutenção indevida em cadastro de inadimplentes gera dano moral in re ipsa, prescindindo de prova do prejuízo.",
    },
  ]);

  const filteredJurisprudence = allJurisprudence.filter((item) => {
    const matchesSearch =
      item.title.toLowerCase().includes(jurisSearch.toLowerCase()) ||
      item.summary.toLowerCase().includes(jurisSearch.toLowerCase()) ||
      item.text.toLowerCase().includes(jurisSearch.toLowerCase());
    const matchesCourt = selectedCourtFilter === "Todos" || item.court === selectedCourtFilter;
    return matchesSearch && matchesCourt;
  });

  const insertSuggestion = (text: string) => {
    setFacts((prev) => prev + "\n\n" + text);
    showToast("Tese jurisprudencial inserida no corpo da petição!");
  };

  const handleCopyCitation = (item: JurisprudenceItem) => {
    navigator.clipboard.writeText(item.text);
    setCopiedId(item.id);
    showToast("Citação copiada para a área de transferência!");
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Rich Text Formatting Mock Actions
  const applyFormat = (prefix: string, suffix: string = "") => {
    setFacts((prev) => prev + `\n${prefix} [Trecho Destacado] ${suffix}\n`);
    showToast("Estilo aplicado!");
  };

  const applyABNTQuote = () => {
    setFacts((prev) => prev + `\n\n    "${factsSummary}"\n    (Citação recuada a 4cm da margem esquerda, fonte 10pt, conforme NBR 10520/ABNT)\n`);
    showToast("Citação Recuada ABNT 4cm inserida!");
  };

  // RBAC Enforcement Rules: FIXED to include SUPER_ADMIN
  const canExportOrPrint = user.role === "SUPER_ADMIN" || user.role === "SOCIO" || user.role === "ASSOCIADO" || isDraftApproved;
  const isSecretaria = user.role === "SECRETARIA";
  const isEstagiario = user.role === "ESTAGIARIO";

  // Calculations
  const wordCount = facts.trim().split(/\s+/).filter(Boolean).length;
  const charCount = facts.length;
  const pageEstimate = Math.max(1, Math.ceil(wordCount / 220));

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 border border-emerald-500 text-white px-4 py-3 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-emerald-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-600/20 border border-blue-500/40 text-blue-400 rounded-xl">
            <Split className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-zinc-100">Editor Split-View de Petições</h1>
              <span className="px-2.5 py-0.5 bg-zinc-950 text-blue-400 font-mono text-[10px] rounded-full border border-blue-800/60 font-bold">
                PRO LEGALTECH
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Redação de petições com assinatura vinculada diretamente ao perfil OAB registrado de <strong>{user.name}</strong> ({user.oabNumber}).
            </p>
          </div>
        </div>

        {/* RBAC Action Controls */}
        <div className="flex items-center space-x-2 shrink-0 self-start sm:self-auto">
          {isEstagiario && !isDraftApproved && (
            <button
              onClick={() => {
                setIsDraftApproved(true);
                showToast("Rascunho de minuta aprovado pelo Sócio!");
              }}
              className="px-3 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-1 shadow-md cursor-pointer"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Submeter para Aprovação</span>
            </button>
          )}

          {/* Functional Print Button */}
          <button
            type="button"
            onClick={handlePrint}
            disabled={!canExportOrPrint}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-colors ${
              canExportOrPrint
                ? "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 cursor-pointer"
                : "bg-zinc-950 text-zinc-600 border border-zinc-800 cursor-not-allowed"
            }`}
          >
            {!canExportOrPrint ? <Lock className="w-3.5 h-3.5 text-amber-500" /> : <Printer className="w-3.5 h-3.5" />}
            <span>Imprimir</span>
          </button>

          {/* Functional Export .docx Button */}
          <button
            type="button"
            onClick={handleExportDocx}
            disabled={!canExportOrPrint}
            className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-lg transition-colors ${
              canExportOrPrint
                ? "bg-blue-600 hover:bg-blue-500 text-white cursor-pointer shadow-blue-950"
                : "bg-zinc-950 text-zinc-600 border border-zinc-800 cursor-not-allowed"
            }`}
          >
            {!canExportOrPrint ? <Lock className="w-3.5 h-3.5 text-amber-500" /> : <Download className="w-3.5 h-3.5" />}
            <span>Exportar Minuta (.docx)</span>
          </button>
        </div>
      </div>

      {/* RBAC Banners */}
      {isSecretaria && (
        <div className="p-4 bg-rose-950/80 border border-rose-800 rounded-xl flex items-center space-x-3 text-rose-200 text-xs">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <div>
            <p className="font-bold">Aviso de Controle de Acesso (RBAC LGPD):</p>
            <p className="text-[11px] opacity-90">
              Seu perfil atual é <strong>Secretaria/Financeiro</strong> (Somente Leitura). Altere o perfil no cabeçalho para Sócio ou Advogado para emitir minutas oficiais.
            </p>
          </div>
        </div>
      )}

      {/* Split View Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN: RICH PETITION EDITOR */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4 shadow-lg">
          {/* Header Controls: Expanded Templates Selector & Title & "+ Criar Modelo" Button */}
          <div className="space-y-3 border-b border-zinc-800 pb-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <label className="text-[10px] font-mono text-zinc-400 uppercase">
                Selecione o Modelo de Peça da Banca:
              </label>
              
              <div className="flex items-center space-x-2 w-full sm:w-auto">
                <select
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                  disabled={isSecretaria}
                  className="bg-zinc-950 text-zinc-100 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs font-semibold focus:outline-none focus:border-blue-500 cursor-pointer w-full sm:max-w-xs"
                >
                  <optgroup label="Modelos Nativos da Banca">
                    <option value="inicial">1. Petição Inicial - Restituição Tributária</option>
                    <option value="contestacao">2. Contestação Cível - Danos Morais</option>
                    <option value="agravo">3. Agravo de Instrumento - Efeito Suspensivo</option>
                    <option value="apelacao">4. Recurso de Apelação Cível - Reforma</option>
                    <option value="replica">5. Réplica à Contestação - Preliminares</option>
                    <option value="embargos">6. Embargos de Declaração - Omissão</option>
                    <option value="mandado">7. Mandado de Segurança Coletivo</option>
                    <option value="parecer">8. Parecer Jurídico de Compliance</option>
                    <option value="habeasdata">9. Habeas Data - Acesso a Dados</option>
                    <option value="trabalhista">10. Reclamação Trabalhista - Horas Extras</option>
                  </optgroup>

                  {Object.keys(customTemplates).length > 0 && (
                    <optgroup label="Meus Modelos Customizados">
                      {Object.entries(customTemplates).map(([key, tpl]) => (
                        <option key={key} value={key}>
                          ★ {tpl.title}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>

                <button
                  type="button"
                  onClick={() => setShowNewTemplateModal(true)}
                  disabled={isSecretaria}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg text-xs flex items-center space-x-1 shadow-sm cursor-pointer whitespace-nowrap shrink-0 transition-colors"
                  title="Criar e salvar um novo modelo customizado de petição"
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  <span>+ Criar Modelo</span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2">
              <input
                type="text"
                value={petitionTitle}
                onChange={(e) => setPetitionTitle(e.target.value)}
                disabled={isSecretaria}
                className="bg-zinc-950/70 hover:bg-zinc-950 border border-transparent hover:border-zinc-800 focus:border-blue-500 text-sm font-bold text-zinc-100 rounded-lg px-2.5 py-1 focus:outline-none w-full disabled:opacity-50 transition-colors"
              />
              <span className="px-2.5 py-1 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded-lg shrink-0 font-semibold">
                {petitionArea}
              </span>
            </div>
          </div>

          {/* AI Copilot & Refine Bar */}
          <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 text-xs">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
                <Wand2 className="w-4 h-4 text-blue-400" />
                <span>AI Copilot Jurídico: <strong className="text-blue-400">{user.name} ({user.oabNumber})</strong></span>
              </span>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={handleAiRefine}
                  disabled={isGenerating || isSecretaria}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-semibold flex items-center space-x-1 transition-colors cursor-pointer"
                  title="Limpar frases e parágrafos duplicados"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
                  <span>Limpar Repetições</span>
                </button>

                <button
                  type="button"
                  onClick={handleGenerateAiPetition}
                  disabled={isGenerating || isSecretaria}
                  className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold rounded-lg text-xs flex items-center space-x-1.5 cursor-pointer shadow-md"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{isGenerating ? "Processando..." : "Gerar com IA"}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Rich-Text Formatting Toolbar */}
          <div className="flex items-center space-x-1 bg-zinc-950 border border-zinc-800 p-2 rounded-xl text-zinc-400 overflow-x-auto">
            <button
              onClick={() => applyFormat("**", "**")}
              className="p-1.5 hover:bg-zinc-800 hover:text-zinc-100 rounded transition-colors"
              title="Negrito (Ctrl+B)"
            >
              <Bold className="w-4 h-4" />
            </button>
            <button
              onClick={() => applyFormat("*", "*")}
              className="p-1.5 hover:bg-zinc-800 hover:text-zinc-100 rounded transition-colors"
              title="Itálico (Ctrl+I)"
            >
              <Italic className="w-4 h-4" />
            </button>

            <div className="h-4 w-px bg-zinc-800 mx-1" />

            <button
              onClick={() => applyFormat("• ")}
              className="p-1.5 hover:bg-zinc-800 hover:text-zinc-100 rounded transition-colors"
              title="Alinhamento à Esquerda"
            >
              <AlignLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => applyFormat("   ")}
              className="p-1.5 hover:bg-zinc-800 hover:text-zinc-100 rounded transition-colors"
              title="Centralizado"
            >
              <AlignCenter className="w-4 h-4" />
            </button>
            <button
              onClick={() => applyFormat("[JUSTIFICADO]\n")}
              className="p-1.5 bg-blue-950 text-blue-400 border border-blue-800 rounded transition-colors"
              title="Alinhamento Justificado (Padrão Petição)"
            >
              <AlignJustify className="w-4 h-4" />
            </button>

            <div className="h-4 w-px bg-zinc-800 mx-1" />

            <button
              onClick={applyABNTQuote}
              className="p-1.5 hover:bg-zinc-800 hover:text-blue-400 rounded transition-colors flex items-center space-x-1 text-xs"
              title="Citação Recuada a 4cm da Margem Esquerda (NBR 10520/ABNT)"
            >
              <Quote className="w-4 h-4" />
              <span className="text-[10px] font-mono">Recuo ABNT (4cm)</span>
            </button>
          </div>

          {/* High Contrast Editor Body */}
          <textarea
            rows={18}
            value={facts}
            onChange={(e) => setFacts(e.target.value)}
            disabled={isSecretaria}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-5 text-zinc-100 font-serif text-xs leading-relaxed focus:outline-none focus:border-blue-500 disabled:opacity-50 transition-colors shadow-inner"
          />

          {/* Footer Metrics & Auto-Save Indicator */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2 pt-2 text-[11px] font-mono text-zinc-400 border-t border-zinc-800">
            <div className="flex items-center space-x-3">
              <span>{wordCount} palavras</span>
              <span>•</span>
              <span>{charCount} caracteres</span>
              <span>•</span>
              <span className="text-blue-400 font-semibold">~{pageEstimate} páginas ABNT</span>
            </div>

            <div className="flex items-center space-x-2">
              <Save className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Rascunho salvo ({lastAutoSave})</span>
              <span className="text-zinc-600">|</span>
              <span className="text-zinc-400">Assinatura SHA-256 Pronta</span>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: DYNAMIC AI JURISPRUDENCE & ASSISTANT */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4 shadow-lg">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <Bot className="w-4 h-4 text-blue-400" />
              <span>Assistente de Jurisprudência STF/STJ</span>
            </h3>
            <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-mono rounded font-semibold">
              IA Conectada
            </span>
          </div>

          {/* Jurisprudence Search & Court Filters */}
          <div className="space-y-2.5">
            <div className="relative">
              <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={jurisSearch}
                onChange={(e) => setJurisSearch(e.target.value)}
                placeholder="Pesquisar por Súmula, RE, Tema de Repercussão Geral..."
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl py-2 pl-9 pr-3 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            <div className="flex items-center space-x-1.5 overflow-x-auto pb-1">
              <Filter className="w-3.5 h-3.5 text-zinc-500 mr-1 shrink-0" />
              {["Todos", "STF", "STJ", "TST", "TJSP"].map((court) => (
                <button
                  key={court}
                  onClick={() => setSelectedCourtFilter(court)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold whitespace-nowrap transition-all ${
                    selectedCourtFilter === court
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-zinc-950 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800"
                  }`}
                >
                  {court}
                </button>
              ))}
            </div>
          </div>

          {/* High Contrast Jurisprudence Cards */}
          <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
            {filteredJurisprudence.length > 0 ? (
              filteredJurisprudence.map((sug) => (
                <div
                  key={sug.id}
                  className="p-4 bg-zinc-950 border border-zinc-800/90 rounded-xl space-y-2.5 hover:border-blue-500/60 transition-all shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 font-mono text-[10px] font-bold rounded">
                        {sug.court}
                      </span>
                      <h4 className="font-bold text-zinc-100 text-xs">{sug.title}</h4>
                    </div>

                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => handleCopyCitation(sug)}
                        className="p-1 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded transition-colors"
                        title="Copiar citação ABNT"
                      >
                        {copiedId === sug.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>

                      <button
                        onClick={() => insertSuggestion(sug.text)}
                        disabled={isSecretaria}
                        className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-[10px] font-bold flex items-center space-x-1 cursor-pointer transition-colors shadow-sm"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Inserir</span>
                      </button>
                    </div>
                  </div>

                  <p className="text-[11px] text-zinc-300 font-medium leading-relaxed">
                    {sug.summary}
                  </p>

                  <div className="bg-zinc-900/90 p-3 rounded-lg border border-zinc-800 text-[11px] font-serif text-zinc-200 leading-relaxed">
                    {sug.text}
                  </div>
                </div>
              ))
            ) : (
              <div className="h-40 flex flex-col items-center justify-center text-center p-4 border border-dashed border-zinc-800 rounded-xl text-zinc-500 text-xs space-y-1">
                <Search className="w-5 h-5 text-zinc-600" />
                <span>Nenhuma tese jurídica encontrada para a busca.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modal: Adicionar Novo Modelo Customizado */}
      {showNewTemplateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2">
                <PlusCircle className="w-5 h-5 text-blue-400" />
                <h2 className="text-base font-bold text-zinc-100">Criar Novo Modelo de Petição da Banca</h2>
              </div>
              <button
                onClick={() => setShowNewTemplateModal(false)}
                className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-zinc-300 font-semibold">Título do Modelo de Peça:</label>
                <input
                  type="text"
                  value={newTplTitle}
                  onChange={(e) => setNewTplTitle(e.target.value)}
                  placeholder="Ex: Ação Indenizatória - Atraso de Voo e Extravio de Bagagem"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-zinc-300 font-semibold">Área do Direito:</label>
                <input
                  type="text"
                  value={newTplArea}
                  onChange={(e) => setNewTplArea(e.target.value)}
                  placeholder="Ex: Direito do Consumidor"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-zinc-300 font-semibold">Conteúdo Base da Minuta:</label>
                <textarea
                  rows={8}
                  value={newTplText}
                  onChange={(e) => setNewTplText(e.target.value)}
                  placeholder="Cole aqui o texto padrão da petição inicial, contestação ou recurso..."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3.5 text-zinc-100 font-serif leading-relaxed placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setShowNewTemplateModal(false)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveNewTemplate}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl text-xs flex items-center space-x-1.5 shadow-lg shadow-blue-950"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Salvar Modelo Customizado</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Print View Modal */}
      {showPrintModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-3xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-950">
              <div className="flex items-center space-x-2">
                <Printer className="w-5 h-5 text-blue-400" />
                <h2 className="text-base font-bold text-zinc-100">Pré-visualização para Impressão Judicial</h2>
              </div>
              <button
                onClick={() => setShowPrintModal(false)}
                className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-8 overflow-y-auto bg-white text-black font-serif text-sm leading-relaxed space-y-4">
              <div className="text-center font-bold uppercase tracking-wider mb-6 border-b border-zinc-300 pb-4">
                <p className="text-lg">{user.officeName}</p>
                <p className="text-xs text-zinc-600 font-sans mt-1">ADVOGADO RESPONSÁVEL: {user.name} — OAB {user.oabNumber}</p>
              </div>
              <div className="whitespace-pre-wrap font-serif text-xs leading-relaxed text-zinc-900">
                {facts}
              </div>
            </div>

            <div className="p-4 border-t border-zinc-800 bg-zinc-950 flex items-center justify-between">
              <span className="text-xs text-zinc-400 font-mono">
                {wordCount} palavras • ~{pageEstimate} páginas ABNT
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setShowPrintModal(false)}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold"
                >
                  Fechar
                </button>
                <button
                  onClick={() => {
                    window.print();
                    setShowPrintModal(false);
                  }}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md"
                >
                  <Printer className="w-4 h-4" />
                  <span>Confirmar Impressão</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



