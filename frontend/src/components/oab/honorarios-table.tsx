"use client";

import React, { useState } from "react";
import {
  Scale,
  TrendingUp,
  RotateCcw,
  Edit3,
  Check,
  Copy,
  Plus,
  Grid,
  Sparkles,
  Info,
  Calendar,
} from "lucide-react";
import { OAB_SECCIONAIS, useOabStore } from "@/store/useOabStore";
import { formatCurrency } from "@/lib/utils";
import { StateSelectorModal } from "./state-selector-modal";

export function HonorariosTable() {
  const {
    feeState,
    honorariosList,
    selectedYear,
    reajustePercentual,
    setSelectedYear,
    setReajustePercentual,
    updateHonorario,
    resetHonorarios,
  } = useOabStore();

  const [isStateModalOpen, setIsStateModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [tempValor, setTempValor] = useState<string>("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const seccionalData =
    OAB_SECCIONAIS.find((s) => s.code === feeState.seccional) ||
    OAB_SECCIONAIS[24]; // SP default

  // Multiplicador regional baseado na base da anuidade em relação à média nacional (R$ 950)
  const regionalMultiplier = seccionalData.baseAnuidade / 950;

  // Multiplicador anual (referência 2026 = 1.0)
  const yearMultipliers: Record<number, number> = {
    2024: 0.91,
    2025: 0.95,
    2026: 1.0,
    2027: 1.06,
  };
  const currentYearMultiplier = yearMultipliers[selectedYear] || 1.0;

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const calculateFinalValue = (valorBase: number) => {
    const adjusted =
      valorBase *
      (1 + reajustePercentual / 100) *
      regionalMultiplier *
      currentYearMultiplier;
    return Math.round(adjusted / 10) * 10; // Arredonda para dezenas
  };

  const handleStartEdit = (id: string, currentValorBase: number) => {
    setEditingId(id);
    setTempValor(currentValorBase.toString());
  };

  const handleSaveEdit = (id: string) => {
    const num = parseFloat(tempValor);
    if (!isNaN(num) && num > 0) {
      updateHonorario(id, num);
      showToast("Valor ajustado com sucesso!");
    }
    setEditingId(null);
  };

  const handleCopyProposal = (servico: string, valorFinal: number, exito: string) => {
    const text = `PROPOSTA COMERCIAL DE HONORÁRIOS JURÍDICOS\nServiço: ${servico}\nSeccional Referência: ${seccionalData.code} (${seccionalData.name})\nAno: ${selectedYear}\nValor Mínimo Ético: ${formatCurrency(
      valorFinal
    )}\nPercentual de Êxito: ${exito}`;
    navigator.clipboard.writeText(text);
    setCopiedId(servico);
    showToast(`Proposta para "${servico}" copiada!`);
    setTimeout(() => setCopiedId(null), 2500);
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6 shadow-xl relative overflow-hidden">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="absolute top-4 right-4 z-20 bg-emerald-500 text-zinc-950 font-bold px-3.5 py-2 rounded-xl shadow-xl flex items-center space-x-2 text-xs animate-in slide-in-from-top duration-300">
          <Check className="w-4 h-4 stroke-[3]" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-zinc-800">
        <div>
          <div className="flex items-center space-x-2">
            <Scale className="w-5 h-5 text-blue-400" />
            <h3 className="text-base font-bold text-zinc-100">
              Tabela Ética Referencial de Honorários Mínimos
            </h3>
            <span className="text-xs font-mono font-bold text-blue-400 bg-blue-950/80 px-2.5 py-0.5 rounded-full border border-blue-800/50">
              {selectedYear}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Valores mínimos recomendados pela{" "}
            <strong className="text-zinc-200">{seccionalData.code} ({seccionalData.name})</strong> com cálculo de reajuste dinâmico.
          </p>
        </div>

        <button
          onClick={() => setIsStateModalOpen(true)}
          className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center space-x-2 bg-blue-950/50 border border-blue-800/60 px-3 py-2 rounded-xl transition-all hover:border-blue-600 self-start md:self-auto"
        >
          <Grid className="w-4 h-4" />
          <span>Trocar Seccional ({seccionalData.uf})</span>
        </button>
      </div>

      {/* Bar de Controles de Reajuste & Ano */}
      <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-center">
        {/* Seletor de Ano */}
        <div>
          <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5 flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5 text-zinc-500" />
            Ano da Tabela
          </label>
          <div className="flex bg-zinc-900 p-1 rounded-lg border border-zinc-800">
            {[2024, 2025, 2026, 2027].map((yr) => (
              <button
                key={yr}
                onClick={() => setSelectedYear(yr)}
                className={`flex-1 py-1 text-xs font-semibold rounded-md transition-all ${
                  selectedYear === yr
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {yr}
              </button>
            ))}
          </div>
        </div>

        {/* Reajuste Porcentual Automático */}
        <div>
          <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1.5 flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            Reajuste Automático (%)
          </label>
          <div className="flex items-center space-x-2">
            <input
              type="number"
              step="0.5"
              value={reajustePercentual}
              onChange={(e) => setReajustePercentual(parseFloat(e.target.value) || 0)}
              className="w-20 bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100 font-mono text-center focus:outline-none focus:border-blue-500"
              placeholder="0%"
            />
            <div className="flex space-x-1">
              {[0, 5, 10, 15].map((pct) => (
                <button
                  key={pct}
                  onClick={() => setReajustePercentual(pct)}
                  className={`px-2 py-1 text-[11px] font-mono rounded-lg border transition-all ${
                    reajustePercentual === pct
                      ? "bg-emerald-600 border-emerald-500 text-white font-bold"
                      : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  +{pct}%
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Indicador de Fator de Reajuste */}
        <div className="text-xs space-y-0.5">
          <span className="text-[11px] text-zinc-400 block font-semibold">Impacto nos Valores:</span>
          <div className="text-emerald-400 font-mono font-bold flex items-center space-x-1">
            <Sparkles className="w-3.5 h-3.5" />
            <span>
              {reajustePercentual >= 0 ? `+${reajustePercentual}%` : `${reajustePercentual}%`} acumulado
            </span>
          </div>
          <span className="text-[10px] text-zinc-500 block">
            Base Seccional {seccionalData.code}: {regionalMultiplier.toFixed(2)}x
          </span>
        </div>

        {/* Reset Button */}
        <div className="flex justify-end sm:justify-start lg:justify-end">
          <button
            onClick={() => {
              resetHonorarios();
              showToast("Tabela restaurada para os padrões OAB!");
            }}
            className="px-3 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Resetar Tabela</span>
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-zinc-800/80">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-zinc-950 border-b border-zinc-800 text-[11px] font-mono text-zinc-400 uppercase">
              <th className="py-3 px-4">Área de Atuação</th>
              <th className="py-3 px-4">Serviço Advocatício</th>
              <th className="py-3 px-4">Valor Mínimo Ético ({selectedYear})</th>
              <th className="py-3 px-4">Percentual de Êxito</th>
              <th className="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60 text-xs">
            {honorariosList.map((item) => {
              const valorFinal = calculateFinalValue(item.valorBase);
              const isEditing = editingId === item.id;
              const isCopied = copiedId === item.servico;

              return (
                <tr key={item.id} className="hover:bg-zinc-950/40 transition-colors group">
                  <td className="py-3 px-4 font-semibold text-zinc-200">{item.area}</td>
                  <td className="py-3 px-4 text-zinc-300">{item.servico}</td>
                  <td className="py-3 px-4 font-mono">
                    {isEditing ? (
                      <div className="flex items-center space-x-1.5">
                        <span className="text-zinc-400">R$</span>
                        <input
                          type="number"
                          value={tempValor}
                          onChange={(e) => setTempValor(e.target.value)}
                          className="w-24 bg-zinc-950 border border-blue-500 rounded px-2 py-1 text-xs text-white focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveEdit(item.id)}
                          className="p-1 bg-emerald-600 text-white rounded hover:bg-emerald-500"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <span className="text-blue-400 font-bold text-sm">
                        {formatCurrency(valorFinal)}
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-mono text-zinc-400">{item.exito}</td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end space-x-2">
                      <button
                        onClick={() => handleStartEdit(item.id, item.valorBase)}
                        className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors"
                        title="Editar valor base do serviço"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() =>
                          handleCopyProposal(item.servico, valorFinal, item.exito)
                        }
                        className={`p-1.5 rounded-lg transition-all flex items-center space-x-1 text-xs font-semibold ${
                          isCopied
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                        }`}
                        title="Copiar Proposta Comercial"
                      >
                        {isCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        <span className="hidden sm:inline">{isCopied ? "Copiado" : "Copiar Proposta"}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Info Banner */}
      <div className="flex items-center space-x-2 text-[11px] text-zinc-400 bg-zinc-950/60 p-3 rounded-xl border border-zinc-800/60">
        <Info className="w-4 h-4 text-blue-400 shrink-0" />
        <span>
          Os valores apresentados constituem o parâmetro ético referencial (Provimento OAB) atualizado para{" "}
          <strong className="text-zinc-200">{seccionalData.code}</strong>. Altere o percentual de reajuste ou clique em{" "}
          <Edit3 className="w-3 h-3 inline mx-0.5" /> para personalizar os preços para o seu escritório.
        </span>
      </div>

      {/* State Selector Modal */}
      <StateSelectorModal
        isOpen={isStateModalOpen}
        onClose={() => setIsStateModalOpen(false)}
      />
    </div>
  );
}
