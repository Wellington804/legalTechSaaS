"use client";

import React, { useState, useEffect } from "react";
import {
  FileCode2,
  FileText,
  Sparkles,
  Download,
  Copy,
  Check,
  RefreshCw,
  Search,
  Plus,
  Zap,
  CheckCircle2,
  Edit3
} from "lucide-react";

interface TemplateItem {
  id: string;
  title: string;
  category: string;
  description: string;
  placeholders: string[];
  content_template: string;
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateItem | null>(null);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [renderedContent, setRenderedContent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    // Fetch available templates
    fetch("/api/v1/templates/")
      .then((res) => res.json())
      .then((data) => {
        setTemplates(data);
        if (data.length > 0) {
          selectTemplate(data[0]);
        }
      })
      .catch(() => {
        // Fallback templates
        const fallbacks: TemplateItem[] = [
          {
            id: "tpl_procuracao",
            title: "Procuração Ad Judicia et Extra",
            category: "Procurações",
            description: "Outorga de poderes amplos para representação judicial em todas as instâncias.",
            placeholders: ["outorgante_nome", "outorgante_cpf", "outorgante_rg", "outorgante_endereco", "foro_cidade"],
            content_template: `PROCURAÇÃO AD JUDICIA ET EXTRA\n\nOUTORGANTE: {{outorgante_nome}}, brasileiro(a), portador(a) do CPF nº {{outorgante_cpf}} e RG nº {{outorgante_rg}}, residente em {{outorgante_endereco}}.\n\nOUTORGADOS: Rossi & Associados Advocacia, OAB/SP 45.890.\n\nPODERES: Concede poderes amplos da cláusula ad judicia et extra perante o Foro da Comarca de {{foro_cidade}}.\n\n{{foro_cidade}}, 24 de Agosto de 2026.`
          },
          {
            id: "tpl_honorarios",
            title: "Contrato de Honorários Quota Litis",
            category: "Contratos",
            description: "Contrato de honorários com cláusula de êxito e parcelamento.",
            placeholders: ["contratante_nome", "contratante_cpf", "percentual_exito", "valor_entrada", "foro_cidade"],
            content_template: `CONTRATO DE HONORÁRIOS ADVOCATÍCIOS\n\nCONTRATANTE: {{contratante_nome}}, CPF nº {{contratante_cpf}}.\nCONTRATADO: Rossi & Associados Advocacia.\n\nCLÁUSULA 1 - Entrada de R$ {{valor_entrada}} + {{percentual_exito}}% sobre o êxito final.\n\n{{foro_cidade}}, 24 de Agosto de 2026.`
          }
        ];
        setTemplates(fallbacks);
        selectTemplate(fallbacks[0]);
      });
  }, []);

  const selectTemplate = (tpl: TemplateItem) => {
    setSelectedTemplate(tpl);
    const initialVars: Record<string, string> = {};
    tpl.placeholders.forEach((p) => {
      initialVars[p] = "";
    });
    setVariables(initialVars);
    setRenderedContent(tpl.content_template);
  };

  const handleVariableChange = (key: string, value: string) => {
    const updated = { ...variables, [key]: value };
    setVariables(updated);

    if (selectedTemplate) {
      let content = selectedTemplate.content_template;
      Object.entries(updated).forEach(([k, v]) => {
        const placeholder = "{{" + k + "}}";
        content = content.replace(new RegExp(placeholder, "g"), v || `[${k}]`);
      });
      setRenderedContent(content);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(renderedContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 text-zinc-100 font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-zinc-800 pb-6">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-purple-400">
            <Zap className="w-4 h-4" />
            <span>Gerador Inteligente de Minutas - Módulo 6</span>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-zinc-100 mt-1">
            Modelos Automatizados & Contratos com IA
          </h1>
          <p className="text-xs text-zinc-400 max-w-2xl mt-1">
            Gere contratos, procurações e termos extrajudiciais em segundos preenchendo variáveis inteligentes ou importando dados direto do CRM.
          </p>
        </div>

        <button
          onClick={handleCopy}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl transition-all shadow flex items-center space-x-2"
        >
          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          <span>{copied ? "Copiado para o Transferidor!" : "Copiar Texto Final"}</span>
        </button>
      </div>

      {/* Main Grid: Template Selector + Fill Form + Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Template Selection list */}
        <div className="lg:col-span-4 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400 font-mono">
            Modelos de Minuta Disponíveis ({templates.length})
          </h2>

          <div className="space-y-3">
            {templates.map((tpl) => (
              <button
                key={tpl.id}
                onClick={() => selectTemplate(tpl)}
                className={`w-full p-4 rounded-2xl border text-left transition-all flex flex-col justify-between space-y-2 ${
                  selectedTemplate?.id === tpl.id
                    ? "bg-purple-950/40 border-purple-600/80 ring-1 ring-purple-500/50"
                    : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-200">{tpl.title}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 bg-zinc-950 text-purple-400 rounded-md border border-purple-800/40">
                    {tpl.category}
                  </span>
                </div>
                <p className="text-[11px] text-zinc-400 line-clamp-2 leading-relaxed">{tpl.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right Column: Fill Variables Form & Live Render Preview */}
        <div className="lg:col-span-8 space-y-6">
          {selectedTemplate && (
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Variable Inputs */}
              <div className="md:col-span-5 bg-zinc-900 border border-zinc-800 rounded-3xl p-5 space-y-4 shadow-xl">
                <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
                  <Edit3 className="w-4 h-4 text-purple-400" />
                  <h3 className="text-xs font-bold text-zinc-200">Preenchimento de Variáveis</h3>
                </div>

                <div className="space-y-3 text-xs">
                  {selectedTemplate.placeholders.map((ph) => (
                    <div key={ph} className="space-y-1">
                      <label className="text-zinc-400 font-mono text-[11px] capitalize">
                        {ph.replace(/_/g, " ")}
                      </label>
                      <input
                        type="text"
                        placeholder={`Digite ${ph}...`}
                        value={variables[ph] || ""}
                        onChange={(e) => handleVariableChange(ph, e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-200 focus:outline-none focus:border-purple-500 font-mono text-xs"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Rendered Live Preview */}
              <div className="md:col-span-7 bg-zinc-950 border border-zinc-800 rounded-3xl p-6 space-y-4 shadow-2xl flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-center border-b border-zinc-800 pb-3">
                    <span className="text-[10px] text-emerald-400 font-mono font-bold flex items-center space-x-1">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Pré-visualização em Tempo Real</span>
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono">Formatado para Impressão</span>
                  </div>

                  <pre className="mt-4 text-xs text-zinc-200 font-serif whitespace-pre-wrap leading-relaxed bg-zinc-900/60 p-4 rounded-2xl border border-zinc-800/80 min-h-[300px]">
                    {renderedContent}
                  </pre>
                </div>

                <div className="pt-4 border-t border-zinc-900 flex justify-between items-center text-xs">
                  <span className="text-zinc-500 text-[11px]">Substituições ativas: {selectedTemplate.placeholders.length}</span>
                  <button
                    onClick={() => alert("Gerando PDF oficial do contrato...")}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl transition-all shadow flex items-center space-x-1.5"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Baixar Minuta em PDF</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
