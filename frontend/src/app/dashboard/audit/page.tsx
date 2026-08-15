"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Lock,
  Search,
  Download,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Key,
  Shield,
  FileCheck2,
} from "lucide-react";

interface AuditLog {
  id: string;
  action: string;
  user: string;
  role: string;
  ipAddress: string;
  timestamp: string;
  hash: string;
  severity: "INFO" | "SECURITY" | "WARNING" | "CRITICAL";
}

export default function AuditPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [logs] = useState<AuditLog[]>([
    {
      id: "LOG-1092",
      action: "OAB_DECLARATION_GENERATED",
      user: "Dr. Alexandre Rossi",
      role: "Sócio Administrador",
      ipAddress: "189.40.102.44",
      timestamp: "12/08/2026 16:42:10",
      hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      severity: "INFO",
    },
    {
      id: "LOG-1093",
      action: "CONFLICT_CHECK_EXECUTED",
      user: "Dra. Juliana Mendes",
      role: "Advogada Associada",
      ipAddress: "177.12.89.201",
      timestamp: "12/08/2026 15:15:02",
      hash: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
      severity: "SECURITY",
    },
    {
      id: "LOG-1094",
      action: "DOCUMENT_DIGITAL_SIGNATURE",
      user: "Dr. Alexandre Rossi",
      role: "Sócio Administrador",
      ipAddress: "189.40.102.44",
      timestamp: "12/08/2026 14:02:44",
      hash: "3c7d91209b5e4a1c88d904b7712390a1fbc09912001928374659102837465019",
      severity: "INFO",
    },
    {
      id: "LOG-1095",
      action: "UNAUTHORIZED_TENANT_ACCESS_ATTEMPT",
      user: "Sistema de Firewall",
      role: "Automated Bot",
      ipAddress: "45.18.201.12",
      timestamp: "12/08/2026 12:30:19",
      hash: "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
      severity: "CRITICAL",
    },
  ]);

  const filteredLogs = logs.filter(
    (l) =>
      l.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.hash.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono uppercase tracking-wider mb-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Trilha de Auditoria Criptográfica Imutável & LGPD Compliance</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Governança & Audit Logs do Sistema
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Registro encadeado por hash de todas as ações de usuários, geração de documentos, assinaturas e verificações éticas para conformidade com a LGPD e a OAB.
        </p>
      </div>

      {/* Security Status Card */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-zinc-900 to-zinc-900 border border-emerald-900/40 rounded-xl p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-950 border border-emerald-800/80 flex items-center justify-center text-emerald-400">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-zinc-100">Integridade dos Audit Logs: 100% Verificada</h3>
            <p className="text-xs text-zinc-400 font-mono">Último Hash do Bloco: 0x9f8b2c4...e11 (Imutável)</p>
          </div>
        </div>

        <button
          onClick={() => alert("Relatório de Governança e Log de Auditoria LGPD exportado com sucesso (SHA-256 Validado).")}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center space-x-2 shrink-0"
        >
          <Download className="w-4 h-4" />
          <span>Exportar Relatório LGPD</span>
        </button>
      </div>

      {/* Log Search and Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider">
            Registros de Auditoria em Tempo Real
          </h3>
          <span className="text-[11px] font-mono text-zinc-500">{filteredLogs.length} Eventos</span>
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filtrar eventos por Ação, Usuário ou Hash..."
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-2 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-300">
            <thead className="bg-zinc-950 border-b border-zinc-800 text-[11px] font-mono text-zinc-400 uppercase">
              <tr>
                <th className="p-3">ID Log</th>
                <th className="p-3">Ação Executada</th>
                <th className="p-3">Usuário / Cargo</th>
                <th className="p-3">IP Origem</th>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Severidade</th>
                <th className="p-3">Hash SHA-256</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-mono">
              {filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-zinc-950/50 transition-colors">
                  <td className="p-3 font-bold text-blue-400">{log.id}</td>
                  <td className="p-3 font-semibold text-zinc-100 font-sans">{log.action}</td>
                  <td className="p-3 text-zinc-300 font-sans">
                    <p className="font-medium text-zinc-200">{log.user}</p>
                    <p className="text-[10px] text-zinc-500">{log.role}</p>
                  </td>
                  <td className="p-3 text-zinc-400">{log.ipAddress}</td>
                  <td className="p-3 text-zinc-400">{log.timestamp}</td>
                  <td className="p-3">
                    {log.severity === "INFO" && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-blue-950 text-blue-400 border border-blue-800">
                        INFO
                      </span>
                    )}
                    {log.severity === "SECURITY" && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                        SEGURANÇA
                      </span>
                    )}
                    {log.severity === "CRITICAL" && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-rose-950 text-rose-400 border border-rose-800">
                        CRÍTICO
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-zinc-500 text-[10px] max-w-xs truncate">{log.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
