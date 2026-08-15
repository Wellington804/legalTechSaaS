"use client";

import React, { useState } from "react";
import {
  DollarSign,
  QrCode,
  Copy,
  Check,
  Clock,
  Plus,
  ArrowUpRight,
  ShieldCheck,
  FileCheck,
  Download
} from "lucide-react";

export default function FinancialPage() {
  const [clientName, setClientName] = useState("Empresa Alimenta Distribuidora Ltda.");
  const [amount, setAmount] = useState("4500.00");
  const [description, setDescription] = useState("Honorários Pro Labore - Ação Tributária");
  const [copiedPayload, setCopiedPayload] = useState(false);

  const pixPayload = "00020126580014BR.GOV.BCB.PIX0136contato@rossiadvocacia.com.br5204000053039865404500.005802BR5925ROSSI E ASSOCIADOS ADV6009SAO PAULO62070503***6304E2CA";

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono uppercase tracking-wider mb-1">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>Módulo 7: Gestão Financeira & Faturamento com Pix</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Timesheet, Honorários & Emissão de Cobrança Pix
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
            Gestão de faturamento de honorários, controle de horas trabalhadas e gerador instantâneo de Payload Pix Copia e Cola.
          </p>
        </div>

        <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-xs flex items-center space-x-2 shadow-lg shadow-emerald-950">
          <Plus className="w-4 h-4" />
          <span>Nova Cobrança de Honorários</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN: PIX GENERATOR FORM */}
        <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 text-xs">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
            <QrCode className="w-4 h-4 text-emerald-400" />
            <span>Gerador de Cobrança Pix Instantânea</span>
          </h3>

          <div className="space-y-3">
            <div>
              <label className="block text-zinc-400 mb-1">Cliente / Razão Social</label>
              <input
                type="text"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-zinc-400 mb-1">Valor dos Honorários (R$)</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 font-mono focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-zinc-400 mb-1">Descrição dos Serviços</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-zinc-200 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="pt-2">
              <button className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl text-xs flex items-center justify-center space-x-2 shadow-md">
                <QrCode className="w-4 h-4" />
                <span>Gerar Payload Pix Autêntico</span>
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: PIX PAYLOAD DISPLAY */}
        <div className="lg:col-span-7 bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Payload Pix Gerado com Sucesso</span>
            </h3>

            <button
              onClick={() => {
                navigator.clipboard.writeText(pixPayload);
                setCopiedPayload(true);
                setTimeout(() => setCopiedPayload(false), 2000);
              }}
              className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg flex items-center space-x-1"
            >
              {copiedPayload ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copiedPayload ? "Copiado!" : "Copiar Pix"}</span>
            </button>
          </div>

          <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-6 p-4 bg-zinc-950 border border-zinc-800 rounded-xl">
            <div className="w-36 h-36 bg-white p-2 rounded-xl flex items-center justify-center shrink-0">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(pixPayload)}`}
                alt="QR Code Pix"
                className="w-full h-full object-contain"
              />
            </div>

            <div className="space-y-2 text-xs text-zinc-300">
              <p className="font-bold text-zinc-100 text-sm">{clientName}</p>
              <p className="font-mono text-emerald-400 text-lg font-extrabold">R$ {parseFloat(amount || "0").toFixed(2)}</p>
              <p className="text-[11px] text-zinc-400">{description}</p>
              <div className="p-2 bg-zinc-900 border border-zinc-800 rounded font-mono text-[10px] text-zinc-400 break-all">
                {pixPayload}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
