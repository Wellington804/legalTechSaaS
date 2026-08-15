"use client";

import React, { useState } from "react";
import {
  Search,
  TrendingUp,
  Clock,
  Scale,
  Award,
  BarChart3,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Building2,
} from "lucide-react";

interface JudgeProfile {
  name: string;
  court: string;
  vara: string;
  favorabilityRate: number; // e.g. 78% favorable to employer / bank
  avgTimeDays: number;
  totalDecisionsAudited: number;
  reformRate: number; // % decision reversed in appeal
  recentPrecedent: string;
}

export default function TrackerPage() {
  const [selectedCourt, setSelectedCourt] = useState("TJSP - São Paulo");
  const [judgeSearch, setJudgeSearch] = useState("");

  const judges: JudgeProfile[] = [
    {
      name: "Dr. Roberto Alencar de Camargo",
      court: "TJSP",
      vara: "12ª Vara Cível Central",
      favorabilityRate: 76,
      avgTimeDays: 42,
      totalDecisionsAudited: 1240,
      reformRate: 12,
      recentPrecedent: "Defere liminares de reintegração de posse sem audiência prévia de conciliação.",
    },
    {
      name: "Dra. Maria Fernanda Vasconcelos",
      court: "TRT-2",
      vara: "45ª Vara do Trabalho de SP",
      favorabilityRate: 34,
      avgTimeDays: 28,
      totalDecisionsAudited: 890,
      reformRate: 24,
      recentPrecedent: "Reconhece vínculo empregatício em plataformas digitais com habitualidade mínima.",
    },
    {
      name: "Dr. Carlos Eduardo Prudente",
      court: "TRF-3",
      vara: "2ª Vara Federal Cível",
      favorabilityRate: 88,
      avgTimeDays: 65,
      totalDecisionsAudited: 2150,
      reformRate: 8,
      recentPrecedent: "Concede tutela antecedente para suspensão de exigibilidade de crédito tributário com garantia fidejussória.",
    },
  ];

  const filteredJudges = judges.filter(
    (j) =>
      j.name.toLowerCase().includes(judgeSearch.toLowerCase()) ||
      j.vara.toLowerCase().includes(judgeSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-purple-400 font-mono uppercase tracking-wider mb-2">
          <BarChart3 className="w-4 h-4 text-purple-400" />
          <span>Jurimetria Preditiva & Inteligência de Magistrados</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Legal Tracker & Analytics de Juízes
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Mapeamento preditivo de perfil decisório de magistrados, tempo médio de prolação de sentenças e taxa de reforma em grau recursal.
        </p>
      </div>

      {/* Search and Filters */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={judgeSearch}
            onChange={(e) => setJudgeSearch(e.target.value)}
            placeholder="Buscar por Nome do Juiz, Vara ou Tribunal..."
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <select
          value={selectedCourt}
          onChange={(e) => setSelectedCourt(e.target.value)}
          className="bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 w-full sm:w-auto"
        >
          <option value="TJSP - São Paulo">TJSP - São Paulo</option>
          <option value="TRT-2 - São Paulo">TRT-2 - São Paulo</option>
          <option value="TRF-3 - Federal">TRF-3 - Federal</option>
          <option value="STJ - Superior">STJ - Brasília</option>
        </select>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {filteredJudges.map((j) => (
          <div
            key={j.name}
            className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 hover:border-zinc-700 transition-all space-y-4 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="px-2.5 py-1 rounded-full bg-blue-950 border border-blue-800 text-blue-400 text-[10px] font-mono">
                  {j.court}
                </span>
                <span className="text-[11px] font-mono text-zinc-400">{j.totalDecisionsAudited} Decisões</span>
              </div>

              <h3 className="text-base font-bold text-zinc-100 mt-3">{j.name}</h3>
              <p className="text-xs text-zinc-400 mt-0.5 font-mono">{j.vara}</p>

              {/* Stats Box */}
              <div className="mt-4 grid grid-cols-3 gap-2 bg-zinc-950 p-3 rounded-lg border border-zinc-800 text-center">
                <div>
                  <span className="block text-[10px] text-zinc-500 uppercase font-mono">Procedência</span>
                  <span className="text-sm font-bold text-emerald-400 font-mono">{j.favorabilityRate}%</span>
                </div>
                <div>
                  <span className="block text-[10px] text-zinc-500 uppercase font-mono">Tempo Médio</span>
                  <span className="text-sm font-bold text-blue-400 font-mono">{j.avgTimeDays} dias</span>
                </div>
                <div>
                  <span className="block text-[10px] text-zinc-500 uppercase font-mono">Taxa Reforma</span>
                  <span className="text-sm font-bold text-amber-400 font-mono">{j.reformRate}%</span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-800/80">
                <p className="text-[11px] font-semibold text-zinc-300">Tese / Entendimento Predominante:</p>
                <p className="text-xs text-zinc-400 mt-1 leading-relaxed italic">"{j.recentPrecedent}"</p>
              </div>
            </div>

            <button
              onClick={() => alert(`Relatório Jurimétrico completo exportado para ${j.name}`)}
              className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center space-x-1.5"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400" />
              <span>Gerar Dossiê Jurimétrico</span>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
