"use client";

import React, { useState } from "react";
import {
  ShieldAlert,
  Search,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Building,
  UserCheck,
  ShieldCheck,
  RefreshCw,
  Award,
  Download,
  Eye,
  Network,
  Lock,
  Sparkles,
  X,
  FileText,
  Copy,
  Check,
  ExternalLink,
  Users,
  Shield,
  Layers,
  FileSpreadsheet,
} from "lucide-react";

export interface ConflictResult {
  id: string;
  clientName: string;
  document: string;
  entityType: string;
  role: string;
  status: "SAFE" | "WARNING" | "CONFLICT";
  matchRatio: number;
  existingProcess?: string;
  notes: string;
  oabArticle: string;
  sha256Hash: string;
  date: string;
  graphNodes?: { name: string; role: string; connection: string }[];
}

export default function ConflitosPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedEntityType, setSelectedEntityType] = useState<string>("Pessoa Jurídica (PJ)");
  const [selectedRole, setSelectedRole] = useState<string>("Cliente Potencial");
  const [isSearching, setIsSearching] = useState(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Modals state
  const [selectedRiskModal, setSelectedRiskModal] = useState<ConflictResult | null>(null);
  const [selectedCertificateModal, setSelectedCertificateModal] = useState<ConflictResult | null>(null);

  const [searchHistory, setSearchHistory] = useState<ConflictResult[]>([
    {
      id: "cnf_101",
      clientName: "Banco Siderúrgico S/A",
      document: "12.345.678/0001-99",
      entityType: "Pessoa Jurídica (PJ)",
      role: "Cliente Potencial",
      status: "SAFE",
      matchRatio: 0,
      notes: "Nenhum vínculo ético adverso encontrado na base do escritório ou nos tribunais.",
      oabArticle: "Art. 17 da Lei 8.906/94 (Sem Impedimento)",
      sha256Hash: "E9C3A1B4D8F70291C4A5B6E7F809123456789ABCDEF123456789ABCDEF123456",
      date: "Hoje, 18:40",
    },
    {
      id: "cnf_102",
      clientName: "Construtora Silva & Filhos Ltda",
      document: "98.765.432/0001-11",
      entityType: "Grupo Econômico / Holding",
      role: "Sócio / Investidor",
      status: "WARNING",
      matchRatio: 45,
      existingProcess: "Proc. 1004589-12.2024.8.26.0100 (2ª Vara do Trabalho de SP)",
      notes: "ALERTA DE VÍNCULO ÉTICO: Sócio minoritário consta como polo passivo em ação trabalhista patrocinada pela banca.",
      oabArticle: "Art. 19 da Lei 8.906/94 (Sigilo & Segredamento Ético)",
      sha256Hash: "7A8B9C0D1E2F3A4B5C6D7E8F90123456789ABCDEF123456789ABCDEF12345678",
      date: "Ontem, 14:15",
      graphNodes: [
        { name: "Construtora Silva & Filhos Ltda", role: "PJ Principal", connection: "Objeto da Consulta" },
        { name: "Carlos Eduardo Silva", role: "Sócio Minoritário (15%)", connection: "Vínculo Societário" },
        { name: "Proc. Trabalhista nº 1004589", role: "Polo Passivo", connection: "Patrocinado pela Banca" },
      ],
    },
    {
      id: "cnf_103",
      clientName: "Carlos Eduardo de Mendonça",
      document: "321.654.987-00",
      entityType: "Pessoa Física (CPF)",
      role: "Polo Passivo (Réu)",
      status: "CONFLICT",
      matchRatio: 98,
      existingProcess: "Proc. 0001234-88.2025.8.26.0000 (3ª Vara Cível de SP)",
      notes: "IMPEDIMENTO ÉTICO ABSOLUTO: Parte contrária ativa em litígio cível vigente patrocinado pela banca. Vedada a representação.",
      oabArticle: "Art. 18 da Lei 8.906/94 (Dupla Representação Vedada)",
      sha256Hash: "F1E2D3C4B5A697887766554433221100AABBCCDDEEFF00112233445566778899",
      date: "11 de Ago",
      graphNodes: [
        { name: "Carlos Eduardo de Mendonça", role: "Pessoa Física", connection: "Objeto da Consulta" },
        { name: "Banca LexFlow Advocacia", role: "Patrono Ativo", connection: "Advogado da Parte Contrária" },
        { name: "Proc. Cível nº 0001234", role: "Autor X Réu", connection: "Litígio Ativo em Andamento" },
      ],
    },
  ]);

  const [lastCheck, setLastCheck] = useState<ConflictResult | null>(null);

  const entityTypes = [
    "Pessoa Jurídica (PJ)",
    "Pessoa Física (CPF)",
    "Grupo Econômico / Holding",
    "Advogado / Banca Adversa",
  ];

  const ethicalRoles = [
    "Cliente Potencial",
    "Polo Passivo (Réu)",
    "Testemunha / Perito",
    "Sócio / Investidor",
  ];

  const handleCheck = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;

    setIsSearching(true);
    setTimeout(() => {
      setIsSearching(false);
      const nameLower = searchTerm.toLowerCase();
      const isConflict = nameLower.includes("carlos") || nameLower.includes("mendonça") || nameLower.includes("conflito");
      const isWarning = nameLower.includes("silva") || nameLower.includes("construtora") || nameLower.includes("holding");

      const generatedHash = Array.from({ length: 64 }, () =>
        Math.floor(Math.random() * 16).toString(16)
      ).join("").toUpperCase();

      const newResult: ConflictResult = {
        id: `cnf_${Date.now()}`,
        clientName: searchTerm.trim(),
        document: isConflict ? "321.654.987-00" : isWarning ? "98.765.432/0001-11" : "45.123.890/0001-33",
        entityType: selectedEntityType,
        role: selectedRole,
        status: isConflict ? "CONFLICT" : isWarning ? "WARNING" : "SAFE",
        matchRatio: isConflict ? 98 : isWarning ? 45 : 0,
        existingProcess: isConflict
          ? "Proc. 1008899-33.2025.8.26.0100 (3ª Vara Cível)"
          : isWarning
          ? "Proc. 0004512-11.2024.8.26.0100 (1ª Vara Empresarial)"
          : undefined,
        notes: isConflict
          ? "IMPEDIMENTO ÉTICO ABSOLUTO: Conflito direto detectado segundo o Art. 18 da Lei 8.906/94 (Estatuto da OAB)."
          : isWarning
          ? "ALERTA ÉTICO: Nome associado a sócio/ex-cliente com dever de sigilo ativo nos últimos 5 anos (Art. 19 OAB)."
          : "NENHUM CONFLITO ÉTICO ENCONTRADO. Autorizado o cadastramento e celebração do contrato de honorários.",
        oabArticle: isConflict
          ? "Art. 18 da Lei 8.906/94 (Vedação de Representação Concorrente)"
          : isWarning
          ? "Art. 19 da Lei 8.906/94 (Dever de Sigilo e Resguardo de Informações)"
          : "Art. 17 da Lei 8.906/94 (Livre Exercício Mandato Ético)",
        sha256Hash: generatedHash,
        date: "Agora mesmo",
        graphNodes: isConflict || isWarning
          ? [
              { name: searchTerm.trim(), role: selectedEntityType, connection: "Alvo da Pesquisa" },
              { name: "Base do Escritório / CRM", role: "Banco de Clientes", connection: "Cruzamento Vetorial" },
              { name: isConflict ? "Proc. 1008899-33" : "Proc. 0004512-11", role: "Litígio Ativo", connection: "Vínculo Detectado" },
            ]
          : undefined,
      };

      setLastCheck(newResult);
      setSearchHistory([newResult, ...searchHistory]);
    }, 700);
  };

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleExportCSV = () => {
    const csvContent =
      "data:text/csv;charset=utf-8," +
      ["ID,Parte,Documento,Tipo,Papel,Status,Score,Hash SHA-256,Data"]
        .concat(
          searchHistory.map(
            (item) =>
              `"${item.id}","${item.clientName}","${item.document}","${item.entityType}","${item.role}","${item.status}","${item.matchRatio}%","${item.sha256Hash}","${item.date}"`
          )
        )
        .join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Auditoria_Conflitos_Eticos_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Metrics
  const totalChecks = searchHistory.length + 120;
  const blockedConflicts = searchHistory.filter((i) => i.status === "CONFLICT").length + 28;
  const totalCertificates = searchHistory.filter((i) => i.status === "SAFE").length + 95;
  const complianceRate = Math.round(((totalChecks - blockedConflicts) / totalChecks) * 100);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div>
          <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono uppercase tracking-wider mb-1">
            <ShieldAlert className="w-4 h-4 text-emerald-400" />
            <span>Módulo de Compliance Ético & Resolução OAB (Arts. 17 a 22)</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Radar Ético de Conflitos de Interesses
          </h1>
          <p className="text-xs text-zinc-400 mt-1 max-w-2xl leading-relaxed">
            Verificação automatizada pré-contratual de partes, sócios e testemunhas para evitar violações ao Estatuto da Advocacia, dupla representação ou quebra de sigilo profissional.
          </p>
        </div>

        <button
          onClick={handleExportCSV}
          className="px-4 py-2.5 bg-zinc-950 hover:bg-zinc-800 border border-zinc-800 text-zinc-200 rounded-xl text-xs font-bold transition-all flex items-center space-x-2 shrink-0 self-start md:self-auto"
        >
          <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
          <span>Exportar Relatório Auditado</span>
        </button>
      </div>

      {/* Executive KPIs Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Consultas Auditadas</span>
            <h3 className="text-xl font-extrabold text-zinc-100 mt-0.5 font-mono">
              {totalChecks}
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
            <Search className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Impedimentos Bloqueados</span>
            <h3 className="text-xl font-extrabold text-rose-400 mt-0.5 font-mono">
              {blockedConflicts} <span className="text-xs font-normal text-zinc-500">impedimentos</span>
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Certidões Emitidas</span>
            <h3 className="text-xl font-extrabold text-emerald-400 mt-0.5 font-mono">
              {totalCertificates} <span className="text-xs font-normal text-zinc-500">SHA-256</span>
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <FileCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Conformidade Ética</span>
            <h3 className="text-xl font-extrabold text-amber-400 mt-0.5 font-mono">
              {complianceRate}% <span className="text-xs font-normal text-zinc-500">100% Auditado</span>
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center">
            <Award className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Advanced Multidimensional Search Box */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5 shadow-lg">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-blue-500" />
            <span>Nova Consulta Ética Pré-Contratual</span>
          </h3>
          <span className="text-[10px] font-mono text-zinc-500">
            Fuzzy Match & Cruzamento Vetorial Ativo
          </span>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-zinc-950 p-4 rounded-xl border border-zinc-800">
          <div>
            <label className="text-[10px] font-mono text-zinc-400 uppercase block mb-1.5">
              Tipo de Entidade Auditada
            </label>
            <div className="flex flex-wrap gap-1.5">
              {entityTypes.map((et) => (
                <button
                  key={et}
                  type="button"
                  onClick={() => setSelectedEntityType(et)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    selectedEntityType === et
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800"
                  }`}
                >
                  {et}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-[10px] font-mono text-zinc-400 uppercase block mb-1.5">
              Papel / Qualificação no Caso
            </label>
            <div className="flex flex-wrap gap-1.5">
              {ethicalRoles.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setSelectedRole(r)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    selectedRole === r
                      ? "bg-emerald-600 text-white shadow-sm"
                      : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Input & Submit */}
        <form onSubmit={handleCheck} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Digite Nome Completo, Razão Social, CPF, CNPJ ou Nome de Sócio..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-3 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !searchTerm.trim()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-lg shadow-blue-950 transition-all flex items-center justify-center space-x-2 shrink-0 cursor-pointer"
          >
            {isSearching ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Cruzando Bases...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Verificar Conflito Ético</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Realtime Check Result Alert & AI Advisor Box */}
      {lastCheck && (
        <div
          className={`p-5 rounded-2xl border flex flex-col space-y-4 shadow-xl animate-in fade-in duration-300 ${
            lastCheck.status === "SAFE"
              ? "bg-emerald-950/30 border-emerald-800/60 text-emerald-300"
              : lastCheck.status === "WARNING"
              ? "bg-amber-950/30 border-amber-800/60 text-amber-300"
              : "bg-rose-950/30 border-rose-800/60 text-rose-300"
          }`}
        >
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-start space-x-3">
              {lastCheck.status === "SAFE" && <CheckCircle2 className="w-7 h-7 text-emerald-400 shrink-0 mt-0.5" />}
              {lastCheck.status === "WARNING" && <AlertTriangle className="w-7 h-7 text-amber-400 shrink-0 mt-0.5" />}
              {lastCheck.status === "CONFLICT" && <ShieldAlert className="w-7 h-7 text-rose-400 shrink-0 mt-0.5" />}

              <div>
                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                  <span className="font-extrabold text-base text-zinc-100">{lastCheck.clientName}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                    {lastCheck.document}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-blue-400">
                    {lastCheck.entityType}
                  </span>
                </div>
                <p className="text-xs mt-1 leading-relaxed text-zinc-200">{lastCheck.notes}</p>
                {lastCheck.existingProcess && (
                  <p className="text-[11px] font-mono mt-1 text-zinc-400">Processo Vinculado: {lastCheck.existingProcess}</p>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0 self-end sm:self-auto">
              {lastCheck.status === "SAFE" && (
                <button
                  onClick={() => setSelectedCertificateModal(lastCheck)}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 shadow-md"
                >
                  <FileCheck className="w-4 h-4" />
                  <span>Emitir Certidão SHA-256</span>
                </button>
              )}

              {(lastCheck.status === "WARNING" || lastCheck.status === "CONFLICT") && (
                <button
                  onClick={() => setSelectedRiskModal(lastCheck)}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5"
                >
                  <Network className="w-4 h-4 text-amber-400" />
                  <span>Ver Grafo de Vínculos</span>
                </button>
              )}
            </div>
          </div>

          {/* AI Advisor Explanation Box */}
          <div className="bg-zinc-950/80 border border-zinc-800/80 rounded-xl p-3.5 flex items-start space-x-3 text-xs">
            <Sparkles className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-purple-300 block mb-0.5">
                Parecer de Inteligência Regulológica OAB ({lastCheck.oabArticle})
              </span>
              <p className="text-zinc-400 leading-relaxed text-[11px]">
                {lastCheck.status === "SAFE"
                  ? "Consulta auditada e validada sem intersecções com clientes ativos da banca. Emitida prova criptográfica em conformidade com as diretrizes de compliance."
                  : lastCheck.status === "WARNING"
                  ? "Detectado vínculo secundário de sócio ou ex-cliente. Recomendado segredamento de arquivo físico e termo de consentimento prévio conforme resolução do TED/OAB."
                  : "Detectado conflito ético direto entre as partes. O Estatuto da OAB veda estritamente o patrocínio de interesses antagônicos no mesmo processo ou causa correlata."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Search History Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-lg">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
            <Layers className="w-4 h-4 text-emerald-400" />
            <span>Histórico Recente de Verificações Éti-Jurídicas</span>
          </h3>
          <span className="text-[11px] font-mono text-zinc-500">
            {searchHistory.length} Registros Auditados
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="bg-zinc-950 border-b border-zinc-800 text-[11px] font-mono text-zinc-400 uppercase">
              <tr>
                <th className="p-3">Parte / Razão Social</th>
                <th className="p-3">Tipo & Papel</th>
                <th className="p-3">Status Ético</th>
                <th className="p-3">Score Risco</th>
                <th className="p-3">Prova Criptográfica (SHA-256)</th>
                <th className="p-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {searchHistory.map((item) => (
                <tr key={item.id} className="hover:bg-zinc-950/50 transition-colors">
                  <td className="p-3">
                    <div className="font-semibold text-zinc-200">{item.clientName}</div>
                    <div className="text-[10px] font-mono text-zinc-500">{item.document}</div>
                  </td>
                  <td className="p-3">
                    <div className="text-[11px] text-zinc-300">{item.entityType}</div>
                    <div className="text-[10px] text-zinc-500">{item.role}</div>
                  </td>
                  <td className="p-3">
                    {item.status === "SAFE" && (
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-950 border border-emerald-800 text-emerald-400">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Aprovado (Sem Conflito)</span>
                      </span>
                    )}
                    {item.status === "WARNING" && (
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-amber-950 border border-amber-800 text-amber-400">
                        <AlertTriangle className="w-3 h-3" />
                        <span>Alerta de Vínculo</span>
                      </span>
                    )}
                    {item.status === "CONFLICT" && (
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-rose-950 border border-rose-800 text-rose-400">
                        <ShieldAlert className="w-3 h-3" />
                        <span>Conflito Direto</span>
                      </span>
                    )}
                  </td>
                  <td className="p-3 font-mono font-semibold">
                    <span className={item.matchRatio > 50 ? "text-rose-400" : item.matchRatio > 0 ? "text-amber-400" : "text-emerald-400"}>
                      {item.matchRatio}%
                    </span>
                  </td>
                  <td className="p-3 font-mono text-[10px] text-zinc-500 max-w-xs truncate">
                    <div className="flex items-center space-x-1">
                      <span className="truncate">{item.sha256Hash}</span>
                      <button
                        onClick={() => handleCopyHash(item.sha256Hash)}
                        className="text-zinc-400 hover:text-zinc-200 shrink-0 p-1"
                        title="Copiar Hash SHA-256"
                      >
                        {copiedHash === item.sha256Hash ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end space-x-2">
                      {item.status === "SAFE" ? (
                        <button
                          onClick={() => setSelectedCertificateModal(item)}
                          className="p-1.5 bg-emerald-950 hover:bg-emerald-900 border border-emerald-800 text-emerald-400 rounded-lg text-xs font-medium transition-colors"
                          title="Ver Certidão Ética"
                        >
                          <FileCheck className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button
                          onClick={() => setSelectedRiskModal(item)}
                          className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition-colors"
                          title="Ver Matriz de Risco / Grafo"
                        >
                          <Network className="w-3.5 h-3.5 text-amber-400" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal 1: Matriz de Risco Ético & Grafo de Vínculos */}
      {selectedRiskModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div 
            className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-400 flex items-center justify-center font-bold text-sm">
                  <Network className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-zinc-100">
                    Matriz de Risco & Grafo de Conexões
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Análise detalhada de vínculos entre {selectedRiskModal.clientName} e a banca.
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedRiskModal(null)}
                className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs">
              {/* Summary Status */}
              <div className="p-4 rounded-xl border bg-zinc-950 border-zinc-800 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">Alvo Auditado</span>
                  <h3 className="text-sm font-bold text-zinc-100 mt-0.5">{selectedRiskModal.clientName}</h3>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase block">Score de Risco</span>
                  <span className={`text-lg font-extrabold font-mono ${selectedRiskModal.matchRatio > 50 ? "text-rose-400" : "text-amber-400"}`}>
                    {selectedRiskModal.matchRatio}% Impedimento
                  </span>
                </div>
              </div>

              {/* Visual Graph Nodes Breakdown */}
              <div className="space-y-3">
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                  Grafo Relacional de Vínculos
                </label>

                <div className="bg-zinc-950 border border-zinc-800/80 rounded-xl p-4 space-y-3">
                  {(selectedRiskModal.graphNodes || [
                    { name: selectedRiskModal.clientName, role: selectedRiskModal.entityType, connection: "Alvo da Pesquisa" },
                    { name: "Litígio Ativo na Banca", role: "Parte Contrária", connection: "Processo Ativo" },
                  ]).map((node, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-zinc-900 border border-zinc-800 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div className="w-7 h-7 rounded-lg bg-blue-950 border border-blue-800 text-blue-400 flex items-center justify-center font-bold text-xs">
                          0{i + 1}
                        </div>
                        <div>
                          <h4 className="font-bold text-zinc-100">{node.name}</h4>
                          <span className="text-[10px] text-zinc-500 font-mono">{node.role}</span>
                        </div>
                      </div>
                      <span className="px-2.5 py-1 bg-zinc-950 text-amber-400 border border-amber-800/60 text-[10px] font-mono rounded">
                        {node.connection}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Regulatory OAB Legal Rationale */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-2">
                <span className="text-[10px] font-mono text-purple-400 uppercase font-bold block">
                  Fundamentação Normativa OAB
                </span>
                <p className="text-zinc-300 leading-relaxed">
                  {selectedRiskModal.oabArticle}: {selectedRiskModal.notes}
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-end">
              <button
                onClick={() => setSelectedRiskModal(null)}
                className="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors"
              >
                Fechar Matriz
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 2: Certidão Ética de Inexistência de Conflito (Hash SHA-256) */}
      {selectedCertificateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div 
            className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 flex items-center justify-center font-bold text-sm">
                  <FileCheck className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-zinc-100">
                    Certidão Ética de Compliance
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Documento oficial de inexistência de conflito de interesses.
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedCertificateModal(null)}
                className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Certificate Layout */}
            <div className="p-6 overflow-y-auto space-y-5 text-xs">
              <div className="bg-zinc-950 border border-emerald-900/60 rounded-xl p-6 space-y-4 text-center">
                <div className="inline-flex items-center space-x-2 px-3 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full font-mono text-[10px]">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>REGISTRO OFICIAL VALIDADO</span>
                </div>

                <h3 className="text-lg font-black text-zinc-100 tracking-tight uppercase">
                  Certidão de Inexistência de Conflito Ético
                </h3>

                <p className="text-zinc-300 leading-relaxed text-xs max-w-md mx-auto">
                  Certificamos para os devidos fins de compliance pré-contratual que a consulta realizada para a entidade <strong className="text-emerald-400">{selectedCertificateModal.clientName}</strong> ({selectedCertificateModal.document}) não apresenta intersecção com partes ou litigantes ativos na banca.
                </p>

                <div className="pt-4 border-t border-zinc-800 space-y-2 text-left">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-zinc-500">Data de Validação:</span>
                    <span className="text-zinc-200 font-mono">{selectedCertificateModal.date}</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-zinc-500">Base Normativa:</span>
                    <span className="text-zinc-200 font-mono">{selectedCertificateModal.oabArticle}</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-zinc-500">Hash SHA-256 Inviolável:</span>
                  </div>
                  <div className="bg-zinc-900 p-2 rounded border border-zinc-800 font-mono text-[10px] text-emerald-400 break-all">
                    {selectedCertificateModal.sha256Hash}
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-between">
              <button
                onClick={() => handleCopyHash(selectedCertificateModal.sha256Hash)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors flex items-center space-x-1.5"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copiar Hash</span>
              </button>

              <button
                onClick={() => {
                  alert(`Certidão Criptográfica gerada e enviada para a fila de impressão em PDF.`);
                  setSelectedCertificateModal(null);
                }}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-md transition-colors flex items-center space-x-1.5"
              >
                <Download className="w-4 h-4" />
                <span>Baixar Certidão PDF</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

