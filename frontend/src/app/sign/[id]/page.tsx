"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { PLATFORM_CONFIG } from "@/config/platform";
import {
  FileSignature,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Clock,
  Sparkles,
  Smartphone,
  Mail,
  QrCode,
  Download,
  AlertCircle,
  Camera,
  Edit3,
  RotateCcw,
  UserCheck,
  Fingerprint,
  KeyRound,
  ShieldAlert,
  Search,
  Building2,
  X,
} from "lucide-react";

export interface SignerInfo {
  name: string;
  email: string;
  role: string;
  authMethod: "OTP" | "BIOMETRIC" | "ICP_BRASIL";
  status: "SIGNED" | "PENDING";
  signedAt?: string;
}

function SignDocumentContent() {
  const params = useParams();
  const searchParams = useSearchParams();

  const docId = (params?.id as string) || "DOC-9949";
  const tokenParam = searchParams?.get("token");
  const signerParam = searchParams?.get("signer");

  const [step, setStep] = useState<"VIEW" | "AUTH" | "SIGN" | "SUCCESS">("VIEW");
  const [authMethod, setAuthMethod] = useState<"OTP" | "BIOMETRIC" | "GOV_BR">("OTP");
  const [otpCode, setOtpCode] = useState("");
  const [typedSignature, setTypedSignature] = useState("");
  const [isBiometricVerified, setIsBiometricVerified] = useState(false);
  const [isGovBrVerified, setIsGovBrVerified] = useState(false);
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Identity Lookup State (for direct URL access without token)
  const [lookupEmail, setLookupEmail] = useState("");
  const [lookupError, setLookupError] = useState("");
  const [isTokenLocked, setIsTokenLocked] = useState(false);

  // Document Signers List (Partes do Documento)
  const [signers, setSigners] = useState<SignerInfo[]>([
    {
      name: "Dr. Alexandre Rossi",
      email: "alexandre@rossiadvocacia.com.br",
      role: "Advogado / Emissor",
      authMethod: "ICP_BRASIL",
      status: "SIGNED",
      signedAt: "11/08/2026 10:15 UTC-3",
    },
    {
      name: "Eduardo Fonseca",
      email: "eduardo@techcorp.io",
      role: "Sócio Administrador",
      authMethod: "OTP",
      status: "PENDING",
    },
    {
      name: "Patrícia Lima",
      email: "patricia@techcorp.io",
      role: "Testemunha Qualificada",
      authMethod: "OTP",
      status: "PENDING",
    },
  ]);

  // Selected Signer State
  const [selectedSignerIndex, setSelectedSignerIndex] = useState<number | null>(null);

  // Helper to decode token or email parameter
  useEffect(() => {
    let targetEmail = "";
    if (signerParam) {
      targetEmail = decodeURIComponent(signerParam).toLowerCase();
    } else if (tokenParam) {
      try {
        targetEmail = atob(tokenParam).toLowerCase();
      } catch {
        targetEmail = decodeURIComponent(tokenParam).toLowerCase();
      }
    }

    if (targetEmail) {
      const idx = signers.findIndex((s) => s.email.toLowerCase() === targetEmail);
      if (idx !== -1) {
        setSelectedSignerIndex(idx);
        setIsTokenLocked(true);
        setTypedSignature(signers[idx].name);
        return;
      }
    }

    // Default: if no valid token/signer param, do NOT select any signer by default
    setSelectedSignerIndex(null);
    setIsTokenLocked(false);
  }, [tokenParam, signerParam, signers]);

  const activeSigner = selectedSignerIndex !== null ? signers[selectedSignerIndex] : null;

  // Document Info
  const docInfo = {
    id: docId,
    title:
      docId === "DOC-9948"
        ? "Contrato de Honorários Advocatícios Quota Litis - Cliente Silva"
        : "Acordo Extrajudicial de Dissolução Societária - TechCorp",
    category: "Societário / M&A",
    issuer: "Dr. Alexandre Rossi (OAB/SP 458.912)",
    hashOriginal: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
  };

  const handleLookupIdentity = (e: React.FormEvent) => {
    e.preventDefault();
    setLookupError("");

    const cleanInput = lookupEmail.trim().toLowerCase();
    if (!cleanInput) {
      setLookupError("Informe seu e-mail cadastrado para prosseguir.");
      return;
    }

    const idx = signers.findIndex((s) => s.email.toLowerCase() === cleanInput);
    if (idx === -1) {
      setLookupError(`Nenhum signatário localizado para "${lookupEmail}". Verifique o e-mail cadastrado no contrato.`);
      return;
    }

    setSelectedSignerIndex(idx);
    setTypedSignature(signers[idx].name);
  };

  const handleSimulateBiometric = () => {
    setIsBiometricVerified(true);
  };

  const handleCompleteSigning = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedSignerIndex === null || !activeSigner) return;
    setIsSubmitting(true);

    setTimeout(() => {
      // Mark ONLY the selected signer as SIGNED
      setSigners((prev) =>
        prev.map((s, idx) => {
          if (idx === selectedSignerIndex) {
            return {
              ...s,
              status: "SIGNED",
              signedAt: new Date().toLocaleString("pt-BR") + " UTC-3",
            };
          }
          return s;
        })
      );

      // Persist status change in localStorage
      if (typeof window !== "undefined") {
        try {
          const stored = localStorage.getItem("lexflow_signatures_docs");
          if (stored) {
            const docs: any[] = JSON.parse(stored);
            const updatedDocs = docs.map((doc) => {
              if (doc.id === docId) {
                const updatedSigners = doc.signers.map((s: any) => {
                  if (s.email.toLowerCase() === activeSigner.email.toLowerCase()) {
                    return {
                      ...s,
                      status: "SIGNED",
                      signedAt: new Date().toLocaleString("pt-BR") + " UTC-3",
                      ipAddress: "177.138.42.109",
                    };
                  }
                  return s;
                });

                const allSigned = updatedSigners.every((s: any) => s.status === "SIGNED");

                return {
                  ...doc,
                  status: allSigned ? "COMPLETED" : "IN_PROGRESS",
                  signers: updatedSigners,
                  auditTrail: [
                    ...doc.auditTrail,
                    {
                      event: `Assinatura digital efetuada por ${activeSigner.name} (${activeSigner.email})`,
                      timestamp: new Date().toLocaleString("pt-BR"),
                      actor: activeSigner.name,
                      ip: "177.138.42.109",
                      device: "LexFlow Portal Seguro de Assinaturas",
                    },
                  ],
                };
              }
              return doc;
            });
            localStorage.setItem("lexflow_signatures_docs", JSON.stringify(updatedDocs));
          }
        } catch (err) {
          console.error("Erro ao sincronizar localStorage no portal público:", err);
        }
      }

      setIsSubmitting(false);
      setStep("SUCCESS");
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center justify-between p-4 sm:p-6 font-sans">
      {/* Top Header Bar */}
      <header className="w-full max-w-4xl flex items-center justify-between py-4 border-b border-zinc-800">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-blue-600 rounded-xl text-white">
            <FileSignature className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-sm font-extrabold text-white tracking-wide uppercase">{PLATFORM_CONFIG.name} Portal</h1>
            <p className="text-[10px] font-mono text-zinc-400">Assinatura Eletrônica Certificada & Trilha Digital</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-[11px] font-mono text-purple-400 bg-purple-950/60 border border-purple-800/80 px-3 py-1.5 rounded-full">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Lei 14.063/2020 & ICP-Brasil</span>
          <span className="sm:hidden">ICP-Brasil</span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="w-full max-w-3xl my-8 space-y-6 flex-1">
        {/* Step Indicator */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 flex items-center justify-between text-xs font-bold">
          <div className={`flex items-center space-x-2 ${step === "VIEW" ? "text-blue-400" : "text-emerald-400"}`}>
            <span className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center text-xs">1</span>
            <span>Identificação & Documento</span>
          </div>
          <div className={`flex items-center space-x-2 ${step === "AUTH" ? "text-blue-400" : step === "SIGN" || step === "SUCCESS" ? "text-emerald-400" : "text-zinc-600"}`}>
            <span className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center text-xs">2</span>
            <span>Autenticação</span>
          </div>
          <div className={`flex items-center space-x-2 ${step === "SIGN" ? "text-blue-400" : step === "SUCCESS" ? "text-emerald-400" : "text-zinc-600"}`}>
            <span className="w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center text-xs">3</span>
            <span>Assinatura Única</span>
          </div>
        </div>

        {/* STEP 1: DOCUMENT READING & SIGNER IDENTIFICATION */}
        {step === "VIEW" && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6 shadow-2xl animate-in fade-in duration-200">
            <div className="border-b border-zinc-800 pb-4 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-blue-400 uppercase font-bold tracking-wider">Identificador {docInfo.id}</span>
                {isTokenLocked && (
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-800 px-2.5 py-1 rounded-full flex items-center space-x-1">
                    <KeyRound className="w-3 h-3 text-emerald-400" />
                    <span>Link Tokenizado Autenticado</span>
                  </span>
                )}
              </div>
              <h2 className="text-xl font-extrabold text-white">{docInfo.title}</h2>
              <p className="text-xs text-zinc-400">Emissor: {docInfo.issuer}</p>
            </div>

            {/* SECURE IDENTITY CARD OR LOOKUP FORM */}
            {activeSigner ? (
              <div className="bg-zinc-950 border border-blue-900/60 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                  <div className="flex items-center space-x-2 text-xs font-bold text-blue-300 uppercase tracking-wider">
                    <UserCheck className="w-4 h-4 text-blue-400" />
                    <span>Signatário Identificado</span>
                  </div>
                  {isTokenLocked ? (
                    <span className="text-[9px] font-mono text-blue-400 bg-blue-950 border border-blue-800 px-2 py-0.5 rounded">
                      🔒 Perfil Travado por Token
                    </span>
                  ) : (
                    <button
                      onClick={() => setSelectedSignerIndex(null)}
                      className="text-[10px] text-zinc-400 hover:text-white underline"
                    >
                      Alterar e-mail
                    </button>
                  )}
                </div>

                <div className="flex items-center justify-between p-3 bg-zinc-900/90 border border-zinc-800 rounded-lg">
                  <div>
                    <h4 className="text-sm font-bold text-white">{activeSigner.name}</h4>
                    <p className="text-xs text-zinc-400">{activeSigner.email}</p>
                    <p className="text-[10px] font-mono text-blue-400 mt-0.5">Papel: {activeSigner.role}</p>
                  </div>
                  <div>
                    {activeSigner.status === "SIGNED" ? (
                      <span className="px-3 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full text-xs font-bold flex items-center space-x-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>ASSINADO</span>
                      </span>
                    ) : (
                      <span className="px-3 py-1 bg-amber-950 text-amber-400 border border-amber-800 rounded-full text-xs font-bold flex items-center space-x-1">
                        <Clock className="w-3.5 h-3.5" />
                        <span>PENDENTE</span>
                      </span>
                    )}
                  </div>
                </div>

                {activeSigner.status === "SIGNED" && (
                  <p className="text-[11px] text-emerald-400 bg-emerald-950/40 p-2.5 rounded-lg border border-emerald-900/50 text-center font-mono">
                    Sua assinatura já foi colhida em {activeSigner.signedAt}.
                  </p>
                )}
              </div>
            ) : (
              <form onSubmit={handleLookupIdentity} className="bg-zinc-950 border border-amber-900/40 p-5 rounded-xl space-y-4">
                <div className="flex items-center space-x-2 text-xs font-bold text-amber-300 uppercase tracking-wider">
                  <Lock className="w-4 h-4 text-amber-400" />
                  <span>Autenticação Obrigatória de Signatário</span>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  Para garantir que o documento seja assinado exclusivamente pela pessoa autorizada (Lei 14.063/2020), informe seu **E-mail cadastrado**:
                </p>

                <div className="space-y-2">
                  <div className="flex space-x-2">
                    <div className="relative flex-1">
                      <Mail className="w-4 h-4 absolute left-3 top-3 text-zinc-500" />
                      <input
                        type="email"
                        required
                        placeholder="seu.email@empresa.com"
                        value={lookupEmail}
                        onChange={(e) => setLookupEmail(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-9 pr-4 py-2.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <button
                      type="submit"
                      className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all shadow flex items-center space-x-1.5 cursor-pointer shrink-0"
                    >
                      <Search className="w-3.5 h-3.5" />
                      <span>Verificar Pendência</span>
                    </button>
                  </div>
                  {lookupError && (
                    <div className="text-[11px] text-rose-400 font-semibold flex items-center space-x-1 pt-1">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      <span>{lookupError}</span>
                    </div>
                  )}
                </div>
              </form>
            )}

            {/* AI Clause Summary & Document Sheet Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">Conteúdo do Instrumento Jurídico</span>
              <button
                type="button"
                onClick={() => setIsAiModalOpen(true)}
                className="px-3.5 py-1.5 bg-purple-950/70 hover:bg-purple-900/80 border border-purple-700/60 text-purple-200 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 cursor-pointer shadow"
              >
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>Analisar Cláusulas com IA (Visual Law & Riscos)</span>
              </button>
            </div>

            {/* Simulated Document Sheet */}
            <div className="bg-zinc-950 border border-zinc-800 p-6 rounded-xl space-y-4 font-serif text-xs text-zinc-300 leading-relaxed max-h-60 overflow-y-auto">
              <p className="text-[10px] text-zinc-500 font-mono">HASH SHA-256 DO DOCUMENTO: {docInfo.hashOriginal}</p>
              <h3 className="font-sans font-bold text-zinc-100 text-sm border-b border-zinc-800 pb-2">CLÁUSULAS DO CONTRATO</h3>
              <p>
                Pelo presente instrumento particular, de um lado o contratante qualificado e de outro o escritório advocatício emissor, pactuam as obrigações e condições pactuadas.
              </p>
              <p>
                As partes declaram ciência integral das obrigações, prazos e condições estabelecidas, anuindo expressamente com o formato de assinatura eletrônica individual mediante verificação biométrica ou código OTP nos termos da Lei 14.063/2020 e LGPD.
              </p>
            </div>

            {activeSigner && (
              <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
                <span className="text-xs font-mono text-zinc-500">
                  Sessão ativa: <strong className="text-blue-400">{activeSigner.name}</strong>
                </span>
                <button
                  onClick={() => {
                    setTypedSignature(activeSigner.name);
                    setStep("AUTH");
                  }}
                  disabled={activeSigner.status === "SIGNED"}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-blue-950 flex items-center space-x-2 cursor-pointer"
                >
                  <span>Li e Concordo — Avançar como {activeSigner.name.split(" ")[0]}</span>
                  <ShieldCheck className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* STEP 2: AUTHENTICATION */}
        {step === "AUTH" && activeSigner && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6 shadow-2xl animate-in fade-in duration-200">
            <div className="space-y-1 border-b border-zinc-800 pb-3">
              <span className="text-[10px] font-mono text-blue-400 uppercase font-bold">Validação da Parte: {activeSigner.name}</span>
              <h2 className="text-lg font-extrabold text-white">Escolha o Método de Validação de Identidade</h2>
              <p className="text-xs text-zinc-400">Exigido pela Lei 14.063/2020 para comprovação da autoria da assinatura de {activeSigner.name}.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setAuthMethod("OTP")}
                className={`p-4 rounded-xl border text-left transition-all cursor-pointer ${
                  authMethod === "OTP" ? "bg-blue-950/60 border-blue-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                <div className="flex items-center space-x-2 text-blue-400 font-bold text-xs mb-1">
                  <Smartphone className="w-4 h-4" />
                  <span>OTP WhatsApp / E-mail</span>
                </div>
                <p className="text-[11px] text-zinc-400">Código individual enviado a {activeSigner.email}.</p>
              </button>

              <button
                type="button"
                onClick={() => setAuthMethod("BIOMETRIC")}
                className={`p-4 rounded-xl border text-left transition-all cursor-pointer ${
                  authMethod === "BIOMETRIC" ? "bg-purple-950/60 border-purple-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                <div className="flex items-center space-x-2 text-purple-400 font-bold text-xs mb-1">
                  <Camera className="w-4 h-4" />
                  <span>Biometria Facial Serpro</span>
                </div>
                <p className="text-[11px] text-zinc-400">Validação facial com CNH de {activeSigner.name}.</p>
              </button>

              <button
                type="button"
                onClick={() => setAuthMethod("GOV_BR")}
                className={`p-4 rounded-xl border text-left transition-all cursor-pointer ${
                  authMethod === "GOV_BR" ? "bg-emerald-950/60 border-emerald-500 text-white" : "bg-zinc-950 border-zinc-800 text-zinc-400"
                }`}
              >
                <div className="flex items-center space-x-2 text-emerald-400 font-bold text-xs mb-1">
                  <Building2 className="w-4 h-4" />
                  <span>Assinatura Gov.br (Prata/Ouro)</span>
                </div>
                <p className="text-[11px] text-zinc-400">Autenticação oficial Gov.br (Lei 14.063/2020).</p>
              </button>
            </div>

            {authMethod === "OTP" && (
              <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-xl space-y-3">
                <label className="block text-xs font-bold text-zinc-300">Digite o Código OTP Enviado a {activeSigner.name} (6 dígitos):</label>
                <div className="flex space-x-2">
                  <input
                    type="text"
                    maxLength={6}
                    placeholder="948201"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    className="w-full max-w-xs bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 text-base font-mono text-center tracking-widest text-white focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => setOtpCode("948201")}
                    className="px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold"
                  >
                    Auto-Preencher
                  </button>
                </div>
              </div>
            )}

            {authMethod === "BIOMETRIC" && (
              <div className="bg-zinc-950 border border-purple-900/60 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-purple-300 uppercase">Validação de Liveness & Biometria CNH</span>
                  {isBiometricVerified && (
                    <span className="text-xs font-mono text-emerald-400 font-bold flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>FACE MATCH 99.8%</span>
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleSimulateBiometric}
                  className={`w-full py-3 rounded-xl text-xs font-bold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                    isBiometricVerified ? "bg-emerald-600 text-white" : "bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-950"
                  }`}
                >
                  <Camera className="w-4 h-4" />
                  <span>{isBiometricVerified ? "Biometria Validada com Sucesso!" : "Iniciar Captura Facial de Liveness"}</span>
                </button>
              </div>
            )}

            {authMethod === "GOV_BR" && (
              <div className="bg-zinc-950 border border-emerald-900/60 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Building2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold text-emerald-300 uppercase">Conexão Oficial Gov.br (Lei 14.063/2020)</span>
                  </div>
                  {isGovBrVerified && (
                    <span className="text-xs font-mono text-emerald-400 font-bold flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>NÍVEL PRATA/OURO CONFIRMADO</span>
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-400">
                  O signatário será autenticado com a conta oficial do Governo Federal, emitindo certificado digital avançado.
                </p>
                <button
                  type="button"
                  onClick={() => setIsGovBrVerified(true)}
                  className={`w-full py-3 rounded-xl text-xs font-bold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                    isGovBrVerified ? "bg-emerald-600 text-white" : "bg-emerald-700 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-950"
                  }`}
                >
                  <ShieldCheck className="w-4 h-4" />
                  <span>{isGovBrVerified ? "Identidade Gov.br Confirmada com Sucesso!" : "Autenticar via Login Gov.br (CPF do Signatário)"}</span>
                </button>
              </div>
            )}

            {authMethod === "BIOMETRIC" && (
              <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-xl text-center space-y-3">
                {isBiometricVerified ? (
                  <div className="p-3 bg-emerald-950/80 border border-emerald-800 rounded-xl text-emerald-300 text-xs font-bold flex items-center justify-center space-x-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>Biometria Facial de {activeSigner.name} Verificada com Sucesso (Match 99.8%)!</span>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={handleSimulateBiometric}
                    className="px-5 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold transition-all shadow flex items-center space-x-2 mx-auto cursor-pointer"
                  >
                    <Camera className="w-4 h-4" />
                    <span>Iniciar Leitura Facial da Câmera</span>
                  </button>
                )}
              </div>
            )}

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setStep("VIEW")}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold"
              >
                Voltar à Seleção
              </button>

              <button
                type="button"
                disabled={authMethod === "OTP" ? !otpCode.trim() : !isBiometricVerified}
                onClick={() => setStep("SIGN")}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all shadow"
              >
                Validar Identidade & Prosseguir
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: SIGNATURE COLLECTION */}
        {step === "SIGN" && activeSigner && (
          <form onSubmit={handleCompleteSigning} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-6 shadow-2xl animate-in fade-in duration-200">
            <div className="space-y-1">
              <h2 className="text-lg font-extrabold text-white">Assinatura Eletrônica de {activeSigner.name}</h2>
              <p className="text-xs text-zinc-400">Confirme o nome completo para selar a assinatura no acervo digital.</p>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider">Nome Completo do Signatário *</label>
              <input
                type="text"
                required
                value={typedSignature}
                onChange={(e) => setTypedSignature(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 font-serif"
              />
            </div>

            {/* Signature Preview Canvas Box */}
            {typedSignature && (
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 text-center space-y-2">
                <span className="text-[10px] font-mono text-zinc-500 uppercase">Pré-visualização do Selo Digital de {activeSigner.name}:</span>
                <div className="font-serif italic text-2xl text-blue-400 py-2 border-b border-dashed border-zinc-800">
                  {typedSignature}
                </div>
                <div className="text-[9px] font-mono text-emerald-400 flex items-center justify-center space-x-1">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Autenticação {authMethod} Validada + Carimbo Temporal ON/NTP</span>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => setStep("AUTH")}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold"
              >
                Voltar
              </button>

              <button
                type="submit"
                disabled={!typedSignature.trim() || isSubmitting}
                className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-extrabold transition-all shadow-lg shadow-emerald-950 flex items-center space-x-2 cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <Clock className="w-4 h-4 animate-spin" />
                    <span>Criptografando & Selando...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Assinar em Nome de {activeSigner.name.split(" ")[0]}</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* STEP 4: SUCCESS CONFIRMATION */}
        {step === "SUCCESS" && activeSigner && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 text-center space-y-6 shadow-2xl animate-in zoom-in-95 duration-300">
            <div className="w-16 h-16 bg-emerald-950 border border-emerald-700 rounded-full flex items-center justify-center mx-auto text-emerald-400 shadow-xl">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-extrabold text-white">Assinatura de {activeSigner.name} Registrada!</h2>
              <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
                A assinatura eletrônica de <strong className="text-white">{activeSigner.name}</strong> foi colhida e selada criptograficamente. Demais partes pendentes receberão notificação para assinar em seus respectivos acessos.
              </p>
            </div>

            {/* Document Signers Status Summary */}
            <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-xl text-left font-mono text-xs space-y-3 max-w-lg mx-auto">
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block border-b border-zinc-800 pb-2">
                Quadro Atualizado de Assinaturas do Documento:
              </span>
              <div className="space-y-2">
                {signers.map((s, idx) => (
                  <div key={idx} className="flex items-center justify-between text-[11px]">
                    <span className="text-zinc-200">{s.name} ({s.role})</span>
                    {s.status === "SIGNED" ? (
                      <span className="text-emerald-400 font-bold flex items-center space-x-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        <span>ASSINADO</span>
                      </span>
                    ) : (
                      <span className="text-amber-400 font-bold flex items-center space-x-1">
                        <Clock className="w-3 h-3 text-amber-400" />
                        <span>PENDENTE</span>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={() => setStep("VIEW")}
                className="px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-all cursor-pointer"
              >
                Voltar ao Documento
              </button>

              <button
                onClick={() => (window.location.href = "/dashboard/assinaturas")}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                Ir ao Painel de Assinaturas
              </button>
            </div>
            </div>
          )}
        </main>

        {/* AI CLAUSE ANALYZER MODAL (VISUAL LAW) */}
        {isAiModalOpen && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="bg-zinc-900 border border-purple-800/80 rounded-2xl max-w-xl w-full p-6 space-y-5 shadow-2xl relative">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center space-x-2 text-purple-300 font-bold text-sm">
                  <Sparkles className="w-5 h-5 text-purple-400" />
                  <span>LexFlow AI — Resumo Simplificado & Riscos (Visual Law)</span>
                </div>
                <button
                  onClick={() => setIsAiModalOpen(false)}
                  className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4 text-xs">
                <div className="bg-purple-950/40 border border-purple-800/60 rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono text-purple-400 font-bold uppercase">Classificação de Risco Contratual</span>
                    <h4 className="text-sm font-extrabold text-emerald-400 flex items-center space-x-1.5 mt-0.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>CONTRATO DE BAIXO RISCO / EQUILIBRADO</span>
                    </h4>
                  </div>
                  <span className="bg-emerald-950 border border-emerald-800 text-emerald-300 font-mono text-[10px] px-2.5 py-1 rounded-full font-bold">
                    SCORE AI: 98/100
                  </span>
                </div>

                <div className="space-y-2">
                  <h4 className="font-bold text-zinc-200 uppercase tracking-wider text-[11px]">Resumo Simplificado para o Signatário:</h4>
                  <ul className="space-y-2 text-zinc-300 list-disc list-inside bg-zinc-950 border border-zinc-800 p-3.5 rounded-xl font-sans leading-relaxed">
                    <li><strong>Objeto do Contrato:</strong> Prestação de serviços jurídicos e representação em procedimentos extrajudiciais e judiciais.</li>
                    <li><strong>Honorários Advocatícios:</strong> Percentual de êxito pactuado (Quota Litis) sem cobrança de taxas ocultas antecipadas.</li>
                    <li><strong>Prazo & Rescisão:</strong> Vigência durante a tramitação do acordo, garantida a faculdade de distrato motivado.</li>
                    <li><strong>Proteção de Dados:</strong> Coleta biométrica e OTP sob conformidade total com a LGPD e Lei 14.063/2020.</li>
                  </ul>
                </div>

                <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl text-[11px] text-zinc-400 flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-purple-400 shrink-0" />
                  <span>Nenhuma cláusula abusiva ou pegadinha identificada pelo motor heurístico do LexFlow.</span>
                </div>
              </div>

              <div className="pt-3 border-t border-zinc-800 flex justify-end">
                <button
                  onClick={() => setIsAiModalOpen(false)}
                  className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-bold transition-all shadow cursor-pointer"
                >
                  Compreendi — Fechar Resumo
                </button>
              </div>
            </div>
          </div>
        )}

      {/* Footer */}
      <footer className="w-full max-w-4xl text-center py-4 border-t border-zinc-800/80 text-[10px] text-zinc-500 font-mono space-y-1">
        <p>{PLATFORM_CONFIG.fullName} — Todos os direitos reservados. {PLATFORM_CONFIG.legalNotice}.</p>
        <p className="text-zinc-600">Tratamento de Dados Pessoais em conformidade estrita com a LGPD (Lei 13.709/2018). Proteção Criptográfica SHA-256.</p>
      </footer>
    </div>
  );
}

export default function SignDocumentPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-400 font-mono text-xs">
        Carregando portal seguro de assinatura...
      </div>
    }>
      <SignDocumentContent />
    </Suspense>
  );
}
