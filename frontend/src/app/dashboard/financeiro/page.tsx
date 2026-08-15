"use client";

import React, { useState } from "react";
import {
  DollarSign,
  TrendingUp,
  CreditCard,
  Receipt,
  Plus,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileSpreadsheet,
  Building,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface Invoice {
  id: string;
  client: string;
  process: string;
  type: "SUCUMBENCIA" | "CONTRATUAL" | "PRO_LABORE";
  amount: number;
  dueDate: string;
  status: "PAID" | "PENDING" | "OVERDUE";
}

export default function FinanceiroPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([
    {
      id: "FAT-2026-001",
      client: "Banco Siderúrgico S/A",
      process: "Proc. 1004589-12.2024.8.26.0100",
      type: "SUCUMBENCIA",
      amount: 145000.0,
      dueDate: "15/08/2026",
      status: "PENDING",
    },
    {
      id: "FAT-2026-002",
      client: "TechCorp Participações Ltda",
      process: "Proc. 0001234-88.2025.8.26.0000",
      type: "CONTRATUAL",
      amount: 45000.0,
      dueDate: "05/08/2026",
      status: "PAID",
    },
    {
      id: "FAT-2026-003",
      client: "Construtora Silva & Filhos",
      process: "Proc. 1008899-33.2025.8.26.0100",
      type: "PRO_LABORE",
      amount: 18500.0,
      dueDate: "01/08/2026",
      status: "PAID",
    },
    {
      id: "FAT-2026-004",
      client: "Indústria Metalúrgica Ramos",
      process: "Proc. 0004512-11.2024.8.26.0100",
      type: "SUCUMBENCIA",
      amount: 78000.0,
      dueDate: "30/07/2026",
      status: "OVERDUE",
    },
  ]);

  const [filterType, setFilterType] = useState<string>("ALL");

  const filteredInvoices = invoices.filter((inv) => filterType === "ALL" || inv.status === filterType);

  const totalPago = invoices.filter((i) => i.status === "PAID").reduce((acc, curr) => acc + curr.amount, 0);
  const totalPendente = invoices.filter((i) => i.status === "PENDING").reduce((acc, curr) => acc + curr.amount, 0);
  const totalAtrasado = invoices.filter((i) => i.status === "OVERDUE").reduce((acc, curr) => acc + curr.amount, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-amber-400 font-mono uppercase tracking-wider mb-2">
          <DollarSign className="w-4 h-4 text-amber-400" />
          <span>Gestão Financeira Legal & Honorários Advocatícios</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Financeiro & Controle de Honorários
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Gestão centralizada de honorários contratuais, pro labore, sucumbenciais e repasse de êxito com emissão de relatórios de faturamento.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">Total Recebido (Mês)</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-extrabold text-emerald-400 font-mono mt-3">
            {formatCurrency(totalPago)}
          </p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">A Receber (No Prazo)</span>
            <Clock className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-2xl font-extrabold text-blue-400 font-mono mt-3">
            {formatCurrency(totalPendente)}
          </p>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400">Honorários em Atraso</span>
            <AlertCircle className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-extrabold text-rose-400 font-mono mt-3">
            {formatCurrency(totalAtrasado)}
          </p>
        </div>
      </div>

      {/* Invoice Table Container */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider">
            Lançamentos de Honorários
          </h3>

          <div className="flex items-center space-x-2">
            <span className="text-xs text-zinc-400">Filtrar:</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 focus:outline-none"
            >
              <option value="ALL">Todos os Status</option>
              <option value="PAID">Liquidados (Recebidos)</option>
              <option value="PENDING">Pendentes</option>
              <option value="OVERDUE">Em Atraso</option>
            </select>

            <button
              onClick={() => alert("Simulação de lançamento de fatura de honorários adicionada!")}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Novo Lançamento</span>
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="bg-zinc-950 border-b border-zinc-800 text-[11px] font-mono text-zinc-400 uppercase">
              <tr>
                <th className="p-3">Fatura</th>
                <th className="p-3">Cliente / Parte</th>
                <th className="p-3">Vínculo Processual</th>
                <th className="p-3">Modalidade</th>
                <th className="p-3">Vencimento</th>
                <th className="p-3">Valor (R$)</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-mono">
              {filteredInvoices.map((inv) => (
                <tr key={inv.id} className="hover:bg-zinc-950/50 transition-colors">
                  <td className="p-3 font-bold text-blue-400">{inv.id}</td>
                  <td className="p-3 text-zinc-200 font-sans font-semibold">{inv.client}</td>
                  <td className="p-3 text-zinc-400 text-[11px]">{inv.process}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-[10px] text-zinc-300">
                      {inv.type}
                    </span>
                  </td>
                  <td className="p-3 text-zinc-400">{inv.dueDate}</td>
                  <td className="p-3 font-bold text-zinc-100">{formatCurrency(inv.amount)}</td>
                  <td className="p-3">
                    {inv.status === "PAID" && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                        Pago
                      </span>
                    )}
                    {inv.status === "PENDING" && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] bg-blue-950 text-blue-400 border border-blue-800">
                        Pendente
                      </span>
                    )}
                    {inv.status === "OVERDUE" && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] bg-rose-950 text-rose-400 border border-rose-800">
                        Atrasado
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
