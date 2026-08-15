"use client";

import React from "react";
import { CheckSquare, ShieldCheck, Filter, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useOabStore } from "@/store/useOabStore";
import { ChecklistItemCard } from "@/components/oab/checklist-item";

export default function ChecklistPage() {
  const { checklist, seccional, setSeccional } = useOabStore();

  const seccionais = ["OAB/SP", "OAB/RJ", "OAB/AL", "OAB/DF", "OAB/MG", "OAB/PR"];

  const completedCount = checklist.filter((item) => item.is_completed).length;
  const progressPct = Math.round((completedCount / checklist.length) * 100);

  return (
    <div className="space-y-6">
      {/* Top Header Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/oab-hub"
          className="text-xs font-semibold text-zinc-400 hover:text-zinc-200 flex items-center space-x-1"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Voltar ao Hub OAB</span>
        </Link>
        <div className="flex items-center space-x-2">
          <span className="text-xs text-zinc-400">Seccional de Inscrição:</span>
          <select
            value={seccional}
            onChange={(e) => setSeccional(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 text-xs text-zinc-200 font-semibold rounded-lg px-3 py-1.5 focus:outline-none focus:border-blue-500"
          >
            {seccionais.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Progress Bar Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="text-lg font-bold text-zinc-100 flex items-center space-x-2">
              <CheckSquare className="w-5 h-5 text-blue-500" />
              <span>Checklist de Documentos Obrigatórios - {seccional}</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              8 itens exigidos pelo Provimento OAB para deferimento da Inscrição Originária.
            </p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-extrabold text-blue-400 font-mono">{progressPct}%</span>
            <span className="text-xs text-zinc-400 block">{completedCount} de {checklist.length} concluídos</span>
          </div>
        </div>

        {/* Progress Bar Track */}
        <div className="w-full bg-zinc-950 h-3 rounded-full overflow-hidden p-0.5 border border-zinc-800">
          <div
            className="bg-gradient-to-r from-blue-600 to-emerald-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Checklist Grid */}
      <div className="space-y-3">
        {checklist.map((item) => (
          <ChecklistItemCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
