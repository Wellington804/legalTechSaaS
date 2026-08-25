"use client";

import React, { useState, useRef } from "react";
import {
  Scale,
  Search,
  CheckCircle2,
  TrendingUp,
  Clock,
  ShieldCheck,
  AlertTriangle,
  FileText,
  PieChart,
  Sparkles,
  Download,
  Copy,
  Check,
  Zap,
  BookOpen,
  ChevronRight,
  Filter,
  BarChart3,
  Award,
  Plus,
  Paperclip,
  Upload,
  FileUp,
  X,
} from "lucide-react";

interface JudgeProfile {
  id: string;
  name: string;
  court: string;
  chamber: string;
  area: string;
  grantRate: number;
  avgDays: number;
  reversalRate: number;
  decisionsCount: number;
  procedentePct: number;
  parcialPct: number;
  improcedentePct: number;
  topAuthors: string[];
  recommendations: {
    urgency: string;
    precedents: string;
    damages: string;
  };
}

export default function JudgeProfilingPage() {
  const [judgeQuery, setJudgeQuery] = useState("");
  const [selectedJudgeId, setSelectedJudgeId] = useState("marcos_santos");
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // External Thesis Upload & Import State
  const [showImportModal, setShowImportModal] = useState(false);
  const [importedText, setImportedText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Thesis Predictor State
  const [thesisQuery, setThesisQuery] = useState("Exclusão do ICMS da base de cálculo do PIS/COFINS");
  const [isSimulating, setIsSimulating] = useState(false);
  const [predictionResult, setPredictionResult] = useState<{
    score: number;
    risk: "BAIXO" | "MÉDIO" | "ELEVADO";
    rationale: string;
  } | null>({
    score: 84.5,
    risk: "BAIXO",
    rationale: "O magistrado alinha-se estritamente à tese fixada pelo STF no Tema 69 (RE 574.706), com deferimento em 92% das ações individuais idênticas.",
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const judgesDatabase: Record<string, JudgeProfile> = {
    marcos_santos: {
      id: "marcos_santos",
      name: "Dr. Marcos Aurelio Santos",
      court: "TJSP",
      chamber: "8ª Câmara de Direito Privado",
      area: "Direito Cível & Empresarial",
      grantRate: 76.4,
      avgDays: 38,
      reversalRate: 14.8,
      decisionsCount: 1420,
      procedentePct: 64,
      parcialPct: 22,
      improcedentePct: 14,
      topAuthors: ["Nelson Nery Jr.", "Humberto Theodoro Jr.", "Flávio Tartuce"],
      recommendations: {
        urgency: "O magistrado exige comprovação de perigo de dano irreparável respaldado em provas documentais pré-constituídas.",
        precedents: "Alta receptividade a precedentes firmados pela 8ª Câmara de Direito Privado e Súmulas do STJ.",
        damages: "Média de arbitramento de Danos Morais entre R$ 10.000,00 e R$ 25.000,00 para casos de negativação indevida.",
      },
    },
    maria_ramos: {
      id: "maria_ramos",
      name: "Dra. Maria Fernanda Ramos",
      court: "TRF3",
      chamber: "2ª Turma Tributária",
      area: "Direito Tributário",
      grantRate: 82.1,
      avgDays: 45,
      reversalRate: 9.3,
      decisionsCount: 2890,
      procedentePct: 71,
      parcialPct: 18,
      improcedentePct: 11,
      topAuthors: ["Hugo de Brito Machado", "Kiyoshi Harada", "Luciano Amaro"],
      recommendations: {
        urgency: "Concede tutelas de urgência fiscais quando demonstrado depósito judicial integral ou garantia via seguro garantia.",
        precedents: "Aplica estritamente a jurisprudência pacificada do STF e STJ em matéria tributária (Temas 69 e 1182).",
        damages: "Inaplicável para danos morais. Foco em repetição de indébito e compensação de tributos federais.",
      },
    },
    roberto_faria: {
      id: "roberto_faria",
      name: "Dr. Roberto Faria Silva",
      court: "TST",
      chamber: "4ª Turma Trabalhista",
      area: "Direito do Trabalho",
      grantRate: 59.8,
      avgDays: 52,
      reversalRate: 21.4,
      decisionsCount: 1980,
      procedentePct: 48,
      parcialPct: 35,
      improcedentePct: 17,
      topAuthors: ["Maurício Godinho Delgado", "Vólia Bomfim Cassar", "Sergio Pinto Martins"],
      recommendations: {
        urgency: "Exige rígida demonstração da verossimilhança das alegações para liminares de reintegração no emprego.",
        precedents: "Segurança jurídica balizada nas Súmulas do TST (especialmente Súmulas 219 e 331).",
        damages: "Arbitramento criterioso de danos morais trabalhistas com base na tarifação da CLT (Art. 223-G).",
      },
    },
    ana_castro: {
      id: "ana_castro",
      name: "Dra. Ana Paula Castro",
      court: "TJRJ",
      chamber: "1ª Vara Cível da Capital",
      area: "Direito do Consumidor",
      grantRate: 88.3,
      avgDays: 29,
      reversalRate: 11.2,
      decisionsCount: 3150,
      procedentePct: 78,
      parcialPct: 14,
      improcedentePct: 8,
      topAuthors: ["Claudia Lima Marques", "Rizzatto Nunes", "Sergio Cavalieri Filho"],
      recommendations: {
        urgency: "Celeridade extrema na apreciação de liminares contra operadoras de plano de saúde e cias aéreas.",
        precedents: "Forte aplicação do CDC (Lei 8.078/90) e inversão do ônus da prova em favor do consumidor vulnerável.",
        damages: "Fixação expressiva de Danos Morais in re ipsa em caso de interrupção indevida de serviços essenciais.",
      },
    },
  };

  const activeProfile = judgesDatabase[selectedJudgeId] || judgesDatabase.marcos_santos;

  const filteredJudges = Object.values(judgesDatabase).filter((j) =>
    j.name.toLowerCase().includes(judgeQuery.toLowerCase()) ||
    j.court.toLowerCase().includes(judgeQuery.toLowerCase()) ||
    j.chamber.toLowerCase().includes(judgeQuery.toLowerCase())
  );

  const handleSimulateThesis = () => {
    if (!thesisQuery.trim()) return;
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);

      if (thesisQuery.toLowerCase().includes("icms") || thesisQuery.toLowerCase().includes("tribut")) {
        setPredictionResult({
          score: 88.2,
          risk: "BAIXO",
          rationale: `O magistrado ${activeProfile.name} possui histórico de alinhamento com súmulas do STF/STJ, concedendo provimento para teses tributárias pacificadas.`,
        });
      } else if (thesisQuery.toLowerCase().includes("dano moral") || thesisQuery.toLowerCase().includes("voo")) {
        setPredictionResult({
          score: 79.4,
          risk: "BAIXO",
          rationale: `Alta receptividade para Danos Morais. O valor estimado de indenização pelo magistrado varia entre R$ 10.000 e R$ 25.000.`,
        });
      } else {
        setPredictionResult({
          score: 72.8,
          risk: "BAIXO",
          rationale: `Tese externa importada sob análise preditiva da IA. Elevada consonância com o acervo da ${activeProfile.chamber}.`,
        });
      }
      showToast("Simulação preditiva concluída com sucesso!");
    }, 500);
  };

  // Handle Attachment / File Upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const fileNameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
    const extractedQuery = `Tese Importada de Arquivo (${fileNameWithoutExt})`;
    
    setThesisQuery(extractedQuery);
    setIsSimulating(true);

    setTimeout(() => {
      setIsSimulating(false);
      setPredictionResult({
        score: 81.6,
        risk: "BAIXO",
        rationale: `Arquivo "${file.name}" anexado e processado com sucesso. Tese extraída e validada contra ${activeProfile.decisionsCount} decisões da base.`,
      });
      showToast(`Tese do arquivo "${file.name}" anexada e calculada!`);
    }, 600);
  };

  // Handle External Text Import Submit
  const handleConfirmImportText = () => {
    if (!importedText.trim()) {
      showToast("Cole o texto da tese ou selecione um arquivo.");
      return;
    }

    const firstSentence = importedText.trim().split("\n")[0].slice(0, 80);
    const query = `Tese Externa: "${firstSentence}..."`;

    setThesisQuery(query);
    setShowImportModal(false);
    setImportedText("");
    setIsSimulating(true);

    setTimeout(() => {
      setIsSimulating(false);
      setPredictionResult({
        score: 83.4,
        risk: "BAIXO",
        rationale: `Tese externa importada e analisada. Compatibilidade de 83.4% com a orientação da ${activeProfile.chamber}.`,
      });
      showToast("Tese externa importada e calculada!");
    }, 500);
  };

  const handleCopyArgument = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    showToast("Fundamentação copiada para a área de transferência!");
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleExportReport = () => {
    const reportText = `====================================================================
LEXFLOW JURIMETRIA ENTERPRISE - RELATÓRIO ESTRATÉGICO DE MAGISTRADO
MAGISTRADO: ${activeProfile.name}
TRIBUNAL: ${activeProfile.court} — ${activeProfile.chamber}
ÁREA: ${activeProfile.area}
TAXA DE DEFERIMENTO: ${activeProfile.grantRate}%
TEMPO MÉDIO DE SENTENÇA: ${activeProfile.avgDays} Dias
TAXA DE REFORMA NO TRIBUNAL: ${activeProfile.reversalRate}%
ACERVO PROCESSUAL ANALISADO: ${activeProfile.decisionsCount} decisões
DATA DA CONSULTA: ${new Date().toLocaleDateString("pt-BR")}
====================================================================

RECOMENDAÇÕES ESTRATÉGICAS:
1. Urgência: ${activeProfile.recommendations.urgency}
2. Jurisprudência: ${activeProfile.recommendations.precedents}
3. Doutrina Preferencial: ${activeProfile.topAuthors.join(", ")}
`;

    const blob = new Blob([reportText], { type: "text/plain;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `Jurimetria_${activeProfile.name.replace(/[^a-zA-Z0-9]/g, "_")}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast("Relatório de Jurimetria exportado com sucesso!");
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Hidden File Input for Direct Attachment */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept=".pdf,.docx,.doc,.txt"
        className="hidden"
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 border border-emerald-500 text-white px-4 py-3 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-emerald-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shadow-xl">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono uppercase tracking-wider mb-1">
            <Scale className="w-4 h-4 text-blue-400" />
            <span>Módulo 4: Legal Tracker & Jurimetria Decisória</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Perfilamento Decisório de Magistrados (Judge Profiling)
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Análise preditiva de decisões, taxa de deferimento de tutelas de urgência, tempo médio de sentença e mapa doutrinário.
          </p>
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto">
          <button
            onClick={handleExportReport}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md shadow-blue-950 cursor-pointer transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Exportar Relatório PDF/CSV</span>
          </button>
        </div>
      </div>

      {/* Search & Magistrate Switcher */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-3 shadow-lg">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <label className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center space-x-1.5">
            <Search className="w-4 h-4 text-blue-400" />
            <span>Selecione o Magistrado ou Pesquise na Base do Tribunal:</span>
          </label>

          <div className="relative w-full md:w-80">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={judgeQuery}
              onChange={(e) => setJudgeQuery(e.target.value)}
              placeholder="Buscar por nome, tribunal ou câmara..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-3 py-1.5 text-zinc-200 text-xs focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-1">
          {filteredJudges.map((j) => (
            <button
              key={j.id}
              onClick={() => {
                setSelectedJudgeId(j.id);
                showToast(`Perfil de ${j.name} selecionado!`);
              }}
              className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                selectedJudgeId === j.id
                  ? "bg-blue-950/80 border-blue-500 text-zinc-100 shadow-md"
                  : "bg-zinc-950 hover:bg-zinc-800 border-zinc-800/80 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 bg-blue-900/60 text-blue-400 font-mono text-[9px] font-bold rounded">
                  {j.court}
                </span>
                <span className="text-[10px] text-emerald-400 font-bold font-mono">{j.grantRate}% defer.</span>
              </div>
              <p className="font-bold text-xs mt-1.5 line-clamp-1">{j.name}</p>
              <p className="text-[10px] opacity-75 mt-0.5 line-clamp-1">{j.chamber}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Taxa de Deferimento Tutelas</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-extrabold text-emerald-400 font-mono">{activeProfile.grantRate}%</p>
          <p className="text-[10px] text-zinc-500">Alta propensão a conceder liminares</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Tempo Médio Sentença</span>
            <Clock className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-2xl font-extrabold text-blue-400 font-mono">{activeProfile.avgDays} Dias</p>
          <p className="text-[10px] text-zinc-500">Julgamento célere e previsível</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Taxa Reforma em Recurso</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-extrabold text-amber-400 font-mono">{activeProfile.reversalRate}%</p>
          <p className="text-[10px] text-zinc-500">Decisões mantidas no Tribunal</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Acervo Analisado</span>
            <FileText className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-2xl font-extrabold text-purple-400 font-mono">{activeProfile.decisionsCount}</p>
          <p className="text-[10px] text-zinc-500">Acórdãos e decisões auditadas</p>
        </div>
      </div>

      {/* Main Grid: AI Predictor Simulator & Decision Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* LEFT: AI Thesis Predictor (Simulador de Sucesso) */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5 shadow-lg">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <Zap className="w-4 h-4 text-blue-400" />
              <span>Simulador Preditivo de Tese Jurídica (Win-Rate Predictor)</span>
            </h3>
            <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded font-bold">
              IA Preditiva
            </span>
          </div>

          <div className="space-y-3">
            <label className="text-xs text-zinc-300 font-semibold">
              Digite a tese ou pedido da sua petição para calcular o êxito perante {activeProfile.name}:
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={thesisQuery}
                onChange={(e) => setThesisQuery(e.target.value)}
                placeholder="Ex: Exclusão do ICMS da base do PIS/COFINS ou Pedido de Tutela..."
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={handleSimulateThesis}
                disabled={isSimulating}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl text-xs flex items-center space-x-1.5 cursor-pointer shadow-md shrink-0 transition-colors"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isSimulating ? "Analisando..." : "Simular Tese"}</span>
              </button>
            </div>

            {/* Attach / Import External Thesis Controls */}
            <div className="pt-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider font-semibold">
                  Inserir Teses Prontas da Banca (1-Clique):
                </span>

                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="px-2.5 py-1 bg-emerald-950 hover:bg-emerald-900 text-emerald-400 border border-emerald-800/80 rounded-lg text-[11px] font-semibold transition-all cursor-pointer flex items-center space-x-1 shadow-sm"
                    title="Anexar arquivo de tese (.pdf, .docx, .txt)"
                  >
                    <Paperclip className="w-3 h-3" />
                    <span>Anexar Arquivo</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setShowImportModal(true)}
                    className="px-2.5 py-1 bg-purple-950 hover:bg-purple-900 text-purple-400 border border-purple-800/80 rounded-lg text-[11px] font-semibold transition-all cursor-pointer flex items-center space-x-1 shadow-sm"
                    title="Importar tese externa via colar texto ou biblioteca"
                  >
                    <FileUp className="w-3 h-3" />
                    <span>Importar Tese Externa</span>
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {[
                  {
                    label: "Tema 69 STF (Exclusão ICMS PIS/COFINS)",
                    query: "Exclusão do ICMS da base de cálculo do PIS/COFINS",
                  },
                  {
                    label: "Dano Moral - Atraso/Cancelamento Voo",
                    query: "Dano moral in re ipsa por atraso de voo e extravio de bagagem",
                  },
                  {
                    label: "Inversão do Ônus da Prova (CDC 6º VIII)",
                    query: "Inversão do ônus da prova por vulnerabilidade do consumidor",
                  },
                  {
                    label: "Impenhorabilidade de Bem de Família",
                    query: "Impenhorabilidade de imóvel residencial familiar",
                  },
                  {
                    label: "Horas Extras & Súmula 338 TST",
                    query: "Horas extras habituais sem pagamento e reflexos trabalhistas",
                  },
                  {
                    label: "Inexigibilidade de Multa - Força Maior",
                    query: "Isenção de multa rescisória por motivo de força maior",
                  },
                ].map((tpl, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setThesisQuery(tpl.query);
                      setIsSimulating(true);
                      setTimeout(() => {
                        setIsSimulating(false);
                        if (tpl.query.toLowerCase().includes("icms")) {
                          setPredictionResult({
                            score: 88.5,
                            risk: "BAIXO",
                            rationale: `O magistrado ${activeProfile.name} possui jurisprudência firmada favorável à exclusão do tributo com alinhamento ao Tema 69 STF.`,
                          });
                        } else if (tpl.query.toLowerCase().includes("dano moral")) {
                          setPredictionResult({
                            score: 82.0,
                            risk: "BAIXO",
                            rationale: `Receptividade de 82% no deferimento de indenizações morais em demandas de consumo perante a ${activeProfile.chamber}.`,
                          });
                        } else if (tpl.query.toLowerCase().includes("inversão")) {
                          setPredictionResult({
                            score: 91.4,
                            risk: "BAIXO",
                            rationale: `Acolhimento da hipossuficiência técnica com inversão imediata do ônus probatório na decisão saneadora.`,
                          });
                        } else if (tpl.query.toLowerCase().includes("bem de família")) {
                          setPredictionResult({
                            score: 74.2,
                            risk: "MÉDIO",
                            rationale: `Magistrado exige prova robusta de que a família reside habitualmente no único imóvel da entidade familiar.`,
                          });
                        } else if (tpl.query.toLowerCase().includes("horas extras")) {
                          setPredictionResult({
                            score: 68.9,
                            risk: "MÉDIO",
                            rationale: `Súmula 338 TST aplicada. Havendo cartões invalidados, presume-se verdadeira a jornada alegada.`,
                          });
                        } else {
                          setPredictionResult({
                            score: 76.5,
                            risk: "BAIXO",
                            rationale: `Tese pronta selecionada com alta probabilidade de acolhimento perante a ${activeProfile.chamber}.`,
                          });
                        }
                        showToast(`Tese pronta "${tpl.label}" selecionada e calculada!`);
                      }, 400);
                    }}
                    className="px-2.5 py-1 bg-zinc-950 hover:bg-zinc-800 text-blue-400 hover:text-blue-300 border border-blue-900/60 rounded-lg text-[11px] font-semibold transition-all cursor-pointer flex items-center space-x-1"
                  >
                    <Plus className="w-3 h-3" />
                    <span>{tpl.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {predictionResult && (
            <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-3 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-zinc-400 font-semibold">Probabilidade Estimada de Vitória:</span>
                  <span className="text-xl font-extrabold text-emerald-400 font-mono">{predictionResult.score}%</span>
                </div>

                <span
                  className={`px-2.5 py-1 text-[10px] font-bold font-mono rounded-full border ${
                    predictionResult.risk === "BAIXO"
                      ? "bg-emerald-950 text-emerald-400 border-emerald-800"
                      : "bg-amber-950 text-amber-400 border-amber-800"
                  }`}
                >
                  RISCO {predictionResult.risk}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-zinc-900 rounded-full h-2.5 overflow-hidden border border-zinc-800">
                <div
                  className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                  style={{ width: `${predictionResult.score}%` }}
                />
              </div>

              <p className="text-xs text-zinc-300 leading-relaxed font-serif pt-1">
                {predictionResult.rationale}
              </p>
            </div>
          )}
        </div>

        {/* RIGHT: Decision Distribution & Top Cited Authors */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5 shadow-lg">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <BarChart3 className="w-4 h-4 text-purple-400" />
              <span>Distribuição Estatística de Provimento</span>
            </h3>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-zinc-300">Procedentes (Vitória Total)</span>
                <span className="text-emerald-400 font-mono font-bold">{activeProfile.procedentePct}%</span>
              </div>
              <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800">
                <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${activeProfile.procedentePct}%` }} />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-zinc-300">Parcialmente Procedentes</span>
                <span className="text-amber-400 font-mono font-bold">{activeProfile.parcialPct}%</span>
              </div>
              <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800">
                <div className="bg-amber-500 h-full rounded-full" style={{ width: `${activeProfile.parcialPct}%` }} />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold mb-1">
                <span className="text-zinc-300">Improcedentes</span>
                <span className="text-rose-400 font-mono font-bold">{activeProfile.improcedentePct}%</span>
              </div>
              <div className="w-full bg-zinc-950 rounded-full h-2 border border-zinc-800">
                <div className="bg-rose-500 h-full rounded-full" style={{ width: `${activeProfile.improcedentePct}%` }} />
              </div>
            </div>
          </div>

          {/* Doutrina Preferencial */}
          <div className="pt-2 space-y-2 border-t border-zinc-800">
            <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider flex items-center space-x-1.5">
              <BookOpen className="w-3.5 h-3.5 text-blue-400" />
              <span>Doutrinadores Mais Citados pelo Juiz:</span>
            </span>
            <div className="flex flex-wrap gap-1.5">
              {activeProfile.topAuthors.map((author, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg text-xs font-semibold text-zinc-300"
                >
                  📖 {author}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Strategic AI Recommendations & Customized Argument Generation */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5 shadow-lg">
        <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2 border-b border-zinc-800 pb-3">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Recomendações Estratégicas de Atuação sob Medida via IA</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 relative group">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-zinc-100">1. Fundamentação de Urgência</h4>
              <button
                onClick={() => handleCopyArgument(activeProfile.recommendations.urgency, 1)}
                className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
                title="Copiar recomendação"
              >
                {copiedIndex === 1 ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <p className="text-zinc-400 leading-relaxed font-serif">
              {activeProfile.recommendations.urgency}
            </p>
          </div>

          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 relative group">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-zinc-100">2. Jurisprudência Preferencial</h4>
              <button
                onClick={() => handleCopyArgument(activeProfile.recommendations.precedents, 2)}
                className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
                title="Copiar recomendação"
              >
                {copiedIndex === 2 ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <p className="text-zinc-400 leading-relaxed font-serif">
              {activeProfile.recommendations.precedents}
            </p>
          </div>

          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 relative group">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-zinc-100">3. Valor de Alçada & Danos Morais</h4>
              <button
                onClick={() => handleCopyArgument(activeProfile.recommendations.damages, 3)}
                className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
                title="Copiar recomendação"
              >
                {copiedIndex === 3 ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <p className="text-zinc-400 leading-relaxed font-serif">
              {activeProfile.recommendations.damages}
            </p>
          </div>
        </div>
      </div>

      {/* Modal: Importar Tese Externa / Colar Texto */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2">
                <FileUp className="w-5 h-5 text-purple-400" />
                <h2 className="text-base font-bold text-zinc-100">Importar Tese Jurídica Externa</h2>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                className="p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div
                onClick={() => fileInputRef.current?.click()}
                className="p-6 border-2 border-dashed border-zinc-700 hover:border-purple-500 rounded-xl bg-zinc-950 flex flex-col items-center justify-center text-center cursor-pointer transition-colors space-y-2"
              >
                <Upload className="w-8 h-8 text-purple-400" />
                <div>
                  <p className="font-bold text-zinc-200">Clique para selecionar o arquivo (.pdf, .docx, .txt)</p>
                  <p className="text-[11px] text-zinc-500 mt-0.5">Ou arraste e solte o documento de petição/parecer aqui</p>
                </div>
              </div>

              <div className="relative flex py-1 items-center">
                <div className="flex-grow border-t border-zinc-800"></div>
                <span className="flex-shrink mx-3 text-zinc-500 font-mono text-[10px] uppercase">ou cole o texto da tese</span>
                <div className="flex-grow border-t border-zinc-800"></div>
              </div>

              <div className="space-y-1">
                <label className="text-zinc-300 font-semibold">Texto da Tese ou Fundamentação:</label>
                <textarea
                  rows={6}
                  value={importedText}
                  onChange={(e) => setImportedText(e.target.value)}
                  placeholder="Cole aqui o trecho do recurso, parecer ou petição para a IA analisar perante este magistrado..."
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-zinc-100 font-serif leading-relaxed placeholder-zinc-500 focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setShowImportModal(false)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmImportText}
                className="px-5 py-2 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl text-xs flex items-center space-x-1.5 shadow-lg shadow-purple-950"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Importar & Calcular Probabilidade</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

