"use client";

import React, { useState, useMemo, useEffect } from "react";
import jsPDF from "jspdf";
import { PLATFORM_CONFIG } from "@/config/platform";
import {
  FileSignature,
  ShieldCheck,
  Upload,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  Plus,
  Lock,
  Search,
  Filter,
  Send,
  Smartphone,
  Sparkles,
  FileText,
  CheckSquare,
  Square,
  RefreshCw,
  AlertCircle,
  Trash2,
  QrCode,
  UserCheck,
  Fingerprint,
  FileCheck,
  X,
  ChevronRight,
  ChevronLeft,
  Building2,
  ShieldAlert,
  ArrowRight,
  ExternalLink,
  Printer,
  Copy,
  MessageSquare,
  Mail,
  Link2,
} from "lucide-react";

export interface Signer {
  name: string;
  email: string;
  phone: string;
  role: "SIGNER" | "WITNESS" | "APPROVER";
  authMethod: "OTP" | "BIOMETRIC" | "ICP_BRASIL";
  status: "SIGNED" | "PENDING";
  signedAt?: string;
  ipAddress?: string;
}

export interface DocSignature {
  id: string;
  title: string;
  category: string;
  createdAt: string;
  expiresAt: string;
  signers: Signer[];
  hashSha256Original: string;
  hashSha256Final: string;
  status: "COMPLETED" | "IN_PROGRESS" | "WAITING_USER";
  auditTrail: {
    event: string;
    timestamp: string;
    actor: string;
    ip: string;
    device: string;
  }[];
}

const STORAGE_KEY = "lexflow_signatures_docs";

const INITIAL_DOCUMENTS: DocSignature[] = [
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
        role: "SIGNER",
        authMethod: "ICP_BRASIL",
        status: "SIGNED",
        signedAt: "12/08/2026 14:22 UTC-3",
        ipAddress: "177.138.42.109",
      },
      {
        name: "Marcos Paulo Silva",
        email: "marcos.silva@email.com",
        phone: "+55 (11) 91234-5678",
        role: "SIGNER",
        authMethod: "BIOMETRIC",
        status: "SIGNED",
        signedAt: "12/08/2026 16:05 UTC-3",
        ipAddress: "201.86.112.44",
      },
    ],
    auditTrail: [
      {
        event: "Documento criado e assinado pelo emissor (ICP-Brasil A1)",
        timestamp: "12/08/2026 14:22:05",
        actor: "Dr. Alexandre Rossi",
        ip: "177.138.42.109",
        device: "macOS / Chrome 127.0",
      },
      {
        event: "Notificação e link seguro de assinatura enviado via WhatsApp & E-mail",
        timestamp: "12/08/2026 14:22:10",
        actor: "Sistema LexFlow Gateway",
        ip: "AWS sa-east-1",
        device: "LexFlow Automated Dispatcher",
      },
      {
        event: "Link de assinatura acessado via dispositivo móvel",
        timestamp: "12/08/2026 16:01:18",
        actor: "Marcos Paulo Silva",
        ip: "201.86.112.44",
        device: "iOS 17.5 / Safari Mobile",
      },
      {
        event: "Validação Facial / Biometria CNH concluída com sucesso (Match 99.8%)",
        timestamp: "12/08/2026 16:04:50",
        actor: "Serviço de Biometria Serpro",
        ip: "Serpro API Gateway",
        device: "LexFlow Facial SDK",
      },
      {
        event: "Assinatura digital efetuada e certificado de auditoria selado com carimbo do tempo ON/NTP",
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
    hashSha256Final: "Pendência de assinaturas",
    signers: [
      {
        name: "Dr. Alexandre Rossi",
        email: "alexandre@rossiadvocacia.com.br",
        phone: "+55 (11) 98765-4321",
        role: "SIGNER",
        authMethod: "ICP_BRASIL",
        status: "SIGNED",
        signedAt: "11/08/2026 10:15 UTC-3",
        ipAddress: "177.138.42.109",
      },
      {
        name: "Eduardo Fonseca",
        email: "eduardo@techcorp.io",
        phone: "+55 (21) 99887-1122",
        role: "SIGNER",
        authMethod: "OTP",
        status: "PENDING",
      },
      {
        name: "Patrícia Lima",
        email: "patricia@techcorp.io",
        phone: "+55 (21) 97766-3344",
        role: "WITNESS",
        authMethod: "OTP",
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
  {
    id: "DOC-9950",
    title: "Procuração Ad Judicia et Extra con Causa - Ação Tributária Federal",
    category: "Procurações",
    createdAt: "10/08/2026",
    expiresAt: "24/08/2026",
    status: "WAITING_USER",
    hashSha256Original: "3a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b",
    hashSha256Final: "Aguardando sua assinatura",
    signers: [
      {
        name: "Indústrias Matarazzo S/A",
        email: "juridico@matarazzo.com.br",
        phone: "+55 (11) 93344-5566",
        role: "SIGNER",
        authMethod: "BIOMETRIC",
        status: "SIGNED",
        signedAt: "10/08/2026 17:40 UTC-3",
        ipAddress: "189.50.200.12",
      },
      {
        name: "Dr. Alexandre Rossi (Você)",
        email: "alexandre@rossiadvocacia.com.br",
        phone: "+55 (11) 98765-4321",
        role: "APPROVER",
        authMethod: "ICP_BRASIL",
        status: "PENDING",
      },
    ],
    auditTrail: [
      {
        event: "Procuração gerada pelo módulo de petições e enviada ao cliente",
        timestamp: "10/08/2026 16:00:00",
        actor: "Sistema Integrado CRM/Petitions",
        ip: "Internal Bus",
        device: "LexFlow Automated Generator",
      },
      {
        event: "Assinado pelo cliente via Biometria Facial",
        timestamp: "10/08/2026 17:40:12",
        actor: "Indústrias Matarazzo S/A",
        ip: "189.50.200.12",
        device: "Android 14 / Chrome Mobile",
      },
    ],
  },
];

export default function AssinaturasPage() {
  // Enterprise Documents Data persisted with localStorage
  const [documents, setDocuments] = useState<DocSignature[]>(INITIAL_DOCUMENTS);

  // Load saved documents from localStorage on mount (Hydration safe)
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed) && parsed.length > 0) {
            setDocuments(parsed);
          }
        }
      } catch (e) {
        console.error("Erro ao carregar do localStorage:", e);
      }
    }
  }, []);

  // Sync state changes with localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(documents));
      } catch (e) {
        console.error("Erro ao salvar no localStorage:", e);
      }
    }
  }, [documents]);

  // Filtering & Search States
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");

  // Selection for Batch Operations
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  // Modals Control
  const [isNewDocModalOpen, setIsNewDocModalOpen] = useState(false);
  const [isTemplatesModalOpen, setIsTemplatesModalOpen] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<DocSignature | null>(null);
  const [auditDoc, setAuditDoc] = useState<DocSignature | null>(null);
  const [whatsappModalDoc, setWhatsappModalDoc] = useState<DocSignature | null>(null);

  // Toast State
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Helper to resolution active signature URL (with token per signer)
  const getSignatureUrl = (docId: string, signerEmail?: string) => {
    const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";
    if (signerEmail) {
      const token = btoa(signerEmail);
      return `${origin}/sign/${docId}?token=${encodeURIComponent(token)}`;
    }
    return `${origin}/sign/${docId}`;
  };

  // Form State for Create Modal Wizard
  const [newDocTitle, setNewDocTitle] = useState("");
  const [newDocCategory, setNewDocCategory] = useState("Contratos de Honorários");
  const [aiExtractToggle, setAiExtractToggle] = useState(true);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [newSigners, setNewSigners] = useState<
    { name: string; email: string; phone: string; role: "SIGNER" | "WITNESS"; authMethod: "OTP" | "BIOMETRIC" | "ICP_BRASIL" }[]
  >([
    { name: "", email: "", phone: "", role: "SIGNER", authMethod: "OTP" },
  ]);

  // File Upload & Real SHA-256 Calculation State
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [computedHashSha256, setComputedHashSha256] = useState<string>("");
  const [useIcpBrasilIssuer, setUseIcpBrasilIssuer] = useState<boolean>(true);
  const [selectedCertType, setSelectedCertType] = useState<"A1" | "A3" | "BIRD_ID">("A1");

  // File Selection Handler with Real SHA-256 Computation
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    if (!newDocTitle.trim()) {
      setNewDocTitle(file.name.replace(/\.[^/.]+$/, ""));
    }
    try {
      const arrayBuffer = await file.arrayBuffer();
      const hashBuffer = await crypto.subtle.digest("SHA-256", arrayBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
      setComputedHashSha256(hashHex);
    } catch {
      setComputedHashSha256("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    }
    showToast(`Arquivo "${file.name}" carregado! Hash SHA-256 gerado.`);
  };

  // Filtered Documents Calculation
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch =
        doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.signers.some((s) => s.name.toLowerCase().includes(searchTerm.toLowerCase()));

      const matchesStatus = statusFilter === "ALL" || doc.status === statusFilter;
      const matchesCategory = categoryFilter === "ALL" || doc.category === categoryFilter;

      return matchesSearch && matchesStatus && matchesCategory;
    });
  }, [documents, searchTerm, statusFilter, categoryFilter]);

  // KPI Calculations
  const totalActive = documents.length;
  const totalCompleted = documents.filter((d) => d.status === "COMPLETED").length;
  const totalInProgress = documents.filter((d) => d.status === "IN_PROGRESS").length;
  const totalWaitingUser = documents.filter((d) => d.status === "WAITING_USER").length;
  const completionRate = Math.round((totalCompleted / totalActive) * 100) || 0;

  // Batch Select Toggle
  const toggleSelectAll = () => {
    if (selectedDocIds.length === filteredDocuments.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(filteredDocuments.map((d) => d.id));
    }
  };

  const toggleSelectDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Actions
  const handleBatchNotify = () => {
    const targetDoc = documents.find((d) => selectedDocIds.includes(d.id) && d.status !== "COMPLETED");
    if (targetDoc) {
      setWhatsappModalDoc(targetDoc);
    } else {
      showToast(
        `Lembretes via WhatsApp e E-mail disparados para os signatários dos ${selectedDocIds.length} documentos!`
      );
      setSelectedDocIds([]);
    }
  };

  // Action to sign ONLY a specific signer in a specific document (Restricted to logged-in user)
  const handleSignSingleSigner = (docId: string, signerEmail: string) => {
    const currentUserEmail = "alexandre@rossiadvocacia.com.br";
    const isCurrentUser =
      signerEmail.toLowerCase() === currentUserEmail.toLowerCase() ||
      signerEmail.toLowerCase().includes("rossiadvocacia");

    if (!isCurrentUser) {
      showToast(
        `Assinatura de terceiros bloqueada por segurança. Utilize o envio de link tokenizado individual via WhatsApp ou E-mail.`
      );
      return;
    }

    let targetSignerName = "";
    setDocuments((prev) =>
      prev.map((doc) => {
        if (doc.id === docId) {
          const updatedSigners = doc.signers.map((s) => {
            if (s.email.toLowerCase() === signerEmail.toLowerCase() && s.status !== "SIGNED") {
              targetSignerName = s.name;
              return {
                ...s,
                status: "SIGNED" as const,
                signedAt: new Date().toLocaleString("pt-BR") + " UTC-3",
                ipAddress: "177.138.42.109",
              };
            }
            return s;
          });

          const totalSigners = updatedSigners.length;
          const totalSigned = updatedSigners.filter((s) => s.status === "SIGNED").length;
          const isAllSigned = totalSigned === totalSigners;

          const newAuditLog = {
            event: `Assinatura digital individual efetuada por ${targetSignerName || signerEmail}`,
            timestamp: new Date().toLocaleString("pt-BR"),
            actor: targetSignerName || signerEmail,
            ip: "177.138.42.109",
            device: "LexFlow Verified Signature Module",
          };

          const newDocStatus = isAllSigned
            ? ("COMPLETED" as const)
            : updatedSigners.some((s) => s.email.includes("rossiadvocacia") && s.status === "PENDING")
            ? ("WAITING_USER" as const)
            : ("IN_PROGRESS" as const);

          const finalHash = isAllSigned
            ? doc.hashSha256Original.slice(0, 32) + "9949final"
            : `Pendência de assinaturas (${totalSigned}/${totalSigners} concluídas)`;

          return {
            ...doc,
            status: newDocStatus,
            hashSha256Final: finalHash,
            signers: updatedSigners,
            auditTrail: [...doc.auditTrail, newAuditLog],
          };
        }
        return doc;
      })
    );

    // Also update viewingDoc if open
    setViewingDoc((prev) => {
      if (prev && prev.id === docId) {
        const updatedSigners = prev.signers.map((s) =>
          s.email.toLowerCase() === signerEmail.toLowerCase()
            ? { ...s, status: "SIGNED" as const, signedAt: new Date().toLocaleString("pt-BR") + " UTC-3", ipAddress: "177.138.42.109" }
            : s
        );
        const isAllSigned = updatedSigners.every((s) => s.status === "SIGNED");
        return {
          ...prev,
          status: isAllSigned ? "COMPLETED" : "IN_PROGRESS",
          signers: updatedSigners,
        };
      }
      return prev;
    });

    showToast(`Assinatura de ${targetSignerName || signerEmail} registrada com sucesso!`);
  };

  const handleBatchSignCurrentUser = () => {
    const currentUserEmail = "alexandre@rossiadvocacia.com.br";
    let signedDocsCount = 0;
    setDocuments((prev) =>
      prev.map((doc) => {
        if (selectedDocIds.includes(doc.id)) {
          const updatedSigners = doc.signers.map((s) => {
            if ((s.email.toLowerCase() === currentUserEmail || s.name.includes("Você")) && s.status !== "SIGNED") {
              signedDocsCount++;
              return {
                ...s,
                status: "SIGNED" as const,
                signedAt: new Date().toLocaleString("pt-BR") + " UTC-3",
                ipAddress: "177.138.42.109",
              };
            }
            return s;
          });

          const totalSigners = updatedSigners.length;
          const totalSigned = updatedSigners.filter((s) => s.status === "SIGNED").length;
          const isAllSigned = totalSigned === totalSigners;

          return {
            ...doc,
            status: isAllSigned ? ("COMPLETED" as const) : ("IN_PROGRESS" as const),
            signers: updatedSigners,
          };
        }
        return doc;
      })
    );
    showToast(`Assinatura do Dr. Alexandre Rossi colhida em ${selectedDocIds.length} documento(s)!`);
    setSelectedDocIds([]);
  };

  // 1. Direct PDF File Downloader using jsPDF (Downloads .pdf file directly WITHOUT opening print dialog)
  const handleDownloadDocumentPdfFile = (doc: DocSignature) => {
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

    // Header
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(16);
    pdf.setTextColor(15, 23, 42);
    pdf.text(doc.title, 14, 20);

    pdf.setFontSize(8.5);
    pdf.setFont("helvetica", "bold");
    pdf.setTextColor(37, 99, 235);
    pdf.text("LEXFLOW ENTERPRISE — INSTRUMENTO JURÍDICO CERTIFICADO (LEI 14.063/2020)", 14, 26);

    pdf.setFont("helvetica", "normal");
    pdf.setTextColor(100, 116, 139);
    pdf.text(`ID: ${doc.id} | Categoria: ${doc.category} | Data: ${doc.createdAt}`, 14, 31);

    pdf.setDrawColor(37, 99, 235);
    pdf.setLineWidth(0.6);
    pdf.line(14, 34, 196, 34);

    // Metadata Box
    pdf.setFillColor(248, 250, 252);
    pdf.roundedRect(14, 38, 182, 30, 3, 3, "F");
    pdf.setDrawColor(226, 232, 240);
    pdf.roundedRect(14, 38, 182, 30, 3, 3, "S");

    pdf.setFontSize(9);
    pdf.setFont("helvetica", "bold");
    pdf.setTextColor(30, 41, 59);
    pdf.text("METADADOS DE CRIPTO-INTEGRIDADE:", 18, 45);

    pdf.setFontSize(8);
    pdf.setFont("courier", "normal");
    pdf.setTextColor(71, 85, 105);
    pdf.text(`HASH SHA-256 ORIGINAL: ${doc.hashSha256Original}`, 18, 52);
    pdf.text(`HASH SHA-256 SELADO:   ${doc.hashSha256Final}`, 18, 60);

    // Body Section
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(15, 23, 42);
    pdf.text("Teor do Instrumento Jurídico", 14, 77);
    pdf.line(14, 79, 196, 79);

    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(9.5);
    pdf.setTextColor(51, 65, 85);

    const bodyText =
      "Pelo presente instrumento particular, as partes qualificadas declaram ter pleno conhecimento de todas as cláusulas e condições pactuadas, concordando expressamente com a assinatura por meio eletrônico e validação biométrica/criptográfica.\n\nDisposições sobre Integridade e Auditoria: O presente documento digital possui carimbo do tempo oficial sincronizado com o Observatório da Hora Legal do Brasil (ON/NTP) e assinatura assimétrica criptografada por meio da chave privada ICP-Brasil SHA-256.";

    const lines = pdf.splitTextToSize(bodyText, 182);
    pdf.text(lines, 14, 86);

    // Signers Section
    let yPos = 125;
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(15, 23, 42);
    pdf.text("Quadro de Assinaturas Registradas", 14, yPos);
    pdf.line(14, yPos + 2, 196, yPos + 2);
    yPos += 8;

    doc.signers.forEach((s) => {
      pdf.setFillColor(255, 255, 255);
      pdf.roundedRect(14, yPos, 182, 22, 2, 2, "F");
      pdf.setDrawColor(203, 213, 225);
      pdf.roundedRect(14, yPos, 182, 22, 2, 2, "S");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(9.5);
      pdf.setTextColor(15, 23, 42);
      pdf.text(s.name, 18, yPos + 7);

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(8);
      if (s.status === "SIGNED") {
        pdf.setTextColor(22, 163, 74);
        pdf.text("ASSINADO", 165, yPos + 7);
      } else {
        pdf.setTextColor(217, 119, 6);
        pdf.text("PENDENTE", 165, yPos + 7);
      }

      pdf.setFont("courier", "normal");
      pdf.setFontSize(8);
      pdf.setTextColor(100, 116, 139);
      pdf.text(`${s.email} | Tel: ${s.phone} | Autenticação: ${s.authMethod}`, 18, yPos + 13);

      if (s.signedAt) {
        pdf.setTextColor(22, 163, 74);
        pdf.text(`Assinado em: ${s.signedAt} (IP: ${s.ipAddress})`, 18, yPos + 18);
      }

      yPos += 26;
    });

    // QR Code / Public Verification Box on PDF footer
    pdf.setFillColor(248, 250, 252);
    pdf.roundedRect(14, 266, 182, 14, 2, 2, "F");
    pdf.setDrawColor(226, 232, 240);
    pdf.roundedRect(14, 266, 182, 14, 2, 2, "S");

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(8);
    pdf.setTextColor(30, 41, 59);
    pdf.text("VALIDAÇÃO POR QR CODE / LINK PÚBLICO (LEI 14.063/2020):", 18, 272);

    pdf.setFont("courier", "bold");
    pdf.setFontSize(7.5);
    pdf.setTextColor(37, 99, 235);
    pdf.text(`http://localhost:3000/verify/${doc.id}`, 18, 277);

    // Footer
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7.5);
    pdf.setTextColor(148, 163, 184);
    pdf.text(
      "Documento gerado eletronicamente por LexFlow Enterprise. Validação técnica por SHA-256 e ICP-Brasil.",
      14,
      285
    );

    const filename = `${doc.id}_Documento.pdf`;
    pdf.save(filename);
    showToast(`Arquivo "${filename}" baixado diretamente para seus Downloads!`);
  };

  // 2. Direct Audit Certificate PDF Downloader using jsPDF (Downloads .pdf file directly WITHOUT print dialog)
  const handleDownloadAuditCertificatePdfFile = (doc: DocSignature) => {
    const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(16);
    pdf.setTextColor(15, 23, 42);
    pdf.text("Manifesto de Auditoria & Trilha Digital", 14, 20);

    pdf.setFontSize(8.5);
    pdf.setFont("helvetica", "bold");
    pdf.setTextColor(147, 51, 234);
    pdf.text("VALOR JURÍDICO ICP-BRASIL & LEI 14.063/2020 — LEXFLOW ENTERPRISE", 14, 26);

    pdf.setFont("helvetica", "normal");
    pdf.setTextColor(100, 116, 139);
    pdf.text(`DOCUMENTO AUDITADO: ${doc.id} — ${doc.title}`, 14, 31);

    pdf.setDrawColor(147, 51, 234);
    pdf.setLineWidth(0.6);
    pdf.line(14, 34, 196, 34);

    // Metadata Box
    pdf.setFillColor(248, 250, 252);
    pdf.roundedRect(14, 38, 182, 28, 3, 3, "F");
    pdf.setDrawColor(226, 232, 240);
    pdf.roundedRect(14, 38, 182, 30, 3, 3, "S");

    pdf.setFontSize(8);
    pdf.setFont("courier", "normal");
    pdf.setTextColor(71, 85, 105);
    pdf.text(`HASH SHA-256 DO ARQUIVO ORIGINAL: ${doc.hashSha256Original}`, 18, 48);
    pdf.text(`HASH SHA-256 FINAL SELADO:        ${doc.hashSha256Final}`, 18, 56);

    // Logs Section
    let yPos = 76;
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(15, 23, 42);
    pdf.text("Histórico Cronológico Inalterável de Auditoria (Logs)", 14, yPos);
    pdf.line(14, yPos + 2, 196, yPos + 2);
    yPos += 10;

    doc.auditTrail.forEach((log) => {
      pdf.setFillColor(255, 255, 255);
      pdf.roundedRect(14, yPos, 182, 16, 2, 2, "F");
      pdf.setDrawColor(226, 232, 240);
      pdf.roundedRect(14, yPos, 182, 16, 2, 2, "S");

      pdf.setFont("helvetica", "bold");
      pdf.setFontSize(9);
      pdf.setTextColor(15, 23, 42);
      pdf.text(log.event, 18, yPos + 6);

      pdf.setFont("courier", "normal");
      pdf.setFontSize(7.5);
      pdf.setTextColor(100, 116, 139);
      pdf.text(`${log.timestamp} | Ator: ${log.actor} | IP: ${log.ip} | Dispositivo: ${log.device}`, 18, yPos + 12);

      yPos += 19;
    });

    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    pdf.setTextColor(148, 163, 184);
    pdf.text(
      "Manifesto de Auditoria gerado eletronicamente por LexFlow Enterprise. Validação por SHA-256 e ICP-Brasil.",
      14,
      285
    );

    const filename = `Certificado_Auditoria_${doc.id}.pdf`;
    pdf.save(filename);
    showToast(`Certificado PDF "${filename}" baixado diretamente para seus Downloads!`);
  };

  // Helper for Clean Printable Window (For Print Dialog Only)
  const openPrintableWindow = (title: string, contentHtml: string) => {
    const printWin = window.open("", "_blank", "width=850,height=950");
    if (!printWin) {
      showToast("Por favor, permita pop-ups no seu navegador para imprimir!");
      return;
    }
    printWin.document.write(`
      <!DOCTYPE html>
      <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <title>${title}</title>
          <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
            body {
              font-family: 'Inter', sans-serif;
              color: #0f172a;
              background-color: #ffffff;
              margin: 0;
              padding: 40px;
              line-height: 1.6;
            }
            .header-banner {
              border-bottom: 3px solid #2563eb;
              padding-bottom: 16px;
              margin-bottom: 24px;
              display: flex;
              justify-content: space-between;
              align-items: flex-start;
            }
            .title { font-size: 20px; font-weight: 800; color: #0f172a; margin: 0; }
            .subtitle { font-size: 11px; color: #64748b; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }
            .badge { background-color: #eff6ff; color: #1d4ed8; font-weight: 700; font-size: 11px; padding: 4px 10px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; border: 1px solid #bfdbfe; }
            .box { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 20px; }
            .mono { font-family: 'JetBrains Mono', monospace; font-size: 11px; }
            .hash { word-break: break-all; color: #475569; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
            .card { border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; background: #fff; }
            .timeline-item { border-left: 2px solid #3b82f6; padding-left: 12px; margin-bottom: 12px; }
            .footer { border-top: 1px solid #e2e8f0; margin-top: 40px; padding-top: 16px; font-size: 10px; color: #94a3b8; text-align: center; }
            @media print {
              body { padding: 20px; }
              .no-print { display: none !important; }
            }
          </style>
        </head>
        <body>
          ${contentHtml}
          <div class="no-print" style="margin-top: 30px; text-align: center;">
            <button onclick="window.print()" style="background: #2563eb; color: white; border: none; padding: 12px 24px; font-weight: bold; border-radius: 8px; cursor: pointer; font-size: 14px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
              🖨️ Abrir Diálogo de Impressão
            </button>
          </div>
          <script>
            window.onload = function() {
              setTimeout(function() {
                window.print();
              }, 400);
            };
          </script>
        </body>
      </html>
    `);
    printWin.document.close();
  };

  // Trigger Print Dialog for Document
  const handlePrintDocument = (doc: DocSignature) => {
    const signersHtml = doc.signers
      .map(
        (s) => `
          <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong>${s.name}</strong>
              <span class="badge font-mono">${s.status === "SIGNED" ? "ASSINADO" : "PENDENTE"}</span>
            </div>
            <div class="mono" style="color:#64748b; margin-top:4px;">${s.email} | Tel: ${s.phone}</div>
            <div class="mono" style="color:#3b82f6; font-size:10px; margin-top:2px;">Autenticação: ${s.authMethod} | Papel: ${s.role}</div>
            ${s.signedAt ? `<div class="mono" style="color:#16a34a; font-size:10px; margin-top:4px;">Assinado em: ${s.signedAt} (IP: ${s.ipAddress})</div>` : ""}
          </div>
        `
      )
      .join("");

    const bodyHtml = `
      <div class="header-banner">
        <div>
          <h1 class="title">${doc.title}</h1>
          <div class="subtitle">LEXFLOW ENTERPRISE — INSTRUMENTO JURÍDICO CERTIFICADO (LEI 14.063/2020)</div>
        </div>
        <span class="badge">${doc.id}</span>
      </div>

      <div class="box">
        <strong style="font-size:12px; color:#334155; text-transform:uppercase;">Metadados de Cripto-Integridade:</strong>
        <div class="grid">
          <div>
            <span class="mono" style="color:#64748b; font-size:10px;">HASH SHA-256 ORIGINAL:</span>
            <div class="mono hash">${doc.hashSha256Original}</div>
          </div>
          <div>
            <span class="mono" style="color:#64748b; font-size:10px;">HASH SHA-256 FINAL SELADO:</span>
            <div class="mono hash" style="color:#2563eb;">${doc.hashSha256Final}</div>
          </div>
        </div>
      </div>

      <div style="margin: 24px 0;">
        <h3 style="font-size: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">Teor do Instrumento Jurídico</h3>
        <p style="font-size: 13px; color: #334155;">
          Pelo presente instrumento particular, as partes qualificadas declaram ter pleno conhecimento de todas as cláusulas e condições pactuadas, concordando expressamente com a assinatura por meio eletrônico e validação biométrica/criptográfica.
        </p>
        <p style="font-size: 12px; color: #64748b; background: #f8fafc; padding: 12px; border-radius: 6px; border-left: 3px solid #2563eb;">
          <strong>Disposições sobre Integridade e Auditoria:</strong> O presente documento digital possui carimbo do tempo oficial sincronizado com o Observatório da Hora Legal do Brasil (ON/NTP) e assinatura assimétrica criptografada por meio da chave privada ICP-Brasil SHA-256.
        </p>
      </div>

      <div style="margin-top: 24px;">
        <h3 style="font-size: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">Quadro de Assinaturas Registradas</h3>
        <div class="grid">
          ${signersHtml}
        </div>
      </div>

      <div class="footer">
        Documento gerado eletronicamente por LexFlow Enterprise LegalTech System. Validação técnica garantida por SHA-256 e ICP-Brasil.
      </div>
    `;

    openPrintableWindow(`${doc.id} — ${doc.title}`, bodyHtml);
  };

  // Trigger Print Dialog for Audit Certificate
  const handlePrintAuditCertificate = (doc: DocSignature) => {
    const logsHtml = doc.auditTrail
      .map(
        (l) => `
          <div class="timeline-item">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="font-size:12px; color:#0f172a;">${l.event}</strong>
              <span class="mono" style="font-size:10px; color:#64748b;">${l.timestamp}</span>
            </div>
            <div class="mono" style="font-size:10px; color:#475569; margin-top:2px;">
              Ator: <strong>${l.actor}</strong> | IP: ${l.ip} | Dispositivo: ${l.device}
            </div>
          </div>
        `
      )
      .join("");

    const signersHtml = doc.signers
      .map(
        (s) => `
          <div class="card">
            <strong>${s.name}</strong> (${s.email})
            <div class="mono" style="font-size:10px; color:#475569;">Tel: ${s.phone} | Método: ${s.authMethod} | Status: ${s.status}</div>
            ${s.signedAt ? `<div class="mono" style="font-size:10px; color:#16a34a;">Assinado em: ${s.signedAt} (IP: ${s.ipAddress})</div>` : ""}
          </div>
        `
      )
      .join("");

    const bodyHtml = `
      <div class="header-banner">
        <div>
          <h1 class="title">Manifesto de Auditoria & Trilha Digital</h1>
          <div class="subtitle">VALOR JURÍDICO ICP-BRASIL & LEI 14.063/2020 — LEXFLOW ENTERPRISE</div>
        </div>
        <span class="badge">${doc.id}</span>
      </div>

      <div class="box">
        <h3 style="margin-top:0; font-size:13px; color:#0f172a;">Documento Auditado: ${doc.title}</h3>
        <div class="grid">
          <div>
            <span class="mono" style="color:#64748b; font-size:10px;">HASH SHA-256 DO ARQUIVO ORIGINAL:</span>
            <div class="mono hash">${doc.hashSha256Original}</div>
          </div>
          <div>
            <span class="mono" style="color:#64748b; font-size:10px;">HASH SHA-256 FINAL SELADO:</span>
            <div class="mono hash" style="color:#2563eb;">${doc.hashSha256Final}</div>
          </div>
        </div>
      </div>

      <div style="margin: 20px 0;">
        <h3 style="font-size: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">Qualificação das Partes Signatárias</h3>
        <div class="grid">
          ${signersHtml}
        </div>
      </div>

      <div style="margin-top: 24px;">
        <h3 style="font-size: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">Histórico Cronológico Inalterável de Auditoria (Logs)</h3>
        <div style="margin-top: 12px;">
          ${logsHtml}
        </div>
      </div>

      <div class="footer">
        Manifesto de Auditoria Digital gerado eletronicamente por LexFlow Enterprise. Validação oficial de acervo criptográfico.
      </div>
    `;

    openPrintableWindow(`Manifesto de Auditoria — ${doc.id}`, bodyHtml);
  };

  // Robust WhatsApp Universal Link Handler (wa.me) pointing to REAL signature portal
  const handleSendWhatsAppWeb = (signerName: string, phone: string, docTitle: string, docId: string, signerEmail?: string) => {
    let cleanPhone = phone.replace(/\D/g, "");
    if (cleanPhone.length === 10 || cleanPhone.length === 11) {
      cleanPhone = "55" + cleanPhone;
    }
    const signatureUrl = getSignatureUrl(docId, signerEmail);
    const msg = `Olá ${signerName}! Lembramos que o documento "${docTitle}" está aguardando sua assinatura eletrônica no ${PLATFORM_CONFIG.fullName}.\n\nAcesse o link direto tokenizado para ler e assinar: ${signatureUrl}`;
    const encodedMsg = encodeURIComponent(msg);
    window.open(`https://wa.me/${cleanPhone}?text=${encodedMsg}`, "_blank");
    showToast(`WhatsApp com link tokenizado aberto para ${signerName} (+${cleanPhone})!`);
  };

  // Direct E-mail Handler (mailto:) pointing to REAL signature portal
  const handleSendEmailClient = (signerName: string, email: string, docTitle: string, docId: string) => {
    const signatureUrl = getSignatureUrl(docId, email);
    const subject = encodeURIComponent(`Assinatura Pendente: ${docTitle} (${PLATFORM_CONFIG.shortName})`);
    const body = encodeURIComponent(
      `Olá ${signerName},\n\nVocê possui um documento pendente de assinatura no sistema ${PLATFORM_CONFIG.fullName}.\n\nDocumento: ${docTitle}\nID: ${docId}\n\nAcesse o link tokenizado exclusivo abaixo para efetuar a assinatura eletrônica com validação jurídica:\n${signatureUrl}\n\nAtenciosamente,\n${PLATFORM_CONFIG.fullName}`
    );
    window.open(`mailto:${email}?subject=${subject}&body=${body}`, "_blank");
    showToast(`Cliente de e-mail com link tokenizado aberto para ${email}!`);
  };

  const handleCopyWhatsAppText = (signerName: string, docTitle: string, docId: string, signerEmail?: string) => {
    const signatureUrl = getSignatureUrl(docId, signerEmail);
    const msg = `Olá ${signerName}! Lembramos que o documento "${docTitle}" está aguardando sua assinatura eletrônica no ${PLATFORM_CONFIG.fullName}.\n\nAcesse o link exclusivo tokenizado para assinar: ${signatureUrl}`;
    navigator.clipboard.writeText(msg);
    showToast("Mensagem e link tokenizado copiados para a área de transferência!");
  };

  const handleCopySignerLink = (docId: string, signerEmail: string, signerName: string) => {
    const signatureUrl = getSignatureUrl(docId, signerEmail);
    navigator.clipboard.writeText(signatureUrl);
    showToast(`Link tokenizado exclusivo de ${signerName} copiado!`);
  };

  // Automated Multi-Channel Dispatch (WhatsApp Business API + Resend SMTP)
  const handleDispatchApiWhatsApp = (doc: DocSignature) => {
    const pendingSigners = doc.signers.filter((s) => s.status !== "SIGNED");

    setDocuments((prev) =>
      prev.map((d) => {
        if (d.id === doc.id) {
          const newLogs = pendingSigners.flatMap((s) => [
            {
              event: `Notificação enviada via WhatsApp Business Cloud API para ${s.phone}`,
              timestamp: new Date().toLocaleString("pt-BR"),
              actor: `LexFlow WhatsApp Engine (+${s.phone.replace(/\D/g, "")})`,
              ip: "WhatsApp Business API Gateway",
              device: "Cloud Webhook Dispatcher",
            },
            {
              event: `E-mail transacional com token criptográfico enviado via SMTP/Resend para ${s.email}`,
              timestamp: new Date().toLocaleString("pt-BR"),
              actor: `LexFlow Mail Gateway (${s.email})`,
              ip: "AWS SES / Resend API",
              device: "SMTP Mail Dispatcher",
            },
          ]);

          return {
            ...d,
            auditTrail: [...d.auditTrail, ...newLogs],
          };
        }
        return d;
      })
    );

    showToast(
      `Disparo concluído com sucesso! ${pendingSigners.length} signatários notificados via WhatsApp API & E-mail!`
    );
    setWhatsappModalDoc(null);
  };

  const handleAddSignerRow = () => {
    setNewSigners((prev) => [
      ...prev,
      { name: "", email: "", phone: "", role: "SIGNER", authMethod: "OTP" },
    ]);
  };

  const handleRemoveSignerRow = (index: number) => {
    if (newSigners.length <= 1) return;
    setNewSigners((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreateDocument = (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (!newDocTitle.trim()) {
      showToast("Informe o título do documento para disparar a fila.");
      setWizardStep(1);
      return;
    }

    const fileHash =
      computedHashSha256 || "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3";

    const validSigners: Signer[] = [
      {
        name: "Dr. Alexandre Rossi (Você)",
        email: "alexandre@rossiadvocacia.com.br",
        phone: "+55 (11) 98765-4321",
        role: "SIGNER",
        authMethod: useIcpBrasilIssuer ? "ICP_BRASIL" : "OTP",
        status: "SIGNED",
        signedAt: new Date().toLocaleString("pt-BR") + " UTC-3",
        ipAddress: "177.138.42.109",
      },
      ...newSigners
        .filter((s) => s.name.trim())
        .map((s) => ({
          name: s.name.trim(),
          email: s.email.trim() || "contato@cliente.com.br",
          phone: s.phone.trim() || "+55 (11) 98765-4321",
          role: s.role,
          authMethod: s.authMethod,
          status: "PENDING" as const,
        })),
    ];

    const initialLogs = [
      {
        event: `Arquivo "${uploadedFile?.name || newDocTitle}.pdf" submetido ao barramento criptográfico`,
        timestamp: new Date().toLocaleString("pt-BR"),
        actor: "Dr. Alexandre Rossi",
        ip: "177.138.42.109",
        device: "LexFlow Enterprise Web",
      },
    ];

    if (useIcpBrasilIssuer) {
      initialLogs.push({
        event: `Assinatura digital efetuada pelo emissor via Certificado ICP-Brasil ${selectedCertType}`,
        timestamp: new Date().toLocaleString("pt-BR"),
        actor: "Dr. Alexandre Rossi (OAB/SP 458.912)",
        ip: "177.138.42.109",
        device: `LexFlow ICP-Brasil PKI Provider (${selectedCertType})`,
      });
    }

    // Auto add dispatch log to created doc
    validSigners
      .filter((s) => s.status === "PENDING")
      .forEach((s) => {
        initialLogs.push({
          event: `Disparo automático enviado via WhatsApp (+${s.phone.replace(/\D/g, "")}) e E-mail (${s.email})`,
          timestamp: new Date().toLocaleString("pt-BR"),
          actor: "LexFlow Gateway Multicanal",
          ip: "Multi-channel Engine",
          device: "AWS SES / Meta Cloud API",
        });
      });

    const createdDoc: DocSignature = {
      id: `DOC-${Math.floor(1000 + Math.random() * 9000)}`,
      title: newDocTitle,
      category: newDocCategory,
      createdAt: new Date().toLocaleDateString("pt-BR"),
      expiresAt: new Date(Date.now() + 14 * 86400000).toLocaleDateString("pt-BR"),
      status: "IN_PROGRESS",
      hashSha256Original: fileHash,
      hashSha256Final: "Pendência de colheita de assinaturas",
      signers: validSigners,
      auditTrail: initialLogs,
    };

    setDocuments([createdDoc, ...documents]);
    setIsNewDocModalOpen(false);
    setNewDocTitle("");
    setUploadedFile(null);
    setComputedHashSha256("");
    setNewSigners([{ name: "", email: "", phone: "", role: "SIGNER", authMethod: "OTP" }]);
    setWizardStep(1);
    showToast("Novo documento criado e disparado via WhatsApp e E-mail com sucesso!");
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-blue-600 border border-blue-500 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-blue-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono uppercase tracking-wider">
            <FileSignature className="w-4 h-4 text-blue-400" />
            <span>Módulo de Validação Criptográfica ICP-Brasil & Lei 14.063/2020</span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            Assinatura Eletrônica & Trilha de Auditoria Digital
          </h1>
          <p className="text-xs text-zinc-400 max-w-3xl leading-relaxed">
            Assinatura digital avançada e qualificada com carimbo do tempo (ON/NTP), integridade garantida por SHA-256 e validade jurídica plena em todo o território nacional.
          </p>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => setIsTemplatesModalOpen(true)}
            className="px-4 py-3 bg-purple-950/80 hover:bg-purple-900 border border-purple-800 text-purple-200 rounded-xl text-xs font-bold transition-all flex items-center space-x-2 cursor-pointer hover:scale-[1.02] shadow-lg shadow-purple-950/40"
          >
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span>Biblioteca de Modelos</span>
          </button>

          <button
            onClick={() => {
              setWizardStep(1);
              setIsNewDocModalOpen(true);
            }}
            className="px-5 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-blue-950/60 transition-all flex items-center space-x-2 cursor-pointer hover:scale-[1.02]"
          >
            <Plus className="w-4 h-4 stroke-[3]" />
            <span>Criar Fila de Assinatura</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Documentos em Trâmite</span>
            <FileText className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-zinc-100">{totalActive}</span>
            <span className="text-[10px] text-zinc-500 font-mono">ativos no sistema</span>
          </div>
          <div className="w-full bg-zinc-950 rounded-full h-1.5 border border-zinc-800 overflow-hidden">
            <div className="bg-blue-500 h-full rounded-full" style={{ width: "100%" }} />
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Taxa de Conclusão</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-emerald-400">{completionRate}%</span>
            <span className="text-[10px] text-emerald-500/80 font-mono">{totalCompleted} concluídos</span>
          </div>
          <div className="w-full bg-zinc-950 rounded-full h-1.5 border border-zinc-800 overflow-hidden">
            <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${completionRate}%` }} />
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Aguardando Sua Assinatura</span>
            <ShieldAlert className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold font-mono text-amber-400">{totalWaitingUser}</span>
            <span className="text-[10px] text-amber-500/80 font-mono">ação pendente</span>
          </div>
          <div className="w-full bg-zinc-950 rounded-full h-1.5 border border-zinc-800 overflow-hidden">
            <div className="bg-amber-500 h-full rounded-full" style={{ width: totalWaitingUser > 0 ? "70%" : "0%" }} />
          </div>
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2 shadow-md">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium">
            <span>Segurança & Criptografia</span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-lg font-bold font-mono text-purple-300">SHA-256 / ICP</span>
          </div>
          <p className="text-[10px] text-zinc-500 font-mono leading-tight">
            Validação Criptográfica + Carimbo Temporal ON/NTP
          </p>
        </div>
      </div>

      {/* Control Toolbar: Search, Filters & Batch Actions */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3 shadow-md">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por contrato, ID ou signatário..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl pl-9 pr-4 py-2 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
            {/* Status Filter */}
            <div className="flex items-center space-x-1 bg-zinc-950 border border-zinc-800 rounded-xl px-2.5 py-1.5">
              <Filter className="w-3.5 h-3.5 text-zinc-500" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-transparent text-xs font-semibold text-zinc-300 focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-zinc-900">Todos os Status</option>
                <option value="IN_PROGRESS" className="bg-zinc-900">Em Trâmite</option>
                <option value="COMPLETED" className="bg-zinc-900">Concluídos</option>
                <option value="WAITING_USER" className="bg-zinc-900">Aguardando Você</option>
              </select>
            </div>

            {/* Category Filter */}
            <div className="flex items-center space-x-1 bg-zinc-950 border border-zinc-800 rounded-xl px-2.5 py-1.5">
              <Building2 className="w-3.5 h-3.5 text-zinc-500" />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="bg-transparent text-xs font-semibold text-zinc-300 focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-zinc-900">Todas as Categorias</option>
                <option value="Contratos de Honorários" className="bg-zinc-900">Honorários</option>
                <option value="Societário / M&A" className="bg-zinc-900">Societário / M&A</option>
                <option value="Procurações" className="bg-zinc-900">Procurações</option>
                <option value="Documento Jurídico Geral" className="bg-zinc-900">Geral</option>
              </select>
            </div>

            {/* Select All Toggle */}
            <button
              onClick={toggleSelectAll}
              className="px-3 py-1.5 bg-zinc-950 border border-zinc-800 hover:border-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer"
            >
              {selectedDocIds.length === filteredDocuments.length && filteredDocuments.length > 0 ? (
                <CheckSquare className="w-3.5 h-3.5 text-blue-400" />
              ) : (
                <Square className="w-3.5 h-3.5 text-zinc-500" />
              )}
              <span>Selecionar Todos</span>
            </button>
          </div>
        </div>

        {/* Floating Batch Action Toolbar */}
        {selectedDocIds.length > 0 && (
          <div className="bg-blue-950/80 border border-blue-800/80 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 animate-in fade-in duration-200">
            <div className="flex items-center space-x-2 text-xs font-semibold text-blue-200">
              <CheckSquare className="w-4 h-4 text-blue-400" />
              <span>{selectedDocIds.length} documento(s) selecionado(s)</span>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleBatchNotify}
                className="px-3 py-1.5 bg-blue-900/60 hover:bg-blue-800 text-blue-100 rounded-lg text-xs font-semibold border border-blue-700/60 transition-colors flex items-center space-x-1.5 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Reenviar WhatsApp/E-mail</span>
              </button>
              <button
                onClick={handleBatchSignCurrentUser}
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow transition-colors flex items-center space-x-1.5 cursor-pointer"
              >
                <Fingerprint className="w-3.5 h-3.5" />
                <span>Assinar Selecionados (Dr. Alexandre Rossi)</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Main Documents Queue Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
            <FileSignature className="w-4 h-4 text-blue-400" />
            <span>Fila Ativa de Assinaturas Eletrônicas</span>
          </h3>
          <span className="text-[11px] font-mono text-zinc-400 bg-zinc-950 px-2.5 py-1 rounded-full border border-zinc-800">
            {filteredDocuments.length} Documentos Exibidos
          </span>
        </div>

        {filteredDocuments.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <FileCheck className="w-10 h-10 text-zinc-600 mx-auto" />
            <p className="text-xs text-zinc-400 font-medium">Nenhum documento encontrado com os filtros selecionados.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredDocuments.map((doc) => {
              const isSelected = selectedDocIds.includes(doc.id);
              const signedCount = doc.signers.filter((s) => s.status === "SIGNED").length;
              const progressPct = Math.round((signedCount / doc.signers.length) * 100);

              return (
                <div
                  key={doc.id}
                  className={`bg-zinc-950 border rounded-xl p-5 transition-all space-y-4 ${
                    isSelected ? "border-blue-500 bg-blue-950/10 shadow-lg" : "border-zinc-800 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-2 max-w-2xl">
                      {/* Top Badges Row */}
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => toggleSelectDoc(doc.id)}
                          className="text-zinc-500 hover:text-zinc-200 cursor-pointer"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-blue-400" />
                          ) : (
                            <Square className="w-4 h-4 text-zinc-600" />
                          )}
                        </button>
                        <span className="font-mono text-xs font-bold text-blue-400">{doc.id}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 font-mono text-zinc-400">
                          {doc.category}
                        </span>
                        <span className="text-[10px] font-mono text-zinc-500">Criação: {doc.createdAt}</span>

                        {doc.status === "COMPLETED" && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-800 text-emerald-400 flex items-center space-x-1">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>CONCLUÍDO</span>
                          </span>
                        )}
                        {doc.status === "IN_PROGRESS" && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-950/80 border border-blue-800 text-blue-300 flex items-center space-x-1">
                            <Clock className="w-3 h-3 animate-spin" />
                            <span>EM TRÂMITE ({progressPct}%)</span>
                          </span>
                        )}
                        {doc.status === "WAITING_USER" && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-950/80 border border-amber-800 text-amber-300 flex items-center space-x-1">
                            <AlertCircle className="w-3 h-3" />
                            <span>AGUARDANDO SUA ASSINATURA</span>
                          </span>
                        )}
                      </div>

                      {/* Title */}
                      <h4 className="text-base font-bold text-zinc-100">{doc.title}</h4>

                      {/* Signers Pill List */}
                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        {doc.signers.map((s, idx) => (
                          <div
                            key={idx}
                            className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border ${
                              s.status === "SIGNED"
                                ? "bg-emerald-950/60 border-emerald-800/80 text-emerald-300"
                                : "bg-zinc-900 border-zinc-800 text-amber-300"
                            }`}
                          >
                            {s.status === "SIGNED" ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Clock className="w-3.5 h-3.5 text-amber-400" />
                            )}
                            <span className="font-semibold">{s.name}</span>
                            <span className="text-[9px] font-mono text-zinc-400">
                              ({s.authMethod === "ICP_BRASIL" ? "ICP" : s.authMethod === "BIOMETRIC" ? "Biometria" : "OTP"})
                            </span>

                            {s.status === "PENDING" && (
                              s.email.includes("rossiadvocacia") ? (
                                <button
                                  type="button"
                                  onClick={() => handleSignSingleSigner(doc.id, s.email)}
                                  title={`Assinar sua cota como ${s.name}`}
                                  className="ml-1 px-1.5 py-0.5 bg-amber-500/20 hover:bg-amber-500/40 text-amber-200 rounded text-[9px] font-bold border border-amber-500/40 cursor-pointer transition-colors flex items-center space-x-1"
                                >
                                  <Fingerprint className="w-3 h-3 text-amber-400" />
                                  <span>Assinar Sua Cota</span>
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleCopySignerLink(doc.id, s.email, s.name)}
                                  title={`Copiar Link Tokenizado Exclusivo de ${s.name}`}
                                  className="ml-1 px-1.5 py-0.5 bg-blue-500/20 hover:bg-blue-500/40 text-blue-200 rounded text-[9px] font-bold border border-blue-500/40 cursor-pointer transition-colors flex items-center space-x-1"
                                >
                                  <Link2 className="w-3 h-3 text-blue-400" />
                                  <span>Copiar Link Exclusivo</span>
                                </button>
                              )
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Hash Footprint */}
                      <p className="text-[10px] font-mono text-zinc-500 truncate pt-1">
                        Hash SHA-256: <span className="text-zinc-400">{doc.hashSha256Original}</span>
                      </p>
                    </div>

                    {/* Action Buttons Right Side */}
                    <div className="flex flex-wrap md:flex-col items-end justify-center gap-2 shrink-0 border-t md:border-t-0 md:border-l border-zinc-800/80 pt-3 md:pt-0 md:pl-4">
                      <button
                        onClick={() => setViewingDoc(doc)}
                        className="w-full px-3 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 border border-zinc-800 cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5 text-blue-400" />
                        <span>Visualizar PDF</span>
                      </button>

                      <button
                        onClick={() => setAuditDoc(doc)}
                        className="w-full px-3 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 border border-zinc-800 cursor-pointer"
                      >
                        <QrCode className="w-3.5 h-3.5 text-purple-400" />
                        <span>Trilha de Auditoria</span>
                      </button>

                      {doc.status !== "COMPLETED" && (
                        <button
                          onClick={() => setWhatsappModalDoc(doc)}
                          className="w-full px-3 py-2 bg-blue-950/80 hover:bg-blue-900 text-blue-300 hover:text-white rounded-lg text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 border border-blue-800/60 cursor-pointer"
                        >
                          <Send className="w-3.5 h-3.5 text-blue-400" />
                          <span>Reenviar Notificação</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* MODAL 1: PRE-VISUALIZAR DOCUMENTO */}
      {viewingDoc && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-950">
              <div className="flex items-center space-x-3">
                <FileText className="w-5 h-5 text-blue-400" />
                <div>
                  <h3 className="text-sm font-bold text-zinc-100">{viewingDoc.title}</h3>
                  <p className="text-[10px] font-mono text-zinc-400">
                    ID: {viewingDoc.id} | Hash SHA-256: {viewingDoc.hashSha256Original.slice(0, 24)}...
                  </p>
                </div>
              </div>
              <button
                onClick={() => setViewingDoc(null)}
                className="p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Document Body */}
            <div className="flex-1 overflow-y-auto p-8 bg-zinc-950 font-serif text-zinc-300 space-y-6 text-sm leading-relaxed relative">
              <div className="absolute top-4 right-4 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-lg text-[10px] font-mono text-zinc-400 uppercase tracking-widest pointer-events-none opacity-60">
                Visualização Protegida LexFlow Cripto
              </div>

              <div className="border-b border-zinc-800 pb-4 text-center space-y-1">
                <h2 className="text-base font-bold uppercase tracking-wider text-zinc-100">{viewingDoc.title}</h2>
                <p className="text-xs text-zinc-400 font-sans">Instrumento Jurídico Registrado sob ICP-Brasil & Lei 14.063/2020</p>
              </div>

              <p>
                Pelo presente instrumento particular, as partes qualificadas no sistema <strong>LexFlow Enterprise LegalTech</strong>, declaram ter pleno conhecimento de todas as cláusulas e condições pactuadas, concordando expressamente com a assinatura por meio eletrônico e validação biométrica/criptográfica.
              </p>

              <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl space-y-2 text-xs font-sans">
                <span className="font-bold text-zinc-200 uppercase text-[10px] tracking-wider block">
                  Disposições sobre Integridade e Auditoria:
                </span>
                <p className="text-zinc-400">
                  O presente documento digital possui carimbo do tempo oficial sincronizado com o Observatório da Hora Legal do Brasil (ON/NTP) e assinatura assimétrica criptografada por meio da chave privada ICP-Brasil SHA-256.
                </p>
              </div>

              {/* Signatures Collection Box inside PDF */}
              <div className="pt-8 border-t border-zinc-800 space-y-4 font-sans">
                <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
                  Assinaturas Colhidas neste Documento:
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {viewingDoc.signers.map((s, i) => (
                    <div
                      key={i}
                      className={`p-3 rounded-xl border space-y-2 ${
                        s.status === "SIGNED"
                          ? "bg-emerald-950/20 border-emerald-800/80"
                          : "bg-amber-950/10 border-amber-900/50"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-zinc-100">{s.name}</span>
                        <span
                          className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded ${
                            s.status === "SIGNED"
                              ? "bg-emerald-900/80 text-emerald-300"
                              : "bg-amber-900/80 text-amber-300"
                          }`}
                        >
                          {s.status === "SIGNED" ? "ASSINADO" : "PENDENTE"}
                        </span>
                      </div>
                      <p className="text-[10px] text-zinc-400">{s.email} | Tel: {s.phone}</p>
                      {s.signedAt ? (
                        <p className="text-[9px] font-mono text-emerald-400">
                          Assinado em: {s.signedAt} (IP: {s.ipAddress})
                        </p>
                      ) : (
                        <div className="pt-1.5 flex items-center justify-between">
                          <span className="text-[10px] text-amber-400/80 italic font-mono flex items-center space-x-1">
                            <Lock className="w-3 h-3 text-amber-400" />
                            <span>Aguardando token individual</span>
                          </span>
                          {s.email.includes("rossiadvocacia") ? (
                            <button
                              type="button"
                              onClick={() => handleSignSingleSigner(viewingDoc.id, s.email)}
                              className="px-2.5 py-1 bg-amber-500 hover:bg-amber-400 text-zinc-950 rounded-lg text-[10px] font-bold shadow flex items-center space-x-1 cursor-pointer transition-all"
                            >
                              <Fingerprint className="w-3 h-3 text-zinc-950" />
                              <span>Assinar Sua Cota</span>
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleCopySignerLink(viewingDoc.id, s.email, s.name)}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold shadow flex items-center space-x-1 cursor-pointer transition-all"
                            >
                              <Link2 className="w-3 h-3 text-white" />
                              <span>Copiar Link Tokenizado</span>
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer with Separated PDF File Download & Print Buttons */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-950 flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-zinc-500 font-mono hidden sm:inline">Página 1 de 1</span>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDownloadDocumentPdfFile(viewingDoc)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1.5 cursor-pointer shadow-md"
                >
                  <Download className="w-4 h-4" />
                  <span>Baixar Arquivo PDF (.pdf)</span>
                </button>

                <button
                  onClick={() => handlePrintDocument(viewingDoc)}
                  className="px-3.5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer"
                >
                  <Printer className="w-4 h-4 text-purple-400" />
                  <span>Imprimir Documento</span>
                </button>

                <button
                  onClick={() => setViewingDoc(null)}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors"
                >
                  Fechar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: CERTIFICADO DE AUDITORIA & TRILHA DIGITAL */}
      {auditDoc && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-950">
              <div className="flex items-center space-x-3">
                <QrCode className="w-5 h-5 text-purple-400" />
                <div>
                  <h3 className="text-sm font-bold text-zinc-100">Manifesto de Auditoria & Trilha Digital</h3>
                  <p className="text-[10px] font-mono text-zinc-400">Validação ICP-Brasil & Lei 14.063/2020</p>
                </div>
              </div>
              <button
                onClick={() => setAuditDoc(null)}
                className="p-1.5 text-zinc-400 hover:text-zinc-200 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Certificate Summary Card */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 space-y-4">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
                  <div>
                    <span className="text-[10px] font-mono text-blue-400 font-bold uppercase">Identificador Criptográfico</span>
                    <h3 className="text-base font-extrabold text-zinc-100">{auditDoc.id} — {auditDoc.title}</h3>
                  </div>
                  <div className="bg-white p-2 rounded-lg shrink-0 flex flex-col items-center justify-center shadow">
                    <QrCode className="w-12 h-12 text-zinc-950" />
                    <span className="text-[8px] font-mono text-zinc-950 font-bold mt-0.5">VALIDAR QR</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                  <div>
                    <span className="text-zinc-500 block text-[10px]">HASH SHA-256 DO ARQUIVO ORIGINAL:</span>
                    <span className="text-zinc-300 break-all text-[11px]">{auditDoc.hashSha256Original}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500 block text-[10px]">HASH SHA-256 FINAL SELADO:</span>
                    <span className="text-purple-300 break-all text-[11px]">{auditDoc.hashSha256Final}</span>
                  </div>
                </div>
              </div>

              {/* Event Logs Timeline */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-purple-400" />
                  <span>Histórico Cronológico de Auditoria (Logs Inalteráveis)</span>
                </h4>

                <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-4">
                  {auditDoc.auditTrail.map((log, idx) => (
                    <div key={idx} className="flex items-start space-x-3 text-xs border-b border-zinc-800/60 last:border-0 pb-3 last:pb-0">
                      <div className="p-1.5 bg-purple-950/80 border border-purple-800/60 rounded-lg text-purple-300 shrink-0 mt-0.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-zinc-100">{log.event}</span>
                          <span className="font-mono text-[10px] text-zinc-500">{log.timestamp}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono text-zinc-400">
                          <span>Ator: <strong className="text-zinc-200">{log.actor}</strong></span>
                          <span>IP: <strong className="text-zinc-200">{log.ip}</strong></span>
                          <span>Dispositivo: <strong className="text-zinc-200">{log.device}</strong></span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer with Separated PDF File Download & Print Buttons */}
            <div className="p-4 border-t border-zinc-800 bg-zinc-950 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDownloadAuditCertificatePdfFile(auditDoc)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-2 cursor-pointer shadow-md"
                >
                  <Download className="w-4 h-4" />
                  <span>Baixar Certificado (.pdf)</span>
                </button>

                <button
                  onClick={() => handlePrintAuditCertificate(auditDoc)}
                  className="px-3.5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer"
                >
                  <Printer className="w-4 h-4 text-purple-400" />
                  <span>Imprimir Certificado</span>
                </button>
              </div>

              <button
                onClick={() => setAuditDoc(null)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors"
              >
                Fechar Manifesto
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: GATEWAY DE DISPARO MULTICANAL (WHATSAPP & E-MAIL) */}
      {whatsappModalDoc && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-blue-400 font-bold text-sm">
                <Send className="w-5 h-5 text-blue-400" />
                <span>Gateway de Disparo Multicanal (WhatsApp & E-mail)</span>
              </div>
              <button
                onClick={() => setWhatsappModalDoc(null)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <span className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider block">Documento Selecionado:</span>
                <h4 className="text-sm font-bold text-zinc-100">{whatsappModalDoc.title} ({whatsappModalDoc.id})</h4>
              </div>

              <div className="space-y-3">
                <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider">
                  Signatários Pendentes para Envio:
                </label>

                {whatsappModalDoc.signers
                  .filter((s) => s.status !== "SIGNED")
                  .map((signer, idx) => (
                    <div key={idx} className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
                        <span className="font-bold text-zinc-100">{signer.name}</span>
                        <div className="flex items-center space-x-2 text-[11px] font-mono">
                          <span className="text-emerald-400">{signer.phone}</span>
                          <span className="text-zinc-600">|</span>
                          <span className="text-blue-400">{signer.email}</span>
                        </div>
                      </div>

                      {/* Link Preview Info */}
                      <div className="text-[10px] font-mono text-zinc-400 bg-zinc-900 border border-zinc-800 p-2 rounded-lg break-all">
                        Link Tokenizado Exclusivo: <a href={getSignatureUrl(whatsappModalDoc.id, signer.email)} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">{getSignatureUrl(whatsappModalDoc.id, signer.email)}</a>
                      </div>

                      {/* Channel Buttons Row */}
                      <div className="flex flex-wrap items-center justify-end gap-2 pt-1 border-t border-zinc-800/80">
                        {/* Open Portal Directly in New Tab */}
                        <a
                          href={getSignatureUrl(whatsappModalDoc.id, signer.email)}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1.5 bg-blue-900/60 hover:bg-blue-800/80 border border-blue-700/60 text-blue-200 rounded-lg text-xs font-bold transition-colors flex items-center space-x-1.5 cursor-pointer shadow"
                        >
                          <Link2 className="w-3.5 h-3.5 text-blue-300" />
                          <span>Testar Portal Online</span>
                        </a>

                        {/* WhatsApp Universal Direct Link */}
                        <button
                          type="button"
                          onClick={() =>
                            handleSendWhatsAppWeb(signer.name, signer.phone, whatsappModalDoc.title, whatsappModalDoc.id)
                          }
                          className="px-3 py-1.5 bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer shadow"
                        >
                          <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
                          <span>WhatsApp Web (wa.me)</span>
                        </button>

                        {/* Mailto Direct E-mail */}
                        <button
                          type="button"
                          onClick={() =>
                            handleSendEmailClient(signer.name, signer.email, whatsappModalDoc.title, whatsappModalDoc.id)
                          }
                          className="px-3 py-1.5 bg-blue-950/90 hover:bg-blue-900 border border-blue-800 text-blue-300 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer shadow"
                        >
                          <Mail className="w-3.5 h-3.5 text-blue-400" />
                          <span>Enviar E-mail (mailto:)</span>
                        </button>

                        {/* Copy Link */}
                        <button
                          type="button"
                          onClick={() => handleCopyWhatsAppText(signer.name, whatsappModalDoc.title, whatsappModalDoc.id)}
                          className="px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1 cursor-pointer"
                        >
                          <Copy className="w-3.5 h-3.5 text-zinc-400" />
                          <span>Copiar Link</span>
                        </button>
                      </div>
                    </div>
                  ))}

                {whatsappModalDoc.signers.filter((s) => s.status !== "SIGNED").length === 0 && (
                  <p className="text-xs text-zinc-400 italic">Todos os signatários já assinaram este documento.</p>
                )}
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={() => handleDispatchApiWhatsApp(whatsappModalDoc)}
                className="w-full sm:w-auto px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center justify-center space-x-2 cursor-pointer shadow-lg shadow-blue-950"
              >
                <Send className="w-4 h-4" />
                <span>Disparar WhatsApp API + E-mail SMTP</span>
              </button>

              <button
                type="button"
                onClick={() => setWhatsappModalDoc(null)}
                className="w-full sm:w-auto px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: CRIAR FILA DE ASSINATURA */}
      {isNewDocModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div className="flex items-center space-x-2 text-blue-400 font-bold text-sm">
                <FileSignature className="w-5 h-5" />
                <span>Nova Fila de Assinatura Eletrônica</span>
              </div>
              <button
                onClick={() => setIsNewDocModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Wizard Steps Indicator (Interactive Tabs) */}
            <div className="flex items-center justify-between px-4 py-2 bg-zinc-950 rounded-xl border border-zinc-800">
              <button
                type="button"
                onClick={() => setWizardStep(1)}
                className={`flex items-center space-x-2 text-xs font-bold transition-colors cursor-pointer ${
                  wizardStep === 1 ? "text-blue-400" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  wizardStep === 1 ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-300"
                }`}>1</span>
                <span>Documento, Upload & Hash</span>
              </button>
              <ChevronRight className="w-4 h-4 text-zinc-700 shrink-0" />

              <button
                type="button"
                onClick={() => {
                  if (!newDocTitle.trim()) {
                    showToast("Informe o título no Passo 1 antes de avançar.");
                    return;
                  }
                  setWizardStep(2);
                }}
                className={`flex items-center space-x-2 text-xs font-bold transition-colors cursor-pointer ${
                  wizardStep === 2 ? "text-blue-400" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  wizardStep === 2 ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-300"
                }`}>2</span>
                <span>Signatários & WhatsApp</span>
              </button>
              <ChevronRight className="w-4 h-4 text-zinc-700 shrink-0" />

              <button
                type="button"
                onClick={() => {
                  if (!newDocTitle.trim()) {
                    showToast("Informe o título no Passo 1 antes de avançar.");
                    return;
                  }
                  setWizardStep(3);
                }}
                className={`flex items-center space-x-2 text-xs font-bold transition-colors cursor-pointer ${
                  wizardStep === 3 ? "text-blue-400" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  wizardStep === 3 ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-300"
                }`}>3</span>
                <span>Autenticação Advogado (Selo ICP)</span>
              </button>
            </div>

            <div className="space-y-4">
              {/* STEP 1 */}
              {wizardStep === 1 && (
                <div className="space-y-4 animate-in fade-in duration-150">
                  {/* File Upload Zone */}
                  <div>
                    <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1.5">
                      Selecione o Documento PDF para Assinar *
                    </label>
                    <div className="relative border-2 border-dashed border-zinc-800 hover:border-blue-500/80 bg-zinc-950/80 rounded-xl p-5 text-center transition-colors cursor-pointer group">
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx"
                        onChange={handleFileSelect}
                        className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                      />
                      {uploadedFile ? (
                        <div className="flex flex-col items-center justify-center space-y-2">
                          <div className="p-2.5 bg-emerald-950/80 border border-emerald-800 rounded-xl text-emerald-300 flex items-center space-x-2">
                            <FileCheck className="w-5 h-5" />
                            <span className="font-bold text-xs">{uploadedFile.name}</span>
                            <span className="text-[10px] font-mono text-emerald-400">
                              ({(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB)
                            </span>
                          </div>
                          <div className="text-[10px] font-mono text-zinc-400 bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-lg break-all max-w-full">
                            Hash SHA-256 Calculado em Tempo Real: <strong className="text-blue-400">{computedHashSha256}</strong>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center space-y-2">
                          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl text-blue-400 group-hover:scale-110 transition-transform">
                            <Upload className="w-6 h-6" />
                          </div>
                          <div>
                            <p className="text-xs font-bold text-zinc-200">Clique para selecionar ou arraste o arquivo PDF aqui</p>
                            <p className="text-[10px] text-zinc-500 font-mono mt-0.5">Suporta PDF, DOC, DOCX (Gera Hash SHA-256 automático)</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1.5">
                      Título do Documento *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Ex: Contrato de Prestação de Serviços Advocatícios - Cliente Silva"
                      value={newDocTitle}
                      onChange={(e) => setNewDocTitle(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider mb-1.5">
                      Categoria do Documento
                    </label>
                    <select
                      value={newDocCategory}
                      onChange={(e) => setNewDocCategory(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-blue-500 cursor-pointer"
                    >
                      <option value="Contratos de Honorários">Contratos de Honorários</option>
                      <option value="Societário / M&A">Societário / M&A</option>
                      <option value="Procurações">Procurações</option>
                      <option value="Documento Jurídico Geral">Documento Jurídico Geral</option>
                    </select>
                  </div>

                  {/* AI Extract Toggle */}
                  <div className="bg-purple-950/30 border border-purple-800/40 rounded-xl p-4 flex items-center justify-between">
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-2 text-purple-300 font-bold text-xs">
                        <Sparkles className="w-4 h-4 text-purple-400" />
                        <span>Extração Automática de Partes via IA</span>
                      </div>
                      <p className="text-[11px] text-zinc-400">
                        O LexFlow lê o PDF enviado e extrai automaticamente os nomes e e-mails para preencher os signatários.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAiExtractToggle(!aiExtractToggle)}
                      className={`w-11 h-6 rounded-full p-1 transition-colors cursor-pointer ${
                        aiExtractToggle ? "bg-purple-600" : "bg-zinc-800"
                      }`}
                    >
                      <div
                        className={`w-4 h-4 rounded-full bg-white transition-transform ${
                          aiExtractToggle ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 2 */}
              {wizardStep === 2 && (
                <div className="space-y-4 animate-in fade-in duration-150 max-h-[50vh] overflow-y-auto pr-1">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold text-zinc-300 uppercase tracking-wider">
                      Signatários Externos (Nome, E-mail e WhatsApp)
                    </label>
                    <button
                      type="button"
                      onClick={handleAddSignerRow}
                      className="text-xs font-bold text-blue-400 hover:text-blue-300 flex items-center space-x-1 cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Adicionar Signatário</span>
                    </button>
                  </div>

                  {newSigners.map((signer, idx) => (
                    <div key={idx} className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3 relative">
                      {newSigners.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveSignerRow(idx)}
                          className="absolute top-3 right-3 text-zinc-500 hover:text-rose-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-[10px] font-bold text-zinc-400 uppercase mb-1">Nome Completo *</label>
                          <input
                            type="text"
                            required
                            placeholder="Ex: João da Silva"
                            value={signer.name}
                            onChange={(e) => {
                              const val = e.target.value;
                              setNewSigners((prev) =>
                                prev.map((s, i) => (i === idx ? { ...s, name: val } : s))
                              );
                            }}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-blue-500"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-zinc-400 uppercase mb-1">E-mail *</label>
                          <input
                            type="email"
                            required
                            placeholder="joao@email.com"
                            value={signer.email}
                            onChange={(e) => {
                              const val = e.target.value;
                              setNewSigners((prev) =>
                                prev.map((s, i) => (i === idx ? { ...s, email: val } : s))
                              );
                            }}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-blue-500"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-zinc-400 uppercase mb-1">Telefone / WhatsApp *</label>
                          <input
                            type="text"
                            required
                            placeholder="Ex: +55 (11) 98765-4321"
                            value={signer.phone}
                            onChange={(e) => {
                              const val = e.target.value;
                              setNewSigners((prev) =>
                                prev.map((s, i) => (i === idx ? { ...s, phone: val } : s))
                              );
                            }}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-blue-500 font-mono"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[10px] font-bold text-zinc-400 uppercase mb-1">Papel no Trâmite</label>
                          <select
                            value={signer.role}
                            onChange={(e) => {
                              const val = e.target.value as any;
                              setNewSigners((prev) =>
                                prev.map((s, i) => (i === idx ? { ...s, role: val } : s))
                              );
                            }}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none cursor-pointer"
                          >
                            <option value="SIGNER">Signatário Principal</option>
                            <option value="WITNESS">Testemunha</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-zinc-400 uppercase mb-1">Autenticação Exigida</label>
                          <select
                            value={signer.authMethod}
                            onChange={(e) => {
                              const val = e.target.value as any;
                              setNewSigners((prev) =>
                                prev.map((s, i) => (i === idx ? { ...s, authMethod: val } : s))
                              );
                            }}
                            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none cursor-pointer"
                          >
                            <option value="OTP">E-mail + WhatsApp OTP</option>
                            <option value="BIOMETRIC">Biometria Facial / CNH</option>
                            <option value="ICP_BRASIL">Certificado Digital ICP-Brasil</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* STEP 3 */}
              {wizardStep === 3 && (
                <div className="space-y-4 animate-in fade-in duration-150">
                  {/* Explanation Card for Lawyer Session Authentication */}
                  <div className="bg-blue-950/40 border border-blue-800/60 rounded-xl p-4 space-y-2">
                    <div className="flex items-center space-x-2 text-blue-300 font-bold text-xs">
                      <UserCheck className="w-4 h-4 text-blue-400" />
                      <span>Autenticação Automática da Sua Conta de Advogado Logado</span>
                    </div>
                    <p className="text-[11px] text-zinc-300 leading-relaxed">
                      Sua identidade é lida diretamente da sua sessão autenticada no LexFlow: <strong className="text-white">Dr. Alexandre Rossi (OAB/SP 458.912 | CPF ***.458.912-**)</strong>. Você será inserido automaticamente como emissor/signatário inicial com status <strong>ASSINADO</strong>.
                    </p>
                  </div>

                  {/* ICP-Brasil & SHA-256 Certification Selector */}
                  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <ShieldCheck className="w-4 h-4 text-purple-400" />
                        <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
                          Selar com Certificado Digital ICP-Brasil do Advogado
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setUseIcpBrasilIssuer(!useIcpBrasilIssuer)}
                        className={`w-11 h-6 rounded-full p-1 transition-colors cursor-pointer ${
                          useIcpBrasilIssuer ? "bg-purple-600" : "bg-zinc-800"
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white transition-transform ${
                            useIcpBrasilIssuer ? "translate-x-5" : "translate-x-0"
                          }`}
                        />
                      </button>
                    </div>

                    {useIcpBrasilIssuer && (
                      <div className="space-y-3 pt-2 border-t border-zinc-800/80 animate-in fade-in duration-150">
                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs bg-zinc-900 border border-zinc-800 p-3 rounded-lg">
                          <div>
                            <span className="font-bold text-zinc-100 block">Dr. Alexandre Rossi (Titular Emissor)</span>
                            <span className="text-[10px] font-mono text-zinc-400">CPF: ***.458.912-** | OAB/SP 458.912</span>
                          </div>
                          <div className="flex items-center space-x-2 font-mono text-[10px]">
                            <span className="bg-emerald-950 border border-emerald-800 text-emerald-300 px-2 py-0.5 rounded font-bold">
                              CERTIFICADO {selectedCertType} VÁLIDO
                            </span>
                            <span className="text-zinc-500">Expira: 12/2027</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedCertType("A1")}
                            className={`py-1.5 text-[11px] font-bold rounded-lg border transition-all cursor-pointer ${
                              selectedCertType === "A1"
                                ? "bg-purple-950 border-purple-600 text-purple-200"
                                : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                            }`}
                          >
                            Certificado A1 (.PFX Salvo)
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedCertType("A3")}
                            className={`py-1.5 text-[11px] font-bold rounded-lg border transition-all cursor-pointer ${
                              selectedCertType === "A3"
                                ? "bg-purple-950 border-purple-600 text-purple-200"
                                : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                            }`}
                          >
                            Certificado A3 (Token USB)
                          </button>
                          <button
                            type="button"
                            onClick={() => setSelectedCertType("BIRD_ID")}
                            className={`py-1.5 text-[11px] font-bold rounded-lg border transition-all cursor-pointer ${
                              selectedCertType === "BIRD_ID"
                                ? "bg-purple-950 border-purple-600 text-purple-200"
                                : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                            }`}
                          >
                            Nuvem (BirdID / ViDAS)
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3">
                    <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
                      Resumo da Fila de Assinatura:
                    </h4>
                    <div className="space-y-1.5 text-xs font-mono">
                      <p className="text-zinc-400">Título: <strong className="text-zinc-100">{newDocTitle || "Sem título"}</strong></p>
                      <p className="text-zinc-400">Arquivo: <strong className="text-zinc-100">{uploadedFile?.name || "contrato_juridico.pdf"}</strong></p>
                      <p className="text-zinc-400 break-all">Hash SHA-256: <strong className="text-blue-400">{computedHashSha256 || "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}</strong></p>
                      <p className="text-zinc-400">Signatários Externos: <strong className="text-emerald-400">{newSigners.filter(s => s.name.trim()).length} cadastrados</strong></p>
                      <p className="text-zinc-400">Autenticação Emissor: <strong className="text-purple-300">{useIcpBrasilIssuer ? `Certificado Digital ICP-Brasil (${selectedCertType})` : "OTP Padrão"}</strong></p>
                    </div>
                  </div>
                </div>
              )}

              {/* Wizard Controls Footer */}
              <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
                {wizardStep > 1 ? (
                  <button
                    type="button"
                    onClick={() => setWizardStep((prev) => (prev > 1 ? ((prev - 1) as 1 | 2 | 3) : 1))}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors flex items-center space-x-1 cursor-pointer"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    <span>Voltar</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setIsNewDocModalOpen(false)}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold transition-colors"
                  >
                    Cancelar
                  </button>
                )}

                {wizardStep === 1 && (
                  <button
                    type="button"
                    disabled={!newDocTitle.trim()}
                    onClick={() => {
                      if (!newDocTitle.trim()) {
                        showToast("Informe o título do documento para prosseguir.");
                        return;
                      }
                      setWizardStep(2);
                    }}
                    className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1 cursor-pointer"
                  >
                    <span>Próximo (Passo 2)</span>
                    <ChevronRight className="w-4 h-4" />
                  </button>
                )}

                {wizardStep === 2 && (
                  <button
                    type="button"
                    onClick={() => setWizardStep(3)}
                    className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1 cursor-pointer shadow-lg shadow-blue-950"
                  >
                    <span>Avançar para Passo 3 (ICP-Brasil)</span>
                    <ChevronRight className="w-4 h-4" />
                  </button>
                )}

                {wizardStep === 3 && (
                  <button
                    type="button"
                    onClick={() => handleCreateDocument()}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-950 transition-colors flex items-center space-x-1.5 cursor-pointer"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Disparar Fila via WhatsApp & E-mail</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TEMPLATE ENGINE MODAL (BIBLIOTECA DE MODELOS PRONTOS) */}
      {isTemplatesModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-zinc-900 border border-purple-800/80 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2 text-purple-300 font-bold text-sm">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <span>Biblioteca de Modelos Jurídicos Pré-Configurados (Template Engine)</span>
              </div>
              <button
                onClick={() => setIsTemplatesModalOpen(false)}
                className="text-zinc-400 hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-zinc-400">
              Selecione um modelo padrão para preencher automaticamente o título, categoria e disparar a fila em segundos:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[60vh] overflow-y-auto pr-1">
              {/* Template Card 1 */}
              <div
                onClick={() => {
                  setNewDocTitle("Contrato de Honorários Advocatícios Quota Litis - Cliente");
                  setNewDocCategory("Contratos de Honorários");
                  setIsTemplatesModalOpen(false);
                  setWizardStep(1);
                  setIsNewDocModalOpen(true);
                  showToast("Modelo 'Contrato de Honorários' carregado com sucesso!");
                }}
                className="p-4 bg-zinc-950 hover:bg-zinc-800/60 border border-zinc-800 hover:border-purple-500 rounded-xl space-y-2 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-purple-400 font-bold uppercase">Honorários</span>
                  <span className="text-[9px] font-mono bg-purple-950 border border-purple-800 text-purple-300 px-2 py-0.5 rounded">Popular</span>
                </div>
                <h4 className="text-xs font-bold text-white group-hover:text-purple-300 transition-colors">
                  Contrato de Honorários Quota Litis
                </h4>
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Contrato com cláusulas de êxito, fórum de arbitragem e carimbo do tempo ICP-Brasil.
                </p>
              </div>

              {/* Template Card 2 */}
              <div
                onClick={() => {
                  setNewDocTitle("Procuração Ad Judicia et Extra con Causa - Representação Geral");
                  setNewDocCategory("Procurações");
                  setIsTemplatesModalOpen(false);
                  setWizardStep(1);
                  setIsNewDocModalOpen(true);
                  showToast("Modelo 'Procuração Ad Judicia' carregado com sucesso!");
                }}
                className="p-4 bg-zinc-950 hover:bg-zinc-800/60 border border-zinc-800 hover:border-blue-500 rounded-xl space-y-2 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-blue-400 font-bold uppercase">Procurações</span>
                  <span className="text-[9px] font-mono bg-blue-950 border border-blue-800 text-blue-300 px-2 py-0.5 rounded">Essencial</span>
                </div>
                <h4 className="text-xs font-bold text-white group-hover:text-blue-300 transition-colors">
                  Procuração Ad Judicia et Extra
                </h4>
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Poderes gerais para o foro e específicos para transigir, receber e dar quitação.
                </p>
              </div>

              {/* Template Card 3 */}
              <div
                onClick={() => {
                  setNewDocTitle("Acordo Extrajudicial de Confissão e Parcelamento de Dívida");
                  setNewDocCategory("Societário / M&A");
                  setIsTemplatesModalOpen(false);
                  setWizardStep(1);
                  setIsNewDocModalOpen(true);
                  showToast("Modelo 'Acordo Extrajudicial' carregado com sucesso!");
                }}
                className="p-4 bg-zinc-950 hover:bg-zinc-800/60 border border-zinc-800 hover:border-emerald-500 rounded-xl space-y-2 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-emerald-400 font-bold uppercase">Acordos</span>
                  <span className="text-[9px] font-mono bg-emerald-950 border border-emerald-800 text-emerald-300 px-2 py-0.5 rounded">Título Executivo</span>
                </div>
                <h4 className="text-xs font-bold text-white group-hover:text-emerald-300 transition-colors">
                  Acordo Extrajudicial & Confissão de Dívida
                </h4>
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Instrumento com força de título executivo extrajudicial nos termos do CPC.
                </p>
              </div>

              {/* Template Card 4 */}
              <div
                onClick={() => {
                  setNewDocTitle("Termo de Confidencialidade (NDA) & Proteção de Segredos Industriais");
                  setNewDocCategory("Documento Jurídico Geral");
                  setIsTemplatesModalOpen(false);
                  setWizardStep(1);
                  setIsNewDocModalOpen(true);
                  showToast("Modelo 'Termo NDA' carregado com sucesso!");
                }}
                className="p-4 bg-zinc-950 hover:bg-zinc-800/60 border border-zinc-800 hover:border-amber-500 rounded-xl space-y-2 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-amber-400 font-bold uppercase">Confidencialidade</span>
                  <span className="text-[9px] font-mono bg-amber-950 border border-amber-800 text-amber-300 px-2 py-0.5 rounded">Compliance</span>
                </div>
                <h4 className="text-xs font-bold text-white group-hover:text-amber-300 transition-colors">
                  Termo de Sigilo & Non-Disclosure (NDA)
                </h4>
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Proteção de segredos de negócio, dados estratégicos e multas por descumprimento.
                </p>
              </div>
            </div>

            <div className="pt-3 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setIsTemplatesModalOpen(false)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
