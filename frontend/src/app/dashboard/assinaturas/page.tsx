"use client";

import React, { useState } from "react";
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
} from "lucide-react";

interface DocSignature {
  id: string;
  title: string;
  category: string;
  createdAt: string;
  signers: { name: string; status: "SIGNED" | "PENDING" }[];
  hashSha256: string;
  status: "COMPLETED" | "IN_PROGRESS";
}

export default function AssinaturasPage() {
  const [documents, setDocuments] = useState<DocSignature[]>([
    {
      id: "DOC-9948",
      title: "Contrato de Honorários Advocatícios Quota Litis - Cliente Silva",
      category: "Contratos de Honorários",
      createdAt: "12/08/2026",
      signers: [
        { name: "Dr. Alexandre Rossi", status: "SIGNED" },
        { name: "Marcos Paulo Silva", status: "SIGNED" },
      ],
      hashSha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      status: "COMPLETED",
    },
    {
      id: "DOC-9949",
      title: "Acordo Extrajudicial de Dissolução Societária - TechCorp",
      category: "Societário / M&A",
      createdAt: "11/08/2026",
      signers: [
        { name: "Dr. Alexandre Rossi", status: "SIGNED" },
        { name: "Eduardo Fonseca", status: "PENDING" },
        { name: "Patrícia Lima", status: "PENDING" },
      ],
      hashSha256: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
      status: "IN_PROGRESS",
    },
  ]);

  const [newDocTitle, setNewDocTitle] = useState("");

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDocTitle.trim()) return;

    const newDoc: DocSignature = {
      id: `DOC-${Math.floor(1000 + Math.random() * 9000)}`,
      title: newDocTitle,
      category: "Documento Jurídico Geral",
      createdAt: new Date().toLocaleDateString("pt-BR"),
      signers: [
        { name: "Dr. Alexandre Rossi", status: "SIGNED" },
        { name: "Parte Signatária Requerida", status: "PENDING" },
      ],
      hashSha256: "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
      status: "IN_PROGRESS",
    };

    setDocuments([newDoc, ...documents]);
    setNewDocTitle("");
    alert("Novo documento enviado com sucesso para a fila de Assinatura Eletrônica!");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-purple-400 font-mono uppercase tracking-wider mb-2">
          <FileSignature className="w-4 h-4 text-purple-400" />
          <span>Módulo de Validação Criptográfica ICP-Brasil & Lei 14.063/2020</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Assinatura Eletrônica & Trilha de Auditoria Digital
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Assinatura digital avançada e qualificada com carimbo do tempo, integridade garantida por SHA-256 e validade jurídica plena em todo o território nacional.
        </p>
      </div>

      {/* Upload New Document Box */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center space-x-2">
          <Upload className="w-4 h-4 text-blue-500" />
          <span>Enviar Novo Documento para Assinatura</span>
        </h3>

        <form onSubmit={handleUpload} className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={newDocTitle}
            onChange={(e) => setNewDocTitle(e.target.value)}
            placeholder="Título do Contrato, Procuração ou Termo Aditivo..."
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-2.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          <button
            type="submit"
            disabled={!newDocTitle.trim()}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-blue-950 transition-colors flex items-center justify-center space-x-2 shrink-0"
          >
            <Plus className="w-4 h-4" />
            <span>Criar Fila de Assinatura</span>
          </button>
        </form>
      </div>

      {/* Documents Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
        <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider flex items-center justify-between">
          <span>Documentos em Trâmite de Assinatura</span>
          <span className="text-[11px] font-mono text-zinc-500">{documents.length} Documentos Ativos</span>
        </h3>

        <div className="space-y-4">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="bg-zinc-950 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2 max-w-xl">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs font-bold text-blue-400">{doc.id}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 font-mono text-zinc-400">
                    {doc.category}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500">{doc.createdAt}</span>
                </div>

                <h4 className="text-sm font-bold text-zinc-100">{doc.title}</h4>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {doc.signers.map((s, idx) => (
                    <span
                      key={idx}
                      className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium border ${
                        s.status === "SIGNED"
                          ? "bg-emerald-950/80 border-emerald-800 text-emerald-300"
                          : "bg-amber-950/80 border-amber-800 text-amber-300"
                      }`}
                    >
                      {s.status === "SIGNED" ? <CheckCircle2 className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                      <span>
                        {s.name} ({s.status === "SIGNED" ? "Assinado" : "Pendente"})
                      </span>
                    </span>
                  ))}
                </div>

                <p className="text-[10px] font-mono text-zinc-500 truncate">
                  Hash SHA-256: <span className="text-zinc-400">{doc.hashSha256}</span>
                </p>
              </div>

              <div className="flex items-center space-x-2 shrink-0">
                <button
                  onClick={() => alert(`Baixando certificado de auditoria da assinatura digital para ${doc.id}`)}
                  className="px-3.5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg transition-colors flex items-center space-x-1.5"
                >
                  <Download className="w-3.5 h-3.5 text-blue-400" />
                  <span>Baixar Certificado</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
