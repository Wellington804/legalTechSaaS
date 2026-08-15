"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, FileText, ShieldCheck } from "lucide-react";
import { DeclarationPreview } from "@/components/oab/declaration-preview";

export default function DeclaracoesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/oab-hub"
          className="text-xs font-semibold text-zinc-400 hover:text-zinc-200 flex items-center space-x-1"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Voltar ao Hub OAB</span>
        </Link>

        <div className="flex items-center space-x-2 text-xs text-blue-400 font-mono">
          <ShieldCheck className="w-4 h-4" />
          <span>Assinatura Digital SHA-256 Nativa</span>
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <h1 className="text-xl font-bold text-zinc-100 flex items-center space-x-2">
          <FileText className="w-5 h-5 text-purple-400" />
          <span>Gerador de Declarações Oficiais da OAB</span>
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-2xl">
          Gere em PDF formatado as declarações de Idoneidade Moral (Art. 8º, VI, Lei 8.906/94) e Não Incompatibilidade (Arts. 27 a 30).
        </p>
      </div>

      <DeclarationPreview />
    </div>
  );
}
