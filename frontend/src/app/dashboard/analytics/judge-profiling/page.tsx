"use client";

import React, { useState } from "react";
import {
  Scale,
  Search,
  CheckCircle2,
  TrendingUp,
  Clock,
  ShieldCheck,
  AlertTriangle,
  FileText,
  PieChart
} from "lucide-react";

export default function JudgeProfilingPage() {
  const [judgeQuery, setJudgeQuery] = useState("Dr. Marcos Aurelio Santos");
  const [activeProfile, setActiveProfile] = useState({
    name: "Dr. Marcos Aurelio Santos",
    court: "Tribunal de Justiça de SP (TJSP)",
    chamber: "8ª Câmara de Direito Privado",
    grantRate: 76.4,
    avgDays: 38,
    reversalRate: 14.8,
    decisionsCount: 1420
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono uppercase tracking-wider mb-1">
            <Scale className="w-4 h-4 text-blue-400" />
            <span>Módulo 4: Legal Tracker & Jurimetria Decisória</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Perfilamento Decisório de Magistrados (Judge Profiling)
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Análise preditiva de decisões, taxa de deferimento de tutelas de urgência e tempo médio de julgamento por magistrado.
          </p>
        </div>

        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-3" />
          <input
            type="text"
            value={judgeQuery}
            onChange={(e) => setJudgeQuery(e.target.value)}
            placeholder="Buscar nome do magistrado ou vara..."
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-3 py-2 text-zinc-200 text-xs focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Taxa de Deferimento Tutelas</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-extrabold text-emerald-400 font-mono">{activeProfile.grantRate}%</p>
          <p className="text-[10px] text-zinc-500">Alta propensão a conceder liminares</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Tempo Médio Sentença</span>
            <Clock className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-2xl font-extrabold text-blue-400 font-mono">{activeProfile.avgDays} Dias</p>
          <p className="text-[10px] text-zinc-500">30% mais célere que a média estadual</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Taxa Reforma em Recurso</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-extrabold text-amber-400 font-mono">{activeProfile.reversalRate}%</p>
          <p className="text-[10px] text-zinc-500">Decisões mantidas no Tribunal</p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Acervo Analisado</span>
            <FileText className="w-4 h-4 text-purple-400" />
          </div>
          <p className="text-2xl font-extrabold text-purple-400 font-mono">{activeProfile.decisionsCount}</p>
          <p className="text-[10px] text-zinc-500">Acórdãos e decisões analisadas</p>
        </div>
      </div>

      {/* Profile Details Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Recomendações Estratégicas de Atuação via IA</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1.5">
            <h4 className="font-bold text-zinc-200">1. Fundamentação de Urgência</h4>
            <p className="text-zinc-400 leading-relaxed">
              O magistrado exige comprovação de perigo de dano irreparável respaldado em provas documentais pré-constituídas.
            </p>
          </div>

          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1.5">
            <h4 className="font-bold text-zinc-200">2. Jurisprudência Preferencial</h4>
            <p className="text-zinc-400 leading-relaxed">
              Alta receptividade a precedentes firmados pela 8ª Câmara de Direito Privado e Súmulas do STJ.
            </p>
          </div>

          <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1.5">
            <h4 className="font-bold text-zinc-200">3. Valor de Alçada para Danos Morais</h4>
            <p className="text-zinc-400 leading-relaxed">
              Média de arbitramento de Danos Morais entre R$ 10.000,00 e R$ 25.000,00 para casos de negativação indevida.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
