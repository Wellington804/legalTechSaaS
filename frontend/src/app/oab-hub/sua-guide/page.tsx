"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Building, CheckCircle2 } from "lucide-react";
import { HonorariosTable } from "@/components/oab/honorarios-table";

export default function SuaGuidePage() {
  const steps = [
    {
      step: "01",
      title: "Definição do Nome Empresarial & Razão Social",
      desc: "A razão social da Sociedade Unipessoal de Advocacia (SUA) deve obrigatoriamente conter o nome do titular seguido da expressão 'Sociedade Unipessoal de Advocacia'.",
    },
    {
      step: "02",
      title: "Elaboração do Contrato Social Unipessoal",
      desc: "Modelo padronizado aprovado pela seccional da OAB. Capital social mínimo recomendado e enquadramento tributário no Simples Nacional (Anexo IV - alíquota inicial de 4.5%).",
    },
    {
      step: "03",
      title: "Protocolo na Comissão de Sociedade de Advogados (CSA/OAB)",
      desc: "Submissão digital do contrato via sistema da Seccional com desconto especial de até 25% para novos advogados cadastrados no programa Jovem Advogado.",
    },
    {
      step: "04",
      title: "Inscrição no CNPJ perante a Receita Federal",
      desc: "Emissão automatizada do CNPJ através do portal Redesim/DBE após a homologação e registro formal da OAB.",
    },
  ];

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
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-2 text-xs text-amber-400 font-mono uppercase mb-1">
          <Building className="w-4 h-4" />
          <span>Manual Prático de Sociedade & Tributação Jurídica</span>
        </div>
        <h1 className="text-xl font-bold text-zinc-100">
          Guia de Registro da Sociedade Unipessoal de Advocacia (SUA)
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl">
          Instruções passo a passo para constituição do seu CNPJ de advocacia individual (Lei 13.247/2016) com redução da carga tributária de 27.5% (PF) para 4.5% (PJ - Simples Nacional).
        </p>
      </div>

      {/* Steps Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {steps.map((s) => (
          <div key={s.step} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-2 relative overflow-hidden">
            <span className="absolute right-4 top-2 text-4xl font-extrabold text-zinc-800 font-mono select-none">
              {s.step}
            </span>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <h3 className="text-xs font-bold text-zinc-200">{s.title}</h3>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed pl-6">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* Tabela Ética Dinâmica e Configurável */}
      <HonorariosTable />
    </div>
  );
}

