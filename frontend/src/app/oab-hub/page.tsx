"use client";

import React from "react";
import Link from "next/link";
import {
  Award,
  CheckSquare,
  FileText,
  Calculator,
  BookOpen,
  Building,
  ArrowRight,
} from "lucide-react";

export default function OabHubPage() {
  const modules = [
    {
      title: "Checklist de Inscrição Originária",
      desc: "Gestão completa dos 8 documentos obrigatórios pós-aprovação no Exame de Ordem com validação inteligente.",
      href: "/oab-hub/checklist",
      icon: CheckSquare,
      color: "text-blue-400",
      badge: "8 Itens Obrigatórios",
    },
    {
      title: "Gerador de Declarações (Arts. 27-30)",
      desc: "Emissão de Declarações de Idoneidade Moral e Não Incompatibilidade pré-preenchidas com assinatura SHA-256.",
      href: "/oab-hub/declaracoes",
      icon: FileText,
      color: "text-purple-400",
      badge: "Lei 8.906/94",
    },
    {
      title: "Calculadora & Painel de Custos",
      desc: "Simulador de taxa de requerimento, confecção da carteira e desconto do Jovem Advogado (anuidade proporcional).",
      href: "/oab-hub/calculadora",
      icon: Calculator,
      color: "text-emerald-400",
      badge: "Simulador 2026",
    },
    {
      title: "Guia SUA & Iniciação Profissional",
      desc: "Roteiro interativo de registro da Sociedade Unipessoal de Advocacia com até 25% de desconto e tabela de honorários.",
      href: "/oab-hub/sua-guide",
      icon: BookOpen,
      color: "text-amber-400",
      badge: "CNPJ de Advocacia",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6">
        <div className="flex items-center space-x-3 text-xs text-blue-400 font-mono uppercase tracking-wider mb-2">
          <Award className="w-4 h-4" />
          <span>Módulo 12 - Inscrição Principal & Novo Advogado</span>
        </div>
        <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
          Hub de Emissão de Carteira OAB & Iniciação Profissional
        </h1>
        <p className="text-xs text-zinc-400 mt-1 max-w-3xl leading-relaxed">
          Central completa de ferramentas para o novo advogado recém-aprovado no Exame de Ordem. Acompanhe a documentação para a seccional, simule descontos de anuidade e formalize sua Sociedade Unipessoal.
        </p>
      </div>

      {/* Grid of 4 Feature Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {modules.map((m) => {
          const Icon = m.icon;
          return (
            <Link
              key={m.title}
              href={m.href}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 hover:border-zinc-700 transition-all flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-center">
                    <Icon className={`w-5 h-5 ${m.color}`} />
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-zinc-950 border border-zinc-800 text-[10px] font-mono text-zinc-400">
                    {m.badge}
                  </span>
                </div>
                <h3 className="text-base font-bold text-zinc-100 group-hover:text-blue-400 transition-colors">
                  {m.title}
                </h3>
                <p className="text-xs text-zinc-400 mt-2 leading-relaxed">{m.desc}</p>
              </div>

              <div className="mt-6 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs font-semibold text-blue-400">
                <span>Acessar Ferramenta</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
