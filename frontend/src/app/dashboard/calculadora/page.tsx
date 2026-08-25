"use client";

import React, { useState } from "react";
import {
  Calculator,
  DollarSign,
  Calendar,
  Percent,
  FileSpreadsheet,
  Download,
  RefreshCw,
  Scale,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Info
} from "lucide-react";

interface MonthlyBreakdown {
  month_year: string;
  index_factor: number;
  updated_principal: number;
  interest_amount: number;
  subtotal: number;
}

interface CalculationResult {
  initial_value: number;
  index_used: string;
  monetary_correction_total: number;
  updated_principal: number;
  accumulated_interest_total: number;
  fine_art_523_amount: number;
  attorney_fees_amount: number;
  grand_total: number;
  start_date: string;
  end_date: string;
  total_months: number;
  breakdown: MonthlyBreakdown[];
}

export default function JudicialCalculatorPage() {
  const [initialValue, setInitialValue] = useState<number>(10000.0);
  const [startDate, setStartDate] = useState<string>("2025-01-01");
  const [endDate, setEndDate] = useState<string>("2026-08-01");
  const [indexType, setIndexType] = useState<string>("IPCA-E");
  const [interestMonthly, setInterestMonthly] = useState<number>(1.0);
  const [includeFineArt523, setIncludeFineArt523] = useState<boolean>(true);
  const [attorneyFeePct, setAttorneyFeePct] = useState<number>(10.0);

  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<CalculationResult | null>(null);

  const handleCalculate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch("/api/v1/calculadora/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          initial_value: Number(initialValue),
          start_date: startDate,
          end_date: endDate,
          index_type: indexType,
          interest_rate_monthly: Number(interestMonthly),
          include_fine_art_523: includeFineArt523,
          attorney_fee_percentage: Number(attorneyFeePct)
        })
      });

      if (res.ok) {
        const data = await res.json();
        setResult(data);
      } else {
        throw new Error();
      }
    } catch {
      // Fallback calculation for offline / local preview
      const dtStart = new Date(startDate);
      const dtEnd = new Date(endDate);
      const months = Math.max(1, (dtEnd.getFullYear() - dtStart.getFullYear()) * 12 + (dtEnd.getMonth() - dtStart.getMonth()));

      const indexFactors: Record<string, number> = { "IPCA-E": 1.0042, INPC: 1.0038, TJSP: 1.0045, SELIC: 1.0075 };
      const factor = indexFactors[indexType] || 1.0042;
      const totalFactor = Math.pow(factor, months);

      const updatedPrinc = initialValue * totalFactor;
      const monCorr = updatedPrinc - initialValue;
      const accInterest = updatedPrinc * ((interestMonthly / 100) * months);
      const subtotal = updatedPrinc + accInterest;
      const fine = includeFineArt523 ? subtotal * 0.1 : 0;
      const attFees = subtotal * (attorneyFeePct / 100);
      const grandTotal = subtotal + fine + attFees;

      const breakdownSample: MonthlyBreakdown[] = Array.from({ length: Math.min(months, 6) }).map((_, i) => ({
        month_year: `Mês ${i + 1}`,
        index_factor: Number(factor.toFixed(6)),
        updated_principal: Number((initialValue * Math.pow(factor, i + 1)).toFixed(2)),
        interest_amount: Number(((initialValue * Math.pow(factor, i + 1)) * (interestMonthly / 100) * (i + 1)).toFixed(2)),
        subtotal: Number(((initialValue * Math.pow(factor, i + 1)) * (1 + (interestMonthly / 100) * (i + 1))).toFixed(2))
      }));

      setResult({
        initial_value: initialValue,
        index_used: indexType,
        monetary_correction_total: Number(monCorr.toFixed(2)),
        updated_principal: Number(updatedPrinc.toFixed(2)),
        accumulated_interest_total: Number(accInterest.toFixed(2)),
        fine_art_523_amount: Number(fine.toFixed(2)),
        attorney_fees_amount: Number(attFees.toFixed(2)),
        grand_total: Number(grandTotal.toFixed(2)),
        start_date: startDate,
        end_date: endDate,
        total_months: months,
        breakdown: breakdownSample
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 text-zinc-100 font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-zinc-800 pb-6">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-blue-400">
            <Scale className="w-4 h-4" />
            <span>Módulo de Engenharia Jurídica - Módulo 8</span>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-zinc-100 mt-1">
            Calculadora Judicial de Liquidação & Atualização Monetária
          </h1>
          <p className="text-xs text-zinc-400 max-w-2xl mt-1">
            Cálculo de débitos judiciais conforme tabelas do TJSP, IPCA-E, INPC e SELIC, com aplicação de juros moratórios, multa do Art. 523 CPC e honorários sucumbenciais.
          </p>
        </div>

        <button
          onClick={() => alert("Gerando PDF da Memória de Cálculo...")}
          disabled={!result}
          className="px-4 py-2.5 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 disabled:opacity-50 text-xs font-semibold rounded-xl transition-all flex items-center space-x-2 shadow"
        >
          <Download className="w-4 h-4 text-blue-400" />
          <span>Exportar Memória de Cálculo (PDF)</span>
        </button>
      </div>

      {/* Main Grid: Form + Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Form Column */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-3xl p-6 space-y-6 shadow-2xl">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-4">
            <Calculator className="w-5 h-5 text-blue-400" />
            <h2 className="text-sm font-bold text-zinc-100">Parâmetros do Débito Judicial</h2>
          </div>

          <form onSubmit={handleCalculate} className="space-y-4 text-xs">
            <div className="space-y-1">
              <label className="text-zinc-400 font-medium">Valor Histórico do Débito (R$)</label>
              <div className="relative">
                <DollarSign className="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" />
                <input
                  type="number"
                  step="0.01"
                  value={initialValue}
                  onChange={(e) => setInitialValue(parseFloat(e.target.value) || 0)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-4 py-2.5 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-zinc-400 font-medium">Data Inicial (Termo a quo)</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
              <div className="space-y-1">
                <label className="text-zinc-400 font-medium">Data Final (Termo ad quem)</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-zinc-400 font-medium">Índice Monetário</label>
                <select
                  value={indexType}
                  onChange={(e) => setIndexType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                >
                  <option value="IPCA-E">IPCA-E (IBGE)</option>
                  <option value="INPC">INPC (IBGE)</option>
                  <option value="TJSP">Tabela Prática TJSP</option>
                  <option value="SELIC">Taxa SELIC</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-zinc-400 font-medium">Juros de Mora (% a.m.)</label>
                <input
                  type="number"
                  step="0.1"
                  value={interestMonthly}
                  onChange={(e) => setInterestMonthly(parseFloat(e.target.value) || 0)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-zinc-400 font-medium">Honorários (%)</label>
                <input
                  type="number"
                  step="1"
                  value={attorneyFeePct}
                  onChange={(e) => setAttorneyFeePct(parseFloat(e.target.value) || 0)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="flex items-center pt-5">
                <label className="flex items-center space-x-2 cursor-pointer text-zinc-300">
                  <input
                    type="checkbox"
                    checked={includeFineArt523}
                    onChange={(e) => setIncludeFineArt523(e.target.checked)}
                    className="w-4 h-4 rounded bg-zinc-950 border-zinc-800 text-blue-600 focus:ring-0"
                  />
                  <span className="text-[11px]">Multa 10% Art. 523 CPC</span>
                </label>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold rounded-2xl transition-all shadow-lg shadow-blue-950 flex items-center justify-center space-x-2 pt-3"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin text-white" />
              ) : (
                <>
                  <Calculator className="w-4 h-4" />
                  <span>Calcular Liquidação</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Results Column */}
        <div className="lg:col-span-7 space-y-6">
          {result ? (
            <div className="space-y-6 animate-fadeIn">
              {/* Grand Total Cards */}
              <div className="bg-gradient-to-br from-blue-950/80 via-zinc-900 to-indigo-950/60 border border-blue-800/60 rounded-3xl p-6 shadow-2xl space-y-4">
                <div className="flex justify-between items-center border-b border-blue-900/40 pb-4">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-blue-400 font-bold">
                      Resultado Final Atualizado
                    </span>
                    <h3 className="text-2xl font-black text-white font-mono mt-0.5">
                      R$ {result.grand_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </h3>
                  </div>

                  <span className="px-3 py-1 bg-blue-900/60 border border-blue-700/60 text-blue-200 text-xs font-mono rounded-full font-bold">
                    {result.total_months} Meses Corridos
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-2xl">
                    <p className="text-[10px] text-zinc-500 font-mono">Correção ({result.index_used})</p>
                    <p className="font-bold text-emerald-400 font-mono mt-1">
                      + R$ {result.monetary_correction_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </p>
                  </div>

                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-2xl">
                    <p className="text-[10px] text-zinc-500 font-mono">Juros Acumulados</p>
                    <p className="font-bold text-indigo-400 font-mono mt-1">
                      + R$ {result.accumulated_interest_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </p>
                  </div>

                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-2xl">
                    <p className="text-[10px] text-zinc-500 font-mono">Multa Art. 523 CPC</p>
                    <p className="font-bold text-amber-400 font-mono mt-1">
                      + R$ {result.fine_art_523_amount.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </p>
                  </div>

                  <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-2xl">
                    <p className="text-[10px] text-zinc-500 font-mono">Honorários</p>
                    <p className="font-bold text-purple-400 font-mono mt-1">
                      + R$ {result.attorney_fees_amount.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </p>
                  </div>
                </div>
              </div>

              {/* Monthly Breakdown Table */}
              <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-6 space-y-4 shadow-xl">
                <div className="flex justify-between items-center border-b border-zinc-800 pb-3">
                  <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-wider font-mono">
                    Memória Amostral de Cálculo Mês a Mês
                  </h4>
                  <span className="text-[10px] text-zinc-500 font-mono">Resumo dos primeiros meses</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-500">
                        <th className="pb-2">Período</th>
                        <th className="pb-2">Fator Índ.</th>
                        <th className="pb-2">Principal Corrigido</th>
                        <th className="pb-2">Juros</th>
                        <th className="pb-2 text-right">Subtotal</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                      {result.breakdown.map((row, idx) => (
                        <tr key={idx} className="hover:bg-zinc-950/50">
                          <td className="py-2.5 font-bold text-zinc-200">{row.month_year}</td>
                          <td className="py-2.5 text-zinc-400">{row.index_factor}</td>
                          <td className="py-2.5">R$ {row.updated_principal.toFixed(2)}</td>
                          <td className="py-2.5 text-indigo-400">R$ {row.interest_amount.toFixed(2)}</td>
                          <td className="py-2.5 text-right font-bold text-emerald-400">
                            R$ {row.subtotal.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-zinc-900 border border-zinc-800 rounded-3xl p-12 text-center space-y-4 shadow-xl">
              <FileSpreadsheet className="w-12 h-12 text-zinc-700 mx-auto" />
              <div className="space-y-1">
                <h3 className="text-base font-bold text-zinc-300">Pronto para Calcular</h3>
                <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                  Preencha os valores e datas à esquerda para gerar a memória completa de liquidação de sentença.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
