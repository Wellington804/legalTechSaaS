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
} from "lucide-react";

interface ConflictResult {
  clientName: string;
  document: string;
  status: "SAFE" | "WARNING" | "CONFLICT";
  matchRatio: number;
  existingProcess?: string;
  notes: string;
}

export default function ConflitosPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchHistory, setSearchHistory] = useState<ConflictResult[]>([
    {
      clientName: "Banco Siderúrgico S/A",
      document: "12.345.678/0001-99",
      status: "SAFE",
      matchRatio: 0,
      notes: "Nenhum vínculo ético adverso encontrado na base do escritório.",
    },
    {
      clientName: "Construtora Silva & Filhos Ltda",
      document: "98.765.432/0001-11",
      status: "WARNING",
      matchRatio: 45,
      existingProcess: "Proc. 1004589-12.2024.8.26.0100",
      notes: "Sócio minoritário consta como polo passivo em ação trabalhista patrocinada pela banca.",
    },
    {
      clientName: "Carlos Eduardo de Mendonça",
      document: "321.654.987-00",
      status: "CONFLICT",
      matchRatio: 98,
      existingProcess: "Proc. 0001234-88.2025.8.26.0000",
      notes: "CONFLITO ÉTICO DIRETO (Art. 18 OAB): Parte contrária ativa em litígio cível vigente.",
    },
  ]);

  const [lastCheck, setLastCheck] = useState<ConflictResult | null>(null);

  const handleCheck = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;

    setIsSearching(true);
    setTimeout(() => {
      setIsSearching(false);
      const isConflict = searchTerm.toLowerCase().includes("carlos") || searchTerm.toLowerCase().includes("mendonça");
      const isWarning = searchTerm.toLowerCase().includes("silva") || searchTerm.toLowerCase().includes("construtora");

      const newResult: ConflictResult = {
        clientName: searchTerm,
        document: "45.123.890/0001-33",
        status: isConflict ? "CONFLICT" : isWarning ? "WARNING" : "SAFE",
        matchRatio: isConflict ? 95 : isWarning ? 50 : 0,
        existingProcess: isConflict ? "Proc. 1008899-33.2025.8.26.0100" : isWarning ? "Proc. 0004512-11.2024.8.26.0100" : undefined,
        notes: isConflict
          ? "IMPEDIMENTO ÉTICO DETECTADO: Conflito de Interesses Direto segundo Arts. 17-20 da Lei 8.906/94."
          : isWarning
          ? "Atenção: Nome associado a ex-cliente com sigilo profissional ativo nos últimos 5 anos."
          : "Nenhum conflito de interesses detectado. Autorizado cadastramento como cliente.",
      };

      setLastCheck(newResult);
      setSearchHistory([newResult, ...searchHistory]);
    }, 600);
  };

  return (
    <div className="space-y-6">
      {/* Page Header Banner */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono uppercase tracking-wider mb-2">
          <ShieldAlert className="w-4 h-4 text-emerald-400" />
          <span>Módulo de Compliance Ético & Resolução OAB (Arts. 17 a 22)</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Radar Ético de Conflitos de Interesses
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Verificação automatizada pré-contratual de partes, sócios e testemunhas para evitar violações ao Estatuto da Advocacia, dupla representação ou quebra de sigilo profissional.
        </p>
      </div>

      {/* Search Input Box */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
          <Search className="w-4 h-4 text-blue-500" />
          <span>Nova Consulta de Parte ou Empresa</span>
        </h3>

        <form onSubmit={handleCheck} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Digite o Nome Completo, Razão Social, CPF ou CNPJ..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !searchTerm.trim()}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-950 transition-colors flex items-center justify-center space-x-2 shrink-0"
          >
            {isSearching ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Cruzando Base...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Verificar Conflito</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Realtime Check Result Alert */}
      {lastCheck && (
        <div
          className={`p-5 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
            lastCheck.status === "SAFE"
              ? "bg-emerald-950/30 border-emerald-800/60 text-emerald-300"
              : lastCheck.status === "WARNING"
              ? "bg-amber-950/30 border-amber-800/60 text-amber-300"
              : "bg-rose-950/30 border-rose-800/60 text-rose-300"
          }`}
        >
          <div className="flex items-start space-x-3">
            {lastCheck.status === "SAFE" && <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />}
            {lastCheck.status === "WARNING" && <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0 mt-0.5" />}
            {lastCheck.status === "CONFLICT" && <ShieldAlert className="w-6 h-6 text-rose-400 shrink-0 mt-0.5" />}

            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-sm text-zinc-100">{lastCheck.clientName}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                  {lastCheck.document}
                </span>
              </div>
              <p className="text-xs mt-1 leading-relaxed">{lastCheck.notes}</p>
              {lastCheck.existingProcess && (
                <p className="text-[11px] font-mono mt-1 text-zinc-400">Vínculo: {lastCheck.existingProcess}</p>
              )}
            </div>
          </div>

          {lastCheck.status === "SAFE" && (
            <button
              onClick={() => alert(`Certidão de Inexistência de Conflito gerada com sucesso para ${lastCheck.clientName} (Hash SHA-256 Validado).`)}
              className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shrink-0 transition-colors flex items-center space-x-1.5"
            >
              <FileCheck className="w-4 h-4" />
              <span>Emitir Certidão Ética</span>
            </button>
          )}
        </div>
      )}

      {/* Search History Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center justify-between">
          <span>Histórico Recente de Verificações Éti-Jurídicas</span>
          <span className="text-[11px] font-mono text-zinc-500">{searchHistory.length} Registros Auditados</span>
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="bg-zinc-950 border-b border-zinc-800 text-[11px] font-mono text-zinc-400 uppercase">
              <tr>
                <th className="p-3">Parte / Razão Social</th>
                <th className="p-3">Documento</th>
                <th className="p-3">Status Ético</th>
                <th className="p-3">Índice Conflito</th>
                <th className="p-3">Observações Auditadas</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {searchHistory.map((item, idx) => (
                <tr key={idx} className="hover:bg-zinc-950/50 transition-colors">
                  <td className="p-3 font-semibold text-zinc-200">{item.clientName}</td>
                  <td className="p-3 font-mono text-zinc-400 text-[11px]">{item.document}</td>
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
                        <span>Conflito Direto (Bloqueado)</span>
                      </span>
                    )}
                  </td>
                  <td className="p-3 font-mono font-semibold">
                    <span className={item.matchRatio > 50 ? "text-rose-400" : item.matchRatio > 0 ? "text-amber-400" : "text-emerald-400"}>
                      {item.matchRatio}%
                    </span>
                  </td>
                  <td className="p-3 text-zinc-400 text-[11px] max-w-md truncate">{item.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
