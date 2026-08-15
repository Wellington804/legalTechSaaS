"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Calculator, Sparkles } from "lucide-react";
import { FeeCalculator } from "@/components/oab/fee-calculator";

export default function CalculadoraPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/oab-hub"
          className="text-xs font-semibold text-zinc-400 hover:text-zinc-200 flex items-center space-x-1"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Voltar ao Hub OAB</span>
        </Link>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <h1 className="text-xl font-bold text-zinc-100 flex items-center space-x-2">
          <Calculator className="w-5 h-5 text-emerald-400" />
          <span>Calculadora & Painel de Anuidade Proporcional</span>
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-2xl">
          Mapeamento exato de taxas de requerimento, confecção de carteira e cartão criptográfico com o simulador de desconto do Jovem Advogado (primeiros 5 anos).
        </p>
      </div>

      <FeeCalculator />
    </div>
  );
}
