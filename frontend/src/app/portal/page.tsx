"use client";

import React, { useState } from "react";
import { ShieldCheck, Search, FileText, ArrowRight, Bot, Lock, CheckCircle2, Scale } from "lucide-react";

export default function ClientPortalPage() {
  const [cpfToken, setCpfToken] = useState("");
  const [searched, setSearched] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!cpfToken.trim()) return;
    setSearched(true);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-between selection:bg-blue-600 selection:text-white">
      {/* Client Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/60 p-6 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg">
            R
          </div>
          <div>
            <h1 className="text-sm font-bold text-zinc-100">Rossi & Associados Advocacia</h1>
            <p className="text-[10px] text-zinc-400 font-mono">Portal do Cliente - Acompanhamento Transparente</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-800/50 px-3 py-1.5 rounded-full font-mono">
          <ShieldCheck className="w-4 h-4" />
          <span>Acesso Seguro SSL 256-bit</span>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-6 space-y-8 my-8">
        {/* Search Hero */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 text-center space-y-4">
          <div className="inline-flex p-3 bg-blue-950 border border-blue-800 rounded-2xl text-blue-400 mb-2">
            <Scale className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Consulte o Andamento do seu Processo sem "Juridiquês"
          </h2>
          <p className="text-xs text-zinc-400 max-w-lg mx-auto leading-relaxed">
            Digite seu CPF ou o Token de Acesso fornecido pelo seu advogado para ver atualizações em linguagem simples e clara.
          </p>

          <form onSubmit={handleSearch} className="max-w-md mx-auto flex items-center gap-2 pt-2">
            <div className="relative flex-1">
              <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-3" />
              <input
                type="text"
                placeholder="Digite seu CPF (ex: 123.456.789-00)"
                value={cpfToken}
                onChange={(e) => setCpfToken(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
              />
            </div>
            <button
              type="submit"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl transition-colors shadow-lg shadow-blue-950 flex items-center space-x-1"
            >
              <span>Consultar</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Process Details Result Simulation */}
        {searched && (
          <div className="space-y-4 animate-fadeIn">
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
              <div className="flex justify-between items-start border-b border-zinc-800 pb-4">
                <div>
                  <span className="px-2.5 py-1 bg-emerald-950 border border-emerald-800 text-emerald-400 text-[10px] font-mono rounded-full">
                    Processo Ativo em Andamento
                  </span>
                  <h3 className="text-lg font-bold text-zinc-100 mt-2">
                    Ação de Restituição Tributária e Ajuste Fiscal
                  </h3>
                  <p className="text-xs text-zinc-400 font-mono">Nº 1048923-44.2026.8.26.0100</p>
                </div>
                <div className="text-right text-xs">
                  <p className="text-zinc-500">Última Atualização</p>
                  <p className="font-semibold text-zinc-300">Hoje às 08:45</p>
                </div>
              </div>

              {/* AI Juridiquês Translator Box */}
              <div className="bg-gradient-to-r from-blue-950/50 to-zinc-950 border border-blue-800/40 rounded-xl p-4 space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-blue-400">
                  <Bot className="w-4 h-4 text-blue-400" />
                  <span>Tradução Simplificada por Inteligência Artificial</span>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  "O Juiz analisou a nossa solicitação e pediu para a parte contrária apresentar a resposta no prazo de 15 dias. Todos os seus documentos estão corretos e nosso escritório já realizou a defesa."
                </p>
              </div>

              {/* Timeline */}
              <div className="pt-4 space-y-3">
                <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">Histórico Recente</h4>
                <div className="space-y-3 text-xs pl-4 border-l-2 border-zinc-800">
                  <div className="relative">
                    <div className="w-2.5 h-2.5 bg-blue-500 rounded-full absolute -left-[21px] top-1" />
                    <p className="font-semibold text-zinc-200">Decisão Interlocutória Deferida</p>
                    <p className="text-[11px] text-zinc-400">Juiz concedeu a tutela de urgência antecipada.</p>
                  </div>
                  <div className="relative">
                    <div className="w-2.5 h-2.5 bg-zinc-700 rounded-full absolute -left-[21px] top-1" />
                    <p className="font-semibold text-zinc-400">Petição Inicial Distribuída</p>
                    <p className="text-[11px] text-zinc-500">Ajuizamento efetuado na 4ª Vara Cível SP.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Client Footer */}
      <footer className="border-t border-zinc-800 bg-zinc-900/40 p-4 text-center text-xs text-zinc-500">
        © 2026 Rossi & Associados Advocacia. Powered by LexFlow Enterprise LegalTech (Multi-Tenant).
      </footer>
    </div>
  );
}
