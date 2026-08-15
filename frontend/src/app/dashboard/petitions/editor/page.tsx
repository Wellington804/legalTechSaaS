"use client";

import React, { useState, useEffect } from "react";
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
  CheckCircle2
} from "lucide-react";

export default function PetitionSplitViewPage() {
  const { user } = useUser();
  const [petitionTitle, setPetitionTitle] = useState("Petição Inicial - Ação de Restituição Tributária");
  const [petitionArea, setPetitionArea] = useState("Direito Tributário");
  const [clientName, setClientName] = useState("ALIMENTA DISTRIBUIDORA LTDA.");
  const [opposingParty, setOpposingParty] = useState("ESTADO DE SÃO PAULO");
  const [factsSummary, setFactsSummary] = useState("Descumprimento contratual decorrente de recusa injustificada de cobertura de sinistro de transporte de cargas.");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDraftApproved, setIsDraftApproved] = useState(false);

  const generateDynamicPetitionText = (uName: string, uOab: string, uOffice: string) => {
    return `EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

REQUERENTE: ${clientName.toUpperCase()}
REQUERIDO: ${opposingParty.toUpperCase()}

I. DOS FATOS
${factsSummary}

II. DO DIREITO E DA FUNDAMENTAÇÃO
A pretensão da Autora encontra respaldo legal nos termos do Artigo 186 e 927 do Código Civil Brasileiro, bem como na jurisprudência pacificada dos Tribunais Superiores que repelem a conduta abusiva da Ré.

III. DOS PEDIDOS
Diante do exposto, requer a Vossa Excelência:
a) A citação da Ré para, querendo, apresentar contestação no prazo legal;
b) Condenação ao pagamento de indenização por danos materiais e morais no valor atualizado da causa;
c) A condenação da Ré ao pagamento das custas processuais e honorários advocatícios sucumbenciais fixados em 20% sobre o valor da causa.

Dá-se à causa o valor de R$ 150.000,00 (cento e cinquenta mil reais).

Termos em que,
Pede deferimento.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
${uName.toUpperCase()} — ${uOab}
${uOffice.toUpperCase()}`;
  };

  const [facts, setFacts] = useState(() =>
    generateDynamicPetitionText(user.name, user.oabNumber, user.officeName)
  );

  // Atualizar petição dinamicamente se o usuário logado mudar
  useEffect(() => {
    setFacts((prev) => {
      // Substituir o bloco final de assinatura pelo nome do usuário logado
      const parts = prev.split("[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]");
      if (parts.length > 1) {
        return `${parts[0]}[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]\n${user.name.toUpperCase()} — ${user.oabNumber}\n${user.officeName.toUpperCase()}`;
      }
      return prev;
    });
  }, [user]);

  const handleGenerateAiPetition = () => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setFacts(generateDynamicPetitionText(user.name, user.oabNumber, user.officeName));
    }, 600);
  };

  const [aiSuggestions] = useState([
    {
      id: "stf_theme",
      title: "Súmula Vinculante STF nº 48",
      summary: "Garantia de ressarcimento de tributos indiretos sem necessidade de prova de não-repercussão.",
      text: "Conforme decidido no RE 574.706/STF (Tema 69 de Repercussão Geral), o valor arrecadado não compõe a base de cálculo."
    },
    {
      id: "stj_precedent",
      title: "Precedente STJ - Repetitivo Tema 986",
      summary: "Prescrição quinquenal para repetição de indébito tributário.",
      text: "Aplica-se o prazo prescricional de 5 (cinco) anos contados da data do efetivo pagamento indevido."
    }
  ]);

  const insertSuggestion = (text: string) => {
    setFacts((prev) => prev + "\n\n" + text);
  };

  // RBAC Enforcement Rules
  const canExportOrPrint = user.role === "SOCIO" || user.role === "ASSOCIADO" || isDraftApproved;
  const isSecretaria = user.role === "SECRETARIA";
  const isEstagiario = user.role === "ESTAGIARIO";

  return (
    <div className="space-y-6">
      {/* Top Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-blue-600/20 border border-blue-500/40 text-blue-400 rounded-xl">
            <Split className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-zinc-100">Editor Split-View de Petições</h1>
              <span className="px-2 py-0.5 bg-zinc-800 text-zinc-300 font-mono text-[10px] rounded border border-zinc-700">
                Logado: {user.name} ({user.oabNumber})
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Redação de petições com assinatura vinculada diretamente ao seu perfil OAB registrado.
            </p>
          </div>
        </div>

        {/* RBAC Action Controls */}
        <div className="flex items-center space-x-2">
          {isEstagiario && !isDraftApproved && (
            <button
              onClick={() => {
                setIsDraftApproved(true);
                alert("Rascunho de minuta submetido e aprovado pelo Sócio com sucesso!");
              }}
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold flex items-center space-x-1 shadow-md cursor-pointer"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Submeter para Aprovação do Sócio</span>
            </button>
          )}

          <button
            onClick={() => {
              if (!canExportOrPrint) {
                alert("Acesso Negado (RBAC): Estagiários podem apenas redigir rascunhos. Exige aprovação de um Sócio para imprimir.");
                return;
              }
              window.print();
            }}
            disabled={!canExportOrPrint}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1 transition-colors ${
              canExportOrPrint
                ? "bg-zinc-800 hover:bg-zinc-700 text-zinc-200 cursor-pointer"
                : "bg-zinc-900 text-zinc-600 border border-zinc-800 cursor-not-allowed"
            }`}
          >
            {!canExportOrPrint ? <Lock className="w-3.5 h-3.5 text-amber-500" /> : <Printer className="w-3.5 h-3.5" />}
            <span>Imprimir</span>
          </button>

          <button
            onClick={() => {
              if (!canExportOrPrint) {
                alert("Acesso Negado (RBAC): Estagiários não possuem permissão para exportar a petição final sem a assinatura/aprovação de um Sócio.");
                return;
              }
              alert(`Exportando minuta oficial assinada por ${user.name} (${user.oabNumber}) em formato .docx`);
            }}
            disabled={!canExportOrPrint}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1 shadow-md transition-colors ${
              canExportOrPrint
                ? "bg-blue-600 hover:bg-blue-500 text-white cursor-pointer"
                : "bg-zinc-900 text-zinc-600 border border-zinc-800 cursor-not-allowed"
            }`}
          >
            {!canExportOrPrint ? <Lock className="w-3.5 h-3.5 text-amber-500" /> : <Download className="w-3.5 h-3.5" />}
            <span>Exportar Minuta (.docx)</span>
          </button>
        </div>
      </div>

      {/* RBAC Warning Banner for Secretaria */}
      {isSecretaria && (
        <div className="p-4 bg-rose-950/80 border border-rose-800 rounded-xl flex items-center space-x-3 text-rose-200 text-xs">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <div>
            <p className="font-bold">Aviso de Controle de Acesso (RBAC LGPD):</p>
            <p className="text-[11px] opacity-90">
              Seu perfil atual é <strong>Secretaria/Financeiro</strong>. Você possui permissão apenas de visualização. Para alterar a petição ou emitir minutas oficiais, altere o perfil no cabeçalho para Sócio ou Advogado.
            </p>
          </div>
        </div>
      )}

      {/* RBAC Warning Banner for Estagiario */}
      {isEstagiario && !isDraftApproved && (
        <div className="p-4 bg-amber-950/80 border border-amber-800 rounded-xl flex items-center space-x-3 text-amber-200 text-xs">
          <Lock className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <p className="font-bold">Modo Rascunho de Estagiário (RBAC):</p>
            <p className="text-[11px] opacity-90">
              Você está redigindo como <strong>Estagiário ({user.name})</strong>. A exportação e protocolo do documento final exigem submissão e aprovação prévia de um Advogado Sócio.
            </p>
          </div>
        </div>
      )}

      {/* Split View Container */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN: FORM & RICH PETITION EDITOR */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <input
              type="text"
              value={petitionTitle}
              onChange={(e) => setPetitionTitle(e.target.value)}
              disabled={isSecretaria}
              className="bg-transparent text-sm font-bold text-zinc-100 focus:outline-none w-full disabled:opacity-50"
            />
            <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded shrink-0">
              {petitionArea}
            </span>
          </div>

          {/* Quick AI Trigger */}
          <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
                <Wand2 className="w-3.5 h-3.5 text-blue-400" />
                <span>Gerar Minuta no Nome de: <strong className="text-blue-400">{user.name} ({user.oabNumber})</strong></span>
              </span>
              <button
                onClick={handleGenerateAiPetition}
                disabled={isGenerating || isSecretaria}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold rounded-lg text-xs flex items-center space-x-1.5 cursor-pointer shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isGenerating ? "Gerando..." : "Gerar Minuta de Petição"}</span>
              </button>
            </div>
          </div>

          <textarea
            rows={20}
            value={facts}
            onChange={(e) => setFacts(e.target.value)}
            disabled={isSecretaria}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-zinc-200 font-serif text-xs leading-relaxed focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
        </div>

        {/* RIGHT COLUMN: AI JURISPRUDENCE & ASSISTANT */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <Bot className="w-4 h-4 text-blue-400" />
              <span>Assistente de Jurisprudência STF/STJ</span>
            </h3>
            <span className="px-2 py-0.5 bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-mono rounded">
              IA Conectada
            </span>
          </div>

          <div className="space-y-3">
            {aiSuggestions.map((sug) => (
              <div key={sug.id} className="p-3.5 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 hover:border-blue-500/50 transition-all">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-zinc-200 text-xs">{sug.title}</h4>
                  <button
                    onClick={() => insertSuggestion(sug.text)}
                    disabled={isSecretaria}
                    className="px-2 py-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-[10px] font-semibold flex items-center space-x-1 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Inserir na Petição</span>
                  </button>
                </div>
                <p className="text-[11px] text-zinc-400">{sug.summary}</p>
                <p className="text-[10px] font-mono text-zinc-500 bg-zinc-900 p-2 rounded border border-zinc-800">{sug.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
