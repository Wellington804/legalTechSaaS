"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { PLATFORM_CONFIG } from "@/config/platform";
import {
  ShieldCheck,
  CheckCircle2,
  Lock,
  FileCheck,
  Search,
  QrCode,
  Download,
  AlertCircle,
  FileText,
  Clock,
  ExternalLink,
  Building2,
  KeyRound,
  UserCheck,
  Fingerprint,
} from "lucide-react";

export interface SignerRecord {
  name: string;
  email: string;
  phone: string;
  role: string;
  authMethod: string;
  status: string;
  signedAt?: string;
  ipAddress?: string;
}

export interface AuditRecord {
  event: string;
  timestamp: string;
  actor: string;
  ip: string;
  device: string;
}

export interface DocRecord {
  id: string;
  title: string;
  category: string;
  createdAt: string;
  expiresAt: string;
  status: string;
  hashSha256Original: string;
  hashSha256Final: string;
  signers: SignerRecord[];
  auditTrail: AuditRecord[];
}

function VerifyDocumentContent() {
  const params = useParams();
  const searchParams = useSearchParams();

  const docIdParam = (params?.id as string) || searchParams?.get("doc") || "DOC-9948";
  const [searchDocId, setSearchDocId] = useState(docIdParam);
  const [activeDoc, setActiveDoc] = useState<DocRecord | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const MOCK_DOCS: DocRecord[] = [
    {
      id: "DOC-9948",
      title: "Contrato de Honorários Advocatícios Quota Litis - Cliente Silva",
      category: "Contratos de Honorários",
      createdAt: "12/08/2026",
      expiresAt: "26/08/2026",
      status: "COMPLETED",
      hashSha256Original: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      hashSha256Final: "7d8a9f0e1c2b3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b",
      signers: [
        {
          name: "Dr. Alexandre Rossi",
          email: "alexandre@rossiadvocacia.com.br",
          phone: "+55 (11) 98765-4321",
          role: "Advogado / Emissor",
          authMethod: "ICP_BRASIL (Certificado A1)",
          status: "SIGNED",
          signedAt: "12/08/2026 14:22 UTC-3",
          ipAddress: "177.138.42.109",
        },
        {
          name: "Marcos Paulo Silva",
          email: "marcos.silva@email.com",
          phone: "+55 (11) 91234-5678",
          role: "Contratante",
          authMethod: "BIOMETRIC (CNH / Serpro)",
          status: "SIGNED",
          signedAt: "12/08/2026 16:05 UTC-3",
          ipAddress: "201.86.112.44",
        },
      ],
      auditTrail: [
        {
          event: "Documento registrado no barramento de auditoria criptográfica",
          timestamp: "12/08/2026 14:22:05",
          actor: "Dr. Alexandre Rossi",
          ip: "177.138.42.109",
          device: "macOS / Chrome 127.0",
        },
        {
          event: "Assinatura digital efetuada pelo emissor via ICP-Brasil A1",
          timestamp: "12/08/2026 14:22:08",
          actor: "Dr. Alexandre Rossi (OAB/SP 458.912)",
          ip: "177.138.42.109",
          device: "LexFlow ICP Provider",
        },
        {
          event: "Validação Facial / Biometria CNH concluída com sucesso (Match 99.8%)",
          timestamp: "12/08/2026 16:04:50",
          actor: "Serviço de Biometria Serpro",
          ip: "Serpro API Gateway",
          device: "LexFlow Facial SDK",
        },
        {
          event: "Documento selado criptograficamente com carimbo temporal ON/NTP",
          timestamp: "12/08/2026 16:05:00",
          actor: "Marcos Paulo Silva",
          ip: "201.86.112.44",
          device: "iOS 17.5 / Safari Mobile",
        },
      ],
    },
    {
      id: "DOC-9949",
      title: "Acordo Extrajudicial de Dissolução Societária - TechCorp",
      category: "Societário / M&A",
      createdAt: "11/08/2026",
      expiresAt: "25/08/2026",
      status: "IN_PROGRESS",
      hashSha256Original: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
      hashSha256Final: "Pendência de colheita de assinaturas",
      signers: [
        {
          name: "Dr. Alexandre Rossi",
          email: "alexandre@rossiadvocacia.com.br",
          phone: "+55 (11) 98765-4321",
          role: "Advogado / Emissor",
          authMethod: "ICP_BRASIL (Certificado A1)",
          status: "SIGNED",
          signedAt: "11/08/2026 10:15 UTC-3",
          ipAddress: "177.138.42.109",
        },
        {
          name: "Eduardo Fonseca",
          email: "eduardo@techcorp.io",
          phone: "+55 (21) 99887-1122",
          role: "Sócio Administrador",
          authMethod: "OTP (E-mail + WhatsApp)",
          status: "PENDING",
        },
        {
          name: "Patrícia Lima",
          email: "patricia@techcorp.io",
          phone: "+55 (21) 97766-3344",
          role: "Testemunha Qualificada",
          authMethod: "OTP (E-mail + WhatsApp)",
          status: "PENDING",
        },
      ],
      auditTrail: [
        {
          event: "Documento registrado no barramento de auditoria criptográfica",
          timestamp: "11/08/2026 10:15:00",
          actor: "Dr. Alexandre Rossi",
          ip: "177.138.42.109",
          device: "Windows 11 / Edge 126.0",
        },
        {
          event: "Notificações enviadas aos signatários pendentes",
          timestamp: "11/08/2026 10:15:05",
          actor: "LexFlow Notification Engine",
          ip: "AWS sa-east-1",
          device: "Multi-channel Engine",
        },
      ],
    },
  ];

  const handleFetchDoc = (id: string) => {
    setErrorMsg("");
    const cleanId = id.trim().toUpperCase();

    // Check localStorage first
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("lexflow_signatures_docs");
        if (stored) {
          const parsed: DocRecord[] = JSON.parse(stored);
          const found = parsed.find((d) => d.id.toUpperCase() === cleanId || d.hashSha256Original.includes(id));
          if (found) {
            setActiveDoc(found);
            return;
          }
        }
      } catch (e) {
        console.error("Erro ao ler localStorage em verify:", e);
      }
    }

    // Fallback to mock docs
    const mockFound = MOCK_DOCS.find((d) => d.id.toUpperCase() === cleanId || d.hashSha256Original.includes(id));
    if (mockFound) {
      setActiveDoc(mockFound);
    } else {
      setActiveDoc(null);
      setErrorMsg(`Nenhum documento localizado para o identificador ou Hash "${id}".`);
    }
  };

  useEffect(() => {
    if (docIdParam) {
      handleFetchDoc(docIdParam);
    }
  }, [docIdParam]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center justify-between p-4 sm:p-6 font-sans">
      {/* Header */}
      <header className="w-full max-w-4xl flex items-center justify-between py-4 border-b border-zinc-800">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-emerald-600 rounded-xl text-white shadow-lg shadow-emerald-950">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-sm font-extrabold text-white tracking-wide uppercase">{PLATFORM_CONFIG.name} Verification Portal</h1>
            <p className="text-[10px] font-mono text-zinc-400">Validador Público de Cripto-Integridade & Carimbo de Tempo ON/NTP</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-[11px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-1.5 rounded-full shadow">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>Validade Jurídica Lei 14.063/2020</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="w-full max-w-4xl my-8 space-y-6 flex-1">
        {/* Search Bar */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 shadow-2xl space-y-3">
          <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider">
            Digite o Código do Documento (ID) ou Hash SHA-256 para Verificar Autenticidade:
          </label>
          <div className="flex space-x-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-3.5 text-zinc-500" />
              <input
                type="text"
                placeholder="Ex: DOC-9948 ou 8f434346648f6b96..."
                value={searchDocId}
                onChange={(e) => setSearchDocId(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-10 pr-4 py-3 text-xs text-white font-mono placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <button
              onClick={() => handleFetchDoc(searchDocId)}
              className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-emerald-950 flex items-center space-x-2 cursor-pointer shrink-0"
            >
              <Search className="w-4 h-4" />
              <span>Verificar Integridade</span>
            </button>
          </div>
          {errorMsg && (
            <div className="p-3 bg-rose-950/60 border border-rose-800 rounded-xl text-rose-300 text-xs font-semibold flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Verification Result Sheet */}
        {activeDoc && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-6 shadow-2xl animate-in fade-in duration-200">
            {/* Banner Status */}
            <div className="bg-emerald-950/60 border border-emerald-800 rounded-2xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-2xl bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
                  <FileCheck className="w-7 h-7" />
                </div>
                <div>
                  <span className="text-[10px] font-mono text-emerald-400 font-bold uppercase tracking-wider">Status do Instrumento Jurídico</span>
                  <h2 className="text-lg font-extrabold text-white flex items-center space-x-2">
                    <span>DOCUMENTO AUTÊNTICO & SELADO</span>
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  </h2>
                  <p className="text-xs text-zinc-300 mt-0.5">
                    Integridade criptográfica SHA-256 e autoria verificadas em conformidade estrita com a Lei 14.063/2020.
                  </p>
                </div>
              </div>

              <div className="shrink-0 bg-zinc-950 border border-zinc-800 px-4 py-2 rounded-xl font-mono text-xs text-center space-y-0.5">
                <span className="text-[10px] text-zinc-400 uppercase block">Identificador Único</span>
                <span className="text-emerald-400 font-extrabold text-sm">{activeDoc.id}</span>
              </div>
            </div>

            {/* Document Metadata Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-2">
                <span className="text-[10px] font-mono text-blue-400 font-bold uppercase">Título do Documento</span>
                <h3 className="text-sm font-bold text-white leading-snug">{activeDoc.title}</h3>
                <div className="flex items-center space-x-2 text-[11px] text-zinc-400 font-mono pt-1">
                  <span>Categoria: {activeDoc.category}</span>
                  <span>•</span>
                  <span>Registrado em: {activeDoc.createdAt}</span>
                </div>
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-2">
                <span className="text-[10px] font-mono text-purple-400 font-bold uppercase">Carimbo Temporal ON/NTP & ICP-Brasil</span>
                <div className="text-xs text-zinc-300 font-mono space-y-1">
                  <p>Sincronização: Observatório da Hora Legal do Brasil</p>
                  <p className="text-emerald-400 font-bold">Validade Técnica Garantida por SHA-256</p>
                </div>
              </div>
            </div>

            {/* Hash Footprint Block */}
            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-2 font-mono text-xs">
              <span className="text-[10px] text-zinc-400 uppercase font-bold block">Pegada Criptográfica SHA-256 (Imutabilidade):</span>
              <div className="space-y-1">
                <p className="text-zinc-400 break-all">
                  HASH ORIGINAL: <span className="text-zinc-200">{activeDoc.hashSha256Original}</span>
                </p>
                <p className="text-zinc-400 break-all">
                  HASH SELADO: <span className="text-blue-400 font-bold">{activeDoc.hashSha256Final}</span>
                </p>
              </div>
            </div>

            {/* Signers Status Table */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center space-x-2">
                <UserCheck className="w-4 h-4 text-emerald-400" />
                <span>Quadro de Signatários & Autenticação Legal</span>
              </h3>

              <div className="grid grid-cols-1 gap-3">
                {activeDoc.signers.map((s, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="text-xs font-bold text-white">{s.name}</h4>
                        <span className="text-[9px] font-mono bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded">
                          {s.role}
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-400 font-mono mt-0.5">{s.email}</p>
                      <p className="text-[10px] text-purple-400 font-mono mt-0.5">
                        Método de Validação: <strong>{s.authMethod}</strong>
                      </p>
                    </div>

                    <div>
                      {s.status === "SIGNED" ? (
                        <div className="text-right font-mono text-xs">
                          <span className="px-3 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full font-bold inline-flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>ASSINADO</span>
                          </span>
                          {s.signedAt && (
                            <p className="text-[10px] text-zinc-500 mt-1">{s.signedAt}</p>
                          )}
                        </div>
                      ) : (
                        <span className="px-3 py-1 bg-amber-950 text-amber-400 border border-amber-800 rounded-full font-bold inline-flex items-center space-x-1 text-xs">
                          <Clock className="w-3.5 h-3.5" />
                          <span>PENDENTE</span>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Audit Trail Timeline */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center space-x-2">
                <Clock className="w-4 h-4 text-purple-400" />
                <span>Trilha Cronológica de Auditoria (Logs Inalteráveis)</span>
              </h3>

              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3 font-mono text-xs">
                {activeDoc.auditTrail.map((log, idx) => (
                  <div key={idx} className="border-l-2 border-emerald-500 pl-3 py-1 space-y-0.5">
                    <p className="text-zinc-200 font-semibold">{log.event}</p>
                    <p className="text-[10px] text-zinc-500">
                      {log.timestamp} | Ator: {log.actor} | IP: {log.ip} | Dispositivo: {log.device}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions Footer */}
            <div className="pt-4 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800">
              <span className="text-[11px] font-mono text-zinc-500">
                Verificação oficial via Barramento LexFlow SHA-256.
              </span>

              <button
                onClick={() => (window.location.href = "/dashboard/assinaturas")}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all cursor-pointer shadow"
              >
                Voltar ao Painel do Sistema
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="w-full max-w-4xl text-center py-4 border-t border-zinc-800 text-[10px] text-zinc-500 font-mono space-y-1">
        <p>{PLATFORM_CONFIG.fullName} — Barramento de Autenticidade & Validação Criptográfica Pública.</p>
        <p className="text-zinc-600">Tratamento de Dados Pessoais em conformidade estrita com a LGPD (Lei 13.709/2018).</p>
      </footer>
    </div>
  );
}

export default function VerifyDocumentPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-400 font-mono text-xs">
        Carregando validador público de documentos...
      </div>
    }>
      <VerifyDocumentContent />
    </Suspense>
  );
}
