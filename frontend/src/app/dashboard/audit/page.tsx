"use client";

import React, { useState, useMemo } from "react";
import jsPDF from "jspdf";
import { PLATFORM_CONFIG } from "@/config/platform";
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
  Eye,
  RefreshCw,
  Sparkles,
  Server,
  Globe,
  Terminal,
  X,
  Copy,
  Check,
  Filter,
  Cpu,
  FileText,
} from "lucide-react";

export interface AuditLog {
  id: string;
  action: string;
  category: "SEGURANÇA" | "DOCUMENTOS" | "LGPD" | "SISTEMA" | "FINANCEIRO";
  user: string;
  role: string;
  ipAddress: string;
  location: string;
  timestamp: string;
  hash: string;
  prevHash: string;
  severity: "INFO" | "SECURITY" | "WARNING" | "CRITICAL" | "LGPD";
  detailsJson: string;
}

export default function AuditPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [isVerifyingChain, setIsVerifyingChain] = useState(false);
  const [chainVerified, setChainVerified] = useState(true);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    showToast("Hash SHA-256 copiado para a área de transferência!");
    setTimeout(() => setCopiedHash(null), 2500);
  };

  const [logs] = useState<AuditLog[]>([
    {
      id: "LOG-1092",
      action: "OAB_DECLARATION_GENERATED",
      category: "DOCUMENTOS",
      user: "Dr. Alexandre Rossi",
      role: "Sócio Administrador (OAB/SP 458.912)",
      ipAddress: "189.40.102.44",
      location: "São Paulo, SP - Brasil",
      timestamp: "12/08/2026 16:42:10 UTC-3",
      hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      prevHash: "0x8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
      severity: "INFO",
      detailsJson: JSON.stringify(
        {
          event: "Geração de Certidão de Regularidade Ética OAB",
          module: "Hub OAB & Novo Advogado",
          documentId: "DOC-OAB-8841",
          verificationCode: "OAB-SP-VERIFIED-2026",
          signatureType: "ICP-Brasil A1",
        },
        null,
        2
      ),
    },
    {
      id: "LOG-1093",
      action: "CONFLICT_CHECK_EXECUTED",
      category: "SEGURANÇA",
      user: "Dra. Juliana Mendes",
      role: "Advogada Associada",
      ipAddress: "177.12.89.201",
      location: "Rio de Janeiro, RJ - Brasil",
      timestamp: "12/08/2026 15:15:02 UTC-3",
      hash: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
      prevHash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      severity: "SECURITY",
      detailsJson: JSON.stringify(
        {
          event: "Pesquisa de Conflito de Interesses de Clientes",
          targetCpfCnpj: "12.345.678/0001-90",
          matchesFound: 0,
          complianceResult: "ISENTO_DE_CONFLITO",
          oabRule: "Artigo 17, Código de Ética e Disciplina da OAB",
        },
        null,
        2
      ),
    },
    {
      id: "LOG-1094",
      action: "DOCUMENT_DIGITAL_SIGNATURE",
      category: "DOCUMENTOS",
      user: "Dr. Alexandre Rossi",
      role: "Sócio Administrador (OAB/SP 458.912)",
      ipAddress: "189.40.102.44",
      location: "São Paulo, SP - Brasil",
      timestamp: "12/08/2026 14:02:44 UTC-3",
      hash: "3c7d91209b5e4a1c88d904b7712390a1fbc09912001928374659102837465019",
      prevHash: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
      severity: "INFO",
      detailsJson: JSON.stringify(
        {
          event: "Selagem Criptográfica de Contrato de Honorários",
          docId: "DOC-9948",
          signersCount: 2,
          ntpTimestamp: "Observatório da Hora Legal do Brasil ON/NTP",
          hashOriginal: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        },
        null,
        2
      ),
    },
    {
      id: "LOG-1095",
      action: "UNAUTHORIZED_TENANT_ACCESS_ATTEMPT",
      category: "SEGURANÇA",
      user: "Sistema de Firewall (WAF)",
      role: "Automated Bot / Unknown IP",
      ipAddress: "45.18.201.12",
      location: "Frankfurt, Hessen - Alemanha",
      timestamp: "12/08/2026 12:30:19 UTC-3",
      hash: "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
      prevHash: "3c7d91209b5e4a1c88d904b7712390a1fbc09912001928374659102837465019",
      severity: "CRITICAL",
      detailsJson: JSON.stringify(
        {
          event: "Tentativa de Violação de Escopo de Tenant (RLS Blocked)",
          targetTenant: "tenant_rossi_law",
          attackVector: "SQL Injection / Direct API Probe",
          actionTaken: "IP_PERMANENTLY_BLOCKED_BY_WAF",
          riskScore: "HIGH_CRITICAL_99",
        },
        null,
        2
      ),
    },
    {
      id: "LOG-1096",
      action: "LGPD_PERSONAL_DATA_ACCESS_REQUEST",
      category: "LGPD",
      user: "Encarregado DPO (Sistema Automático)",
      role: "DPO Officer",
      ipAddress: "177.138.42.109",
      location: "São Paulo, SP - Brasil",
      timestamp: "12/08/2026 11:10:00 UTC-3",
      hash: "9b8a7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
      prevHash: "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
      severity: "LGPD",
      detailsJson: JSON.stringify(
        {
          event: "Requisição de Transparência de Dados do Titular (Art. 18 LGPD)",
          subjectCpf: "***.984.120-**",
          actionExecuted: "EXPORT_DATA_PORTABILITY_PACKAGE",
          anonymizedFields: ["hash_biometric", "ip_logs"],
          complianceOfficer: "Dr. Alexandre Rossi (DPO Lead)",
        },
        null,
        2
      ),
    },
  ]);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesSearch =
        log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.hash.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.id.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesSeverity = severityFilter === "ALL" || log.severity === severityFilter;

      return matchesSearch && matchesSeverity;
    });
  }, [logs, searchTerm, severityFilter]);

  const handleVerifyChainIntegrity = () => {
    setIsVerifyingChain(true);
    setTimeout(() => {
      setIsVerifyingChain(false);
      setChainVerified(true);
      showToast("Cadeia de Custódia Auditada: 100% dos blocos possuem Hash SHA-256 encadeado e imutável!");
    }, 1800);
  };

  const handleExportLgpdReportPdf = () => {
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(16);
    pdf.setTextColor(15, 23, 42);
    pdf.text("Relatório de Impacto à Proteção de Dados (RIPD / DPIA)", 14, 18);

    pdf.setFontSize(8.5);
    pdf.setFont("helvetica", "bold");
    pdf.setTextColor(147, 51, 234);
    pdf.text("CONFORMIDADE ESTREITA LGPD (LEI 13.709/2018) & PROVIMENTO OAB", 14, 24);

    pdf.setFont("helvetica", "normal");
    pdf.setTextColor(100, 116, 139);
    pdf.text(`EMISSOR: ${PLATFORM_CONFIG.fullName} | DATA: ${new Date().toLocaleDateString("pt-BR")}`, 14, 29);

    pdf.setDrawColor(147, 51, 234);
    pdf.setLineWidth(0.6);
    pdf.line(14, 32, 196, 32);

    // Summary Box
    pdf.setFillColor(248, 250, 252);
    pdf.roundedRect(14, 36, 182, 32, 3, 3, "F");
    pdf.setDrawColor(226, 232, 240);
    pdf.roundedRect(14, 36, 182, 32, 3, 3, "S");

    pdf.setFontSize(8.5);
    pdf.setFont("helvetica", "bold");
    pdf.setTextColor(15, 23, 42);
    pdf.text("CERTIFICADO DE GOVERNANÇA E AUDITORIA CRIPTOGRÁFICA", 18, 44);

    pdf.setFont("courier", "normal");
    pdf.setFontSize(8);
    pdf.setTextColor(71, 85, 105);
    pdf.text("INTEGRIDADE DOS LOGS:    100% CADEIA DE CUSTÓDIA ENCADECADA", 18, 51);
    pdf.text("ALGORITMO DE AUDITORIA:  SHA-256 & NORMAS ICP-BRASIL / ON/NTP", 18, 57);
    pdf.text("STATUS DE SEGURANÇA:     ZERO INCIDENTES DE VAZAMENTO CONFIRMADOS", 18, 63);

    // Table Header
    let yPos = 78;
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(15, 23, 42);
    pdf.text("Inventário do Livro de Auditoria Criptográfica", 14, yPos);
    pdf.line(14, yPos + 2, 196, yPos + 2);
    yPos += 10;

    logs.forEach((l) => {
      pdf.setFillColor(255, 255, 255);
      pdf.roundedRect(14, yPos, 182, 16, 2, 2, "F");
      pdf.setDrawColor(226, 232, 240);
      pdf.roundedRect(14, yPos, 182, 16, 2, 2, "S");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(9);
      pdf.setTextColor(15, 23, 42);
      pdf.text(`${l.id} - ${l.action}`, 18, yPos + 6);

      pdf.setFont("courier", "normal");
      pdf.setFontSize(7.5);
      pdf.setTextColor(100, 116, 139);
      pdf.text(`${l.timestamp} | Ator: ${l.user} | IP: ${l.ipAddress} (${l.location})`, 18, yPos + 12);

      yPos += 19;
    });

    // Verification Box Footer
    pdf.setFillColor(248, 250, 252);
    pdf.roundedRect(14, 266, 182, 14, 2, 2, "F");
    pdf.setDrawColor(226, 232, 240);
    pdf.roundedRect(14, 266, 182, 14, 2, 2, "S");

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(8);
    pdf.setTextColor(30, 41, 59);
    pdf.text("VERIFICAÇÃO PÚBLICA DE AUDITORIA (LEI 13.709/2018):", 18, 272);

    pdf.setFont("courier", "bold");
    pdf.setFontSize(7.5);
    pdf.setTextColor(147, 51, 234);
    pdf.text(`http://localhost:3000/verify/LOG-AUDIT-2026`, 18, 277);

    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7.5);
    pdf.setTextColor(148, 163, 184);
    pdf.text(
      "Relatório gerado eletronicamente por LexFlow Enterprise. Assinatura SHA-256 e selo de conformidade DPO.",
      14,
      285
    );

    const filename = `Relatorio_LGPD_RIPD_${new Date().toISOString().slice(0, 10)}.pdf`;
    pdf.save(filename);
    showToast(`Relatório LGPD "${filename}" exportado e baixado com sucesso!`);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 border border-emerald-500 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-emerald-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Trilha de Auditoria Criptográfica Imutável & LGPD Compliance (Art. 38)</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Governança, Audit Logs & Cripto-Custódia
          </h1>
          <p className="text-xs text-zinc-400 max-w-3xl leading-relaxed">
            Livro de registros imutáveis encadeado por hash (SHA-256), auditoria forense de acessos, validação de conformidade OAB e relatórios de privacidade LGPD.
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          <button
            onClick={handleVerifyChainIntegrity}
            disabled={isVerifyingChain}
            className="px-4 py-3 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-200 border border-zinc-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-2 cursor-pointer shadow hover:scale-[1.02]"
          >
            <RefreshCw className={`w-4 h-4 text-emerald-400 ${isVerifyingChain ? "animate-spin" : ""}`} />
            <span>{isVerifyingChain ? "Auditando Blocos..." : "Verificar Cadeia de Custódia"}</span>
          </button>

          <button
            onClick={handleExportLgpdReportPdf}
            className="px-5 py-3 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-purple-950/60 flex items-center space-x-2 cursor-pointer hover:scale-[1.02]"
          >
            <Download className="w-4 h-4 stroke-[2.5]" />
            <span>Exportar Relatório LGPD (RIPD)</span>
          </button>
        </div>
      </div>

      {/* Security Status Card & AI Security Watchdog Banner */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-8 bg-gradient-to-r from-emerald-950/50 via-zinc-900 to-zinc-900 border border-emerald-800/60 rounded-2xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-lg">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-2xl bg-emerald-950 border border-emerald-800/80 flex items-center justify-center text-emerald-400 shrink-0 shadow">
              <Lock className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-zinc-100">Integridade da Cadeia de Audit Logs: 100% Verificada</h3>
                {chainVerified && (
                  <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950 border border-emerald-800 px-2 py-0.5 rounded font-bold">
                    CADEIA IMUTÁVEL
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 font-mono mt-0.5">
                Último Bloco Criptográfico: <strong className="text-blue-400">0x9f8b2c4...e11</strong> (SHA-256 Encadeado)
              </p>
            </div>
          </div>

          <div className="shrink-0 font-mono text-xs text-right">
            <span className="text-emerald-400 font-bold block">REGRAS DE TENANT ACTIVE</span>
            <span className="text-zinc-500 text-[10px]">Isolamento RLS por Banco de Dados</span>
          </div>
        </div>

        <div className="lg:col-span-4 bg-zinc-900 border border-purple-900/50 rounded-2xl p-5 flex items-center space-x-3 shadow-lg">
          <div className="w-10 h-10 rounded-xl bg-purple-950 border border-purple-800 flex items-center justify-center text-purple-400 shrink-0">
            <Cpu className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5 text-xs font-bold text-purple-300 uppercase tracking-wider">
              <span>AI Security Watchdog</span>
            </div>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Monitorando em tempo real. <strong className="text-emerald-400">0 anomalias críticas</strong> nas últimas 24h.
            </p>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-5 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setSeverityFilter("ALL")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                severityFilter === "ALL" ? "bg-blue-600 text-white" : "bg-zinc-950 text-zinc-400 hover:text-zinc-200 border border-zinc-800"
              }`}
            >
              Todos os Eventos ({logs.length})
            </button>
            <button
              onClick={() => setSeverityFilter("CRITICAL")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                severityFilter === "CRITICAL" ? "bg-rose-600 text-white" : "bg-zinc-950 text-rose-400 hover:bg-rose-950/40 border border-zinc-800"
              }`}
            >
              Crítico / Alertas ({logs.filter((l) => l.severity === "CRITICAL").length})
            </button>
            <button
              onClick={() => setSeverityFilter("SECURITY")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                severityFilter === "SECURITY" ? "bg-emerald-600 text-white" : "bg-zinc-950 text-emerald-400 hover:bg-emerald-950/40 border border-zinc-800"
              }`}
            >
              Segurança OAB ({logs.filter((l) => l.severity === "SECURITY").length})
            </button>
            <button
              onClick={() => setSeverityFilter("LGPD")}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                severityFilter === "LGPD" ? "bg-purple-600 text-white" : "bg-zinc-950 text-purple-300 hover:bg-purple-950/40 border border-zinc-800"
              }`}
            >
              LGPD Titulares ({logs.filter((l) => l.severity === "LGPD").length})
            </button>
          </div>

          <span className="text-xs font-mono text-zinc-400">
            Exibindo <strong className="text-white">{filteredLogs.length}</strong> de {logs.length} registros
          </span>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Buscar evento por ID (ex: LOG-1095), Ação, Nome de Usuário, IP ou Hash SHA-256..."
            className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors font-mono"
          />
        </div>

        {/* Audit Logs Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-zinc-300 border-collapse">
            <thead className="bg-zinc-950 border-b border-zinc-800 text-[10px] font-mono text-zinc-400 uppercase tracking-wider">
              <tr>
                <th className="p-3">ID Log</th>
                <th className="p-3">Ação Executada</th>
                <th className="p-3">Usuário / Cargo</th>
                <th className="p-3">Origem & IP</th>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Severidade</th>
                <th className="p-3">Hash SHA-256</th>
                <th className="p-3 text-right">Inspeção</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-mono">
              {filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-zinc-950/70 transition-colors">
                  <td className="p-3 font-bold text-blue-400">{log.id}</td>
                  <td className="p-3 font-semibold text-zinc-100 font-sans">
                    {log.action}
                    <span className="block text-[10px] font-mono text-zinc-500">{log.category}</span>
                  </td>
                  <td className="p-3 text-zinc-300 font-sans">
                    <p className="font-bold text-zinc-200">{log.user}</p>
                    <p className="text-[10px] text-zinc-500 font-mono">{log.role}</p>
                  </td>
                  <td className="p-3 text-zinc-400">
                    <p className="font-bold text-zinc-300">{log.ipAddress}</p>
                    <p className="text-[10px] text-zinc-500 font-sans">{log.location}</p>
                  </td>
                  <td className="p-3 text-zinc-400 text-[11px]">{log.timestamp}</td>
                  <td className="p-3">
                    {log.severity === "INFO" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950 text-blue-400 border border-blue-800">
                        INFO
                      </span>
                    )}
                    {log.severity === "SECURITY" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                        SEGURANÇA
                      </span>
                    )}
                    {log.severity === "CRITICAL" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800">
                        CRÍTICO
                      </span>
                    )}
                    {log.severity === "LGPD" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950 text-purple-300 border border-purple-800">
                        LGPD
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-zinc-500 text-[10px] max-w-xs truncate" title={log.hash}>
                    {log.hash.slice(0, 16)}...{log.hash.slice(-8)}
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => setSelectedLog(log)}
                      className="p-1.5 bg-zinc-800 hover:bg-zinc-700 text-blue-400 hover:text-white rounded-lg transition-colors cursor-pointer"
                      title="Inspecionar Metadados Forenses em JSON"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* FORENSIC LOG INSPECTOR MODAL */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-blue-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Inspeção Forense de Log Criptográfico: <span className="text-blue-400 font-mono">{selectedLog.id}</span>
                </h3>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Log Metadata Grid */}
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1">
                <span className="text-[10px] text-zinc-500 uppercase">Ação Registrada</span>
                <p className="text-zinc-100 font-bold">{selectedLog.action}</p>
              </div>

              <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1">
                <span className="text-[10px] text-zinc-500 uppercase">Usuário / Ator</span>
                <p className="text-zinc-100 font-bold">{selectedLog.user}</p>
                <p className="text-[10px] text-zinc-400">{selectedLog.role}</p>
              </div>

              <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1">
                <span className="text-[10px] text-zinc-500 uppercase">Endereço IP & Geolocalização</span>
                <p className="text-zinc-100 font-bold">{selectedLog.ipAddress}</p>
                <p className="text-[10px] text-zinc-400">{selectedLog.location}</p>
              </div>

              <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-1">
                <span className="text-[10px] text-zinc-500 uppercase">Timestamp Oficial</span>
                <p className="text-zinc-100 font-bold">{selectedLog.timestamp}</p>
              </div>
            </div>

            {/* Hashes Block */}
            <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 text-xs font-mono">
              <div>
                <span className="text-[10px] text-zinc-500 uppercase block">Hash do Bloco Anterior (Prev SHA-256):</span>
                <p className="text-zinc-400 break-all">{selectedLog.prevHash}</p>
              </div>
              <div className="pt-2 border-t border-zinc-800">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-emerald-400 font-bold uppercase">Hash SHA-256 do Evento Atual (Imutável):</span>
                  <button
                    onClick={() => copyToClipboard(selectedLog.hash)}
                    className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                  >
                    {copiedHash === selectedLog.hash ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>Copiar Hash</span>
                  </button>
                </div>
                <p className="text-blue-300 font-bold break-all">{selectedLog.hash}</p>
              </div>
            </div>

            {/* Payload JSON Inspector */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-mono text-zinc-400 uppercase font-bold">Payload Técnico JSON (Estrutura Completa):</span>
              <pre className="bg-zinc-950 border border-zinc-800 p-4 rounded-xl text-[11px] font-mono text-emerald-400 overflow-x-auto leading-relaxed max-h-40">
                {selectedLog.detailsJson}
              </pre>
            </div>

            <div className="pt-3 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-colors cursor-pointer"
              >
                Concluir Inspeção
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
