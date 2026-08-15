"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Award,
  ShieldAlert,
  Scale,
  FileSignature,
  DollarSign,
  TrendingUp,
  Users,
  Clock,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  Grid,
  Sparkles,
  Plus,
  QrCode,
  FileText,
  AlertTriangle,
  Check,
} from "lucide-react";
import { OAB_SECCIONAIS, useOabStore } from "@/store/useOabStore";
import { formatCurrency } from "@/lib/utils";
import { StateSelectorModal } from "@/components/oab/state-selector-modal";
import { getDashboardSummary, FALLBACK_PERIOD_DATA, KPIMetrics } from "@/lib/dashboardService";

export default function DashboardPage() {
  const { seccional, checklist } = useOabStore();
  const [selectedPeriod, setSelectedPeriod] = useState<"Hoje" | "Semana" | "Mês" | "Ano">("Mês");
  const [isStateModalOpen, setIsStateModalOpen] = useState(false);
  const [currentKPI, setCurrentKPI] = useState<KPIMetrics>(FALLBACK_PERIOD_DATA["Mês"]);
  const [isLoadingApi, setIsLoadingApi] = useState(false);

  // Metadados da Seccional Ativa
  const currentSeccional =
    OAB_SECCIONAIS.find((s) => s.code === seccional) || OAB_SECCIONAIS[24]; // SP por padrão

  // Cálculo real do Checklist OAB
  const completedCount = checklist.filter((i) => i.is_completed).length;
  const totalChecklist = checklist.length;
  const progressPct = Math.round((completedCount / totalChecklist) * 100);

  // Carregar métricas dinâmicas da API (FastAPI / PostgreSQL)
  useEffect(() => {
    let isMounted = true;
    setIsLoadingApi(true);
    getDashboardSummary(selectedPeriod).then((kpiData) => {
      if (isMounted) {
        setCurrentKPI(kpiData);
        setIsLoadingApi(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, [selectedPeriod]);

  const auditLogs = [
    { action: "OAB_SECCIONAL_SELECTED", detail: `Seccional alterada para ${currentSeccional.code}`, time: "Há 2 min", hash: "sha256-f89a12..." },
    { action: "CHECKLIST_ITEM_VALIDATED", detail: `${completedCount} de ${totalChecklist} documentos aprovados`, time: "Há 12 min", hash: "sha256-a4f9e1..." },
    { action: "PIX_PAYMENT_GENERATED", detail: `Guia OAB ${currentSeccional.code} emitida no Pix`, time: "Há 34 min", hash: "sha256-99b8c2..." },
    { action: "CRM_LEAD_STAGE_UPDATED", detail: "Oportunidade movida para Contrato Fechado", time: "Há 1 hora", hash: "sha256-3c7d91..." },
  ];

  const criticalTasks = [
    { title: "Protocolar Inscrição na CSA/OAB", dept: "Hub OAB", deadline: "Hoje, 17:00", priority: "Alta", color: "text-rose-400 border-rose-900/60 bg-rose-950/40" },
    { title: "Acompanhar Proposta Parecer IBS/CBS", dept: "CRM", deadline: "Amanhã, 12:00", priority: "Média", color: "text-amber-400 border-amber-900/60 bg-amber-950/40" },
    { title: "Validar Certidão Negativa Estadual", dept: "Checklist", deadline: "Em 3 dias", priority: "Normal", color: "text-blue-400 border-blue-900/60 bg-blue-950/40" },
  ];

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-blue-950/60 via-zinc-900 to-zinc-900 border border-blue-900/40 rounded-2xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono uppercase tracking-wider mb-1">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Ambiente Multi-Tenant Certificado Tier 1</span>
          </div>
          <h1 className="text-xl font-extrabold text-zinc-100 tracking-tight">
            Painel de Controle Jurídico & Governança
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-2xl">
            Visão consolidada de inteligência jurídica, radar de conflitos éticos, pipeline comercial CRM e trâmite oficial da carteira OAB.
          </p>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <Link
            href="/dashboard/crm"
            className="px-3.5 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5 border border-zinc-700"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Novo Lead</span>
          </Link>
          <Link
            href="/oab-hub"
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-blue-950 transition-all flex items-center space-x-2"
          >
            <Award className="w-4 h-4" />
            <span>Acessar Hub OAB</span>
          </Link>
        </div>
      </div>

      {/* KPI Controls Header & Period Selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-zinc-900/80 border border-zinc-800 p-3.5 rounded-2xl">
        <span className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
          <TrendingUp className="w-4 h-4 text-blue-400" />
          Métricas de Desempenho Executivo
        </span>

        {/* Period Selector */}
        <div className="flex bg-zinc-950 p-1 rounded-xl border border-zinc-800 w-full sm:w-auto">
          {(["Hoje", "Semana", "Mês", "Ano"] as const).map((period) => (
            <button
              key={period}
              onClick={() => setSelectedPeriod(period)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                selectedPeriod === period
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {period}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 hover:border-zinc-700 transition-all shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400">Processos Ativos</span>
            <Scale className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-2xl font-black text-zinc-100 font-mono">{currentKPI.processos}</span>
            <span className="text-[11px] font-medium text-emerald-400 font-mono">
              {currentKPI.processosChange}
            </span>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 hover:border-zinc-700 transition-all shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400">Conflitos Verificados</span>
            <ShieldAlert className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-2xl font-black text-zinc-100 font-mono">{currentKPI.conflitos}</span>
            <span className="text-[11px] font-medium text-emerald-400 font-mono">
              {currentKPI.conflitosChange}
            </span>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 hover:border-zinc-700 transition-all shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400">Contratos Assinados ({selectedPeriod})</span>
            <FileSignature className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-2xl font-black text-zinc-100 font-mono">{currentKPI.contratos}</span>
            <span className="text-[11px] font-medium text-emerald-400 font-mono">
              {currentKPI.contratosChange}
            </span>
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 hover:border-zinc-700 transition-all shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-400">Faturamento Projetado</span>
            <DollarSign className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <span className="text-2xl font-black text-amber-400 font-mono">
              {formatCurrency(currentKPI.faturamento)}
            </span>
            <span className="text-[11px] font-medium text-emerald-400 font-mono">
              {currentKPI.faturamentoChange}
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Grid: OAB Status + CRM Pipeline + Audit Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols): OAB Live Status & CRM Pipeline Summary */}
        <div className="lg:col-span-2 space-y-6">
          {/* OAB Live Status Card (Connected to Zustand Store) */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-xl">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-zinc-800 pb-4 gap-3">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-blue-950 border border-blue-800/50 flex items-center justify-center text-blue-400 shrink-0">
                  <Award className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-zinc-100">Status da Inscrição OAB (Módulo 12)</h3>
                  <p className="text-xs text-zinc-400">Acompanhamento em tempo real do trâmite da carteira vermelha</p>
                </div>
              </div>
              <button
                onClick={() => setIsStateModalOpen(true)}
                className="px-3 py-1.5 bg-blue-950/80 hover:bg-blue-900/60 border border-blue-800/60 text-blue-300 rounded-xl text-xs font-semibold transition-all flex items-center space-x-1.5"
              >
                <Grid className="w-3.5 h-3.5" />
                <span>Trocar UF ({currentSeccional.code})</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80">
                <p className="text-[11px] font-medium text-zinc-400">Seccional Alvo</p>
                <p className="text-sm font-extrabold text-zinc-100 mt-1 font-mono">
                  {currentSeccional.code} ({currentSeccional.uf})
                </p>
                <span className="text-[10px] text-zinc-500 font-mono block mt-0.5">
                  Região {currentSeccional.region}
                </span>
              </div>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80">
                <p className="text-[11px] font-medium text-zinc-400">Progresso do Checklist</p>
                <p className="text-sm font-extrabold text-blue-400 mt-1 font-mono">
                  {completedCount} de {totalChecklist} ({progressPct}%)
                </p>
                <div className="w-full bg-zinc-900 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="bg-blue-500 h-full transition-all duration-500"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800/80">
                <p className="text-[11px] font-medium text-zinc-400">Protocolo de Entrada</p>
                <p className="text-sm font-extrabold text-zinc-200 mt-1 font-mono">PROT-OAB-89F2A1</p>
                <span className="text-[10px] text-emerald-400 font-mono block mt-0.5">
                  ✓ Documentação Homologada
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
              <span className="text-[11px] text-zinc-400">
                Anuidade Base {currentSeccional.code}: <strong className="text-zinc-200 font-mono">{formatCurrency(currentSeccional.baseAnuidade)}</strong>
              </span>
              <Link
                href="/oab-hub/checklist"
                className="text-xs font-bold text-blue-400 hover:text-blue-300 flex items-center space-x-1"
              >
                <span>Gerenciar Checklist Completo</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>

          {/* Quick Launch Action Hub */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-3 shadow-xl">
            <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>Central de Ações Rápidas Executivas</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <Link
                href="/dashboard/crm"
                className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-xl hover:border-blue-500/60 transition-all flex items-center space-x-3 group"
              >
                <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 group-hover:scale-105 transition-transform">
                  <Users className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-zinc-200 group-hover:text-blue-400 transition-colors">Novo Lead CRM</p>
                  <p className="text-[10px] text-zinc-500">Cadastrar cliente</p>
                </div>
              </Link>

              <Link
                href="/oab-hub/calculadora"
                className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-xl hover:border-emerald-500/60 transition-all flex items-center space-x-3 group"
              >
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 group-hover:scale-105 transition-transform">
                  <QrCode className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-zinc-200 group-hover:text-emerald-400 transition-colors">Boleto/Pix OAB</p>
                  <p className="text-[10px] text-zinc-500">Emitir guia oficial</p>
                </div>
              </Link>

              <Link
                href="/oab-hub/sua-guide"
                className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-xl hover:border-amber-500/60 transition-all flex items-center space-x-3 group"
              >
                <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 group-hover:scale-105 transition-transform">
                  <DollarSign className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-zinc-200 group-hover:text-amber-400 transition-colors">Tabela Ética</p>
                  <p className="text-[10px] text-zinc-500">Reajuste honorários</p>
                </div>
              </Link>

              <Link
                href="/oab-hub/declaracoes"
                className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-xl hover:border-purple-500/60 transition-all flex items-center space-x-3 group"
              >
                <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 group-hover:scale-105 transition-transform">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-zinc-200 group-hover:text-purple-400 transition-colors">Emitir Declaração</p>
                  <p className="text-[10px] text-zinc-500">Arts. 27-30 OAB</p>
                </div>
              </Link>
            </div>
          </div>
        </div>

        {/* Right Column (1 Col): Prazos & Audit Logs */}
        <div className="space-y-6">
          {/* Prazos Críticos */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-xl">
            <h3 className="text-sm font-bold text-zinc-100 flex items-center justify-between">
              <span>Agenda & Prazos Críticos</span>
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </h3>

            <div className="space-y-3">
              {criticalTasks.map((t, i) => (
                <div key={i} className={`p-3 rounded-xl border ${t.color} space-y-1.5`}>
                  <div className="flex justify-between items-start">
                    <h4 className="text-xs font-bold text-zinc-200 leading-tight">{t.title}</h4>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800">
                      {t.priority}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-[10px] font-mono text-zinc-400">
                    <span>{t.dept}</span>
                    <span>{t.deadline}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Audit Logs Recentes */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-xl">
            <h3 className="text-sm font-bold text-zinc-100 flex items-center justify-between">
              <span>Audit Logs Recentes (LGPD)</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </h3>
            <div className="space-y-3">
              {auditLogs.map((log, i) => (
                <div key={i} className="p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs space-y-1">
                  <div className="flex justify-between items-center">
                    <p className="font-bold text-zinc-200 font-mono text-[11px]">{log.action}</p>
                    <span className="text-[10px] text-zinc-400 flex items-center font-mono">
                      <Clock className="w-3 h-3 mr-1" />
                      {log.time}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug">{log.detail}</p>
                  <p className="text-[9px] text-zinc-500 font-mono pt-1 border-t border-zinc-900">{log.hash}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* State Selector Modal */}
      <StateSelectorModal
        isOpen={isStateModalOpen}
        onClose={() => setIsStateModalOpen(false)}
      />
    </div>
  );
}

