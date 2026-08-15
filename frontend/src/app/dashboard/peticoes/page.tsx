"use client";

import React, { useState } from "react";
import {
  Scale,
  Sparkles,
  Copy,
  Download,
  Check,
  FileText,
  Briefcase,
  BookOpen,
  ArrowRight,
  RefreshCcw,
} from "lucide-react";

export default function PeticoesPage() {
  const [area, setArea] = useState("Cível");
  const [tipoPeca, setTipoPeca] = useState("Petição Inicial");
  const [autor, setAutor] = useState("Empresa Alfa Comércio e Serviços Ltda");
  const [reu, setReu] = useState("Seguradora Beta S/A");
  const [fatos, setFatos] = useState("Descumprimento contratual decorrente de recusa injustificada de cobertura de sinistro de transporte de cargas.");
  const [pedidos, setPedidos] = useState("Condenação ao pagamento de indenização por danos materiais no valor de R$ 150.000,00 acrescido de lucros cessantes.");
  const [isGenerating, setIsGenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const [generatedDraft, setGeneratedDraft] = useState<string | null>(null);

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setGeneratedDraft(`EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA ____ª VARA CÍVEL DA COMARCA DE SÃO PAULO - SP

ÁREA: DIREITO ${area.toUpperCase()}
PROCESSO DE EXECUÇÃO / AÇÃO CONHECIMENTO

${autor.toUpperCase()}, pessoa jurídica de direito privado, inscrita no CNPJ/MF sob o nº XX.XXX.XXX/0001-XX, por seu advogado infra-assinado, vem, respeitosamente, à presença de Vossa Excelência, propor a presente

${tipoPeca.toUpperCase()} COM PEDIDO DE TUTELA DE URGÊNCIA

em face de ${reu.toUpperCase()}, pessoa jurídica de direito privado, inscrita no CNPJ sob nº YY.YYY.YYY/0001-YY, pelos fatos e fundamentos jurídicos a seguir expostos:

I - DOS FATOS
${fatos}

II - DO DIREITO
A pretensão da Autora encontra respaldo legal nos termos do Artigo 186 e 927 do Código Civil Brasileiro, bem como na jurisprudência pacificada dos Tribunais Superiores que repelem a conduta abusiva da Ré.

III - DOS PEDIDOS
Diante do exposto, requer a Vossa Excelência:
a) A citação da Ré para, querendo, apresentar contestação no prazo legal;
b) ${pedidos};
c) A condenação da Ré ao pagamento das custas processuais e honorários advocatícios sucumbenciais fixados em 20% (vinte por cento) sobre o valor atualizado da causa.

Dá-se à causa o valor de R$ 150.000,00 (cento e cinquenta mil reais).

Termos em que,
Pede deferimento.

São Paulo, ${new Date().toLocaleDateString("pt-BR")}.

[Assinatura Eletrônica Certificada SHA-256 via LexFlow API]
Advogado(a) OAB/SP 482.910`);
    }, 700);
  };

  const handleCopy = () => {
    if (!generatedDraft) return;
    navigator.clipboard.writeText(generatedDraft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono uppercase tracking-wider mb-2">
          <Scale className="w-4 h-4 text-blue-400" />
          <span>Motor de Redação Jurídica Generativa LexFlow AI</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Central de Petições Inteligentes
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Gere minutas processuais completas, petições iniciais, recursos e peças de urgência fundamentadas na doutrina e jurisprudência dos Tribunais Superiores.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form Inputs */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span>Parâmetros da Peça Processual</span>
          </h3>

          <form onSubmit={handleGenerate} className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-zinc-300 mb-1">Área do Direito</label>
              <select
                value={area}
                onChange={(e) => setArea(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-blue-500 focus:outline-none"
              >
                <option value="Cível">Direito Cível / Contratos</option>
                <option value="Trabalhista">Direito Trabalhista</option>
                <option value="Tributário">Direito Tributário</option>
                <option value="Penal">Direito Penal</option>
                <option value="Família">Direito de Família</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-zinc-300 mb-1">Tipo de Peça Processual</label>
              <select
                value={tipoPeca}
                onChange={(e) => setTipoPeca(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-blue-500 focus:outline-none"
              >
                <option value="Petição Inicial">Petição Inicial com Tutela</option>
                <option value="Contestação">Contestação com Reconvenção</option>
                <option value="Agravo de Instrumento">Agravo de Instrumento com Efeito Suspensivo</option>
                <option value="Mandado de Segurança">Mandado de Segurança Coletivo</option>
                <option value="Habeas Corpus">Habeas Corpus de Urgência</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-zinc-300 mb-1">Autor / Requerente</label>
              <input
                type="text"
                value={autor}
                onChange={(e) => setAutor(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-medium text-zinc-300 mb-1">Réu / Requerido</label>
              <input
                type="text"
                value={reu}
                onChange={(e) => setReu(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block font-medium text-zinc-300 mb-1">Resumo dos Fatos</label>
              <textarea
                rows={3}
                value={fatos}
                onChange={(e) => setFatos(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-blue-500 focus:outline-none resize-none"
              />
            </div>

            <div>
              <label className="block font-medium text-zinc-300 mb-1">Síntese dos Pedidos</label>
              <textarea
                rows={2}
                value={pedidos}
                onChange={(e) => setPedidos(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:border-blue-500 focus:outline-none resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={isGenerating}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-950 transition-colors flex items-center justify-center space-x-2"
            >
              {isGenerating ? (
                <>
                  <RefreshCcw className="w-4 h-4 animate-spin" />
                  <span>Redigindo Peça via AI...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Gerar Minuta de Petição</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Live Preview Box */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <FileText className="w-4 h-4 text-emerald-400" />
              <span>Minuta Gerada (Preview em Tempo Real)</span>
            </h3>
            {generatedDraft && (
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleCopy}
                  className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded-lg transition-colors flex items-center space-x-1"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? "Copiado!" : "Copiar Texto"}</span>
                </button>
                <button
                  onClick={() => alert("Baixando arquivo .docx formatado segundo ABNT e diretrizes de processo eletrônico.")}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-colors flex items-center space-x-1"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Exportar Word/PDF</span>
                </button>
              </div>
            )}
          </div>

          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 flex-1 min-h-[400px] overflow-y-auto font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap selection:bg-blue-600 selection:text-white">
            {generatedDraft ? (
              generatedDraft
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center text-zinc-500 space-y-2 py-20">
                <Scale className="w-12 h-12 text-zinc-700" />
                <p className="text-xs font-medium text-zinc-400">Nenhuma minuta gerada ainda.</p>
                <p className="text-[11px] text-zinc-600 max-w-xs">
                  Preencha os parâmetros ao lado e clique em "Gerar Minuta de Petição" para criar sua peça jurídica.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
