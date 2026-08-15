"use client";

import React, { useState } from "react";
import { Calculator, Percent, Sparkles, MapPin, Grid, QrCode, ChevronDown, Check } from "lucide-react";
import { OAB_SECCIONAIS, useOabStore } from "@/store/useOabStore";
import { formatCurrency } from "@/lib/utils";
import { StateSelectorModal } from "./state-selector-modal";
import { PixPaymentModal } from "./pix-payment-modal";

export function FeeCalculator() {
  const { feeState, setFeeState } = useOabStore();
  const [isStateModalOpen, setIsStateModalOpen] = useState(false);
  const [isPixModalOpen, setIsPixModalOpen] = useState(false);

  // Principais seccionais atalho rápido (7 estados + 1 botão gatilho = 8 itens perfeitos em grid de 4 colunas)
  const quickSeccionais = ["OAB/SP", "OAB/RJ", "OAB/DF", "OAB/MG", "OAB/PR", "OAB/RS", "OAB/BA"];
  
  const meses = [
    { value: 1, label: "Janeiro" },
    { value: 2, label: "Fevereiro" },
    { value: 3, label: "Março" },
    { value: 4, label: "Abril" },
    { value: 5, label: "Maio" },
    { value: 6, label: "Junho" },
    { value: 7, label: "Julho" },
    { value: 8, label: "Agosto" },
    { value: 9, label: "Setembro" },
    { value: 10, label: "Outubro" },
    { value: 11, label: "Novembro" },
    { value: 12, label: "Dezembro" },
  ];

  // Obter metadados da Seccional ativa
  const currentSeccional = OAB_SECCIONAIS.find((s) => s.code === feeState.seccional) || OAB_SECCIONAIS[24]; // SP por padrão

  // Fee calculation logic dinâmico por UF
  const baseAnuidade = currentSeccional.baseAnuidade;
  const taxaRequerimento = currentSeccional.taxaRequerimento;
  const taxaCartao = currentSeccional.taxaCartao;

  const mesesRestantes = Math.max(1, 13 - feeState.monthOfRegistration);
  const anuidadeProporcional = (baseAnuidade / 12) * mesesRestantes;

  const descontoJovem = feeState.isJovemAdvogado ? anuidadeProporcional * 0.50 : 0;
  const descontoSua = feeState.registerSua ? anuidadeProporcional * 0.25 : 0;

  const anuidadeFinal = Math.max(0, anuidadeProporcional - descontoJovem - descontoSua);
  const totalEstimado = taxaRequerimento + taxaCartao + anuidadeFinal;

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        {/* Controls Form Card */}
        <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6 shadow-xl flex flex-col justify-between">
          <div className="space-y-6">
            {/* Section Title */}
            <div className="pb-4 border-b border-zinc-800/80">
              <h3 className="text-sm font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
                <Calculator className="w-4 h-4 text-blue-500" />
                <span>Parâmetros de Inscrição na Seccional</span>
              </h3>
              <p className="text-xs text-zinc-400 mt-1">
                Simule o custo real da anuidade proporcional e taxas da Ordem dos Advogados do Brasil em qualquer um dos 27 estados.
              </p>
            </div>

            {/* Seccional selector with Floating Box Trigger */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-zinc-200">Seccional da OAB</label>
                <button
                  onClick={() => setIsStateModalOpen(true)}
                  className="text-[11px] text-blue-400 hover:text-blue-300 font-semibold flex items-center space-x-1.5 bg-blue-950/60 border border-blue-800/50 px-3 py-1.5 rounded-xl transition-all hover:border-blue-600 hover:bg-blue-900/40 shadow-sm"
                >
                  <Grid className="w-3.5 h-3.5" />
                  <span>Ver todas as 27 UFs (Caixa Flutuante)</span>
                </button>
              </div>

              {/* Grid Responsiva e Simétrica de Botões de UF */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {quickSeccionais.map((sec) => (
                  <button
                    key={sec}
                    onClick={() => setFeeState({ seccional: sec })}
                    className={`py-2.5 px-3 text-xs font-semibold rounded-xl border transition-all duration-150 flex items-center justify-center space-x-1 ${
                      feeState.seccional === sec
                        ? "bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-950/60 ring-1 ring-blue-400/40"
                        : "bg-zinc-950/80 border-zinc-800 text-zinc-300 hover:bg-zinc-800/80 hover:border-zinc-700 hover:text-white"
                    }`}
                  >
                    <span>{sec}</span>
                  </button>
                ))}

                {/* Botão de Destaque se a UF ativa for de fora dos atalhos rápidos */}
                {!quickSeccionais.includes(feeState.seccional) ? (
                  <button
                    onClick={() => setIsStateModalOpen(true)}
                    className="py-2.5 px-3 text-xs font-bold rounded-xl border bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-950/60 ring-1 ring-blue-400/40 flex items-center justify-center"
                  >
                    <span>{feeState.seccional}</span>
                  </button>
                ) : (
                  /* Botão Gatilho Adicional para completar o grid de 8 itens */
                  <button
                    onClick={() => setIsStateModalOpen(true)}
                    className="py-2.5 px-3 text-xs font-semibold rounded-xl border border-dashed border-zinc-700 bg-zinc-950/60 text-blue-400 hover:text-blue-300 hover:bg-zinc-800/80 hover:border-blue-500 flex items-center justify-center space-x-1.5 transition-all"
                  >
                    <MapPin className="w-3.5 h-3.5" />
                    <span>+ 20 UFs</span>
                  </button>
                )}
              </div>

              {/* Informação sobre a UF selecionada */}
              <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl px-3.5 py-2 flex items-center justify-between text-[11px] text-zinc-400">
                <span>Estado Ativo: <strong className="text-zinc-100 font-semibold">{currentSeccional.name} ({currentSeccional.uf})</strong></span>
                <span className="text-zinc-400 font-mono bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-md">Região {currentSeccional.region}</span>
              </div>
            </div>

            {/* Month selector */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-zinc-200 block">Mês de Entrada / Aprovação</label>
              <div className="relative">
                <select
                  value={feeState.monthOfRegistration}
                  onChange={(e) => setFeeState({ monthOfRegistration: Number(e.target.value) })}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 appearance-none cursor-pointer pr-10 transition-colors"
                >
                  {meses.map((m) => (
                    <option key={m.value} value={m.value} className="bg-zinc-900 text-zinc-200 py-1">
                      {m.label} ({13 - m.value} meses de anuidade em 2026)
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
              </div>
            </div>

            {/* Toggles de Descontos */}
            <div className="space-y-3 pt-1">
              <label className="flex items-center justify-between p-3.5 rounded-xl bg-zinc-950/80 border border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all group">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 group-hover:scale-105 transition-transform">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-zinc-200">Desconto do Jovem Advogado (50%)</p>
                    <p className="text-[11px] text-zinc-400 mt-0.5">Válido para os primeiros 5 anos de inscrição principal na OAB.</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={feeState.isJovemAdvogado}
                  onChange={(e) => setFeeState({ isJovemAdvogado: e.target.checked })}
                  className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-3.5 rounded-xl bg-zinc-950/80 border border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all group">
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 group-hover:scale-105 transition-transform">
                    <Percent className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-zinc-200">Inclusão de Sociedade Unipessoal (SUA - 25%)</p>
                    <p className="text-[11px] text-zinc-400 mt-0.5">Desconto cumulativo para registro simplificado de CNPJ de advocacia.</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={feeState.registerSua}
                  onChange={(e) => setFeeState({ registerSua: e.target.checked })}
                  className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
              </label>
            </div>
          </div>
        </div>

        {/* Summary Box Card */}
        <div className="bg-gradient-to-b from-blue-950/50 via-zinc-900 to-zinc-900 border border-blue-900/60 rounded-2xl p-6 flex flex-col justify-between shadow-2xl shadow-blue-950/30 min-h-[420px]">
          <div>
            <div className="pb-3 border-b border-blue-900/40">
              <span className="text-[10px] font-mono font-bold text-blue-400 uppercase tracking-widest block mb-1">
                Resumo Financeiro - {currentSeccional.code}
              </span>
              <h4 className="text-lg font-bold text-zinc-100">Investimento Inicial</h4>
            </div>

            <div className="space-y-3 mt-6 text-xs">
              <div className="flex justify-between text-zinc-400">
                <span>Taxa de Requerimento:</span>
                <span className="font-mono font-semibold text-zinc-200">{formatCurrency(taxaRequerimento)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Carteira Vermelha & Chip:</span>
                <span className="font-mono font-semibold text-zinc-200">{formatCurrency(taxaCartao)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Anuidade Bruta ({mesesRestantes} meses):</span>
                <span className="font-mono font-semibold text-zinc-200">{formatCurrency(anuidadeProporcional)}</span>
              </div>

              {feeState.isJovemAdvogado && (
                <div className="flex justify-between text-emerald-400 font-medium">
                  <span>Desconto Jovem Advogado (50%):</span>
                  <span className="font-mono font-bold">-{formatCurrency(descontoJovem)}</span>
                </div>
              )}

              {feeState.registerSua && (
                <div className="flex justify-between text-emerald-400 font-medium">
                  <span>Desconto Registro SUA (25%):</span>
                  <span className="font-mono font-bold">-{formatCurrency(descontoSua)}</span>
                </div>
              )}
            </div>
          </div>

          <div className="mt-8 pt-4 border-t border-zinc-800/80 space-y-4">
            <div className="flex justify-between items-baseline">
              <span className="text-xs font-bold text-zinc-300">Total a Pagar:</span>
              <span className="text-2xl font-black text-blue-400 font-mono tracking-tight">
                {formatCurrency(totalEstimado)}
              </span>
            </div>

            <button
              onClick={() => setIsPixModalOpen(true)}
              className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-blue-950/80 transition-all flex items-center justify-center space-x-2 group hover:scale-[1.01] active:scale-[0.99]"
            >
              <QrCode className="w-4 h-4" />
              <span>Gerar Boleto/Pix da Ordem</span>
            </button>
          </div>
        </div>
      </div>

      {/* Modals */}
      <StateSelectorModal
        isOpen={isStateModalOpen}
        onClose={() => setIsStateModalOpen(false)}
      />

      <PixPaymentModal
        isOpen={isPixModalOpen}
        onClose={() => setIsPixModalOpen(false)}
        totalCalculated={totalEstimado}
        taxaRequerimento={taxaRequerimento}
        taxaCartao={taxaCartao}
        anuidadeProporcional={anuidadeProporcional}
        descontoJovem={descontoJovem}
        descontoSua={descontoSua}
        mesesRestantes={mesesRestantes}
      />
    </>
  );
}


