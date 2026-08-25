"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Search, Command, LayoutDashboard, Briefcase, Scale, Calculator, ShieldAlert, FileSignature, Users, FileText, BarChart3, X } from "lucide-react";

interface CommandItem {
  id: string;
  title: string;
  category: string;
  path: string;
  icon: React.ReactNode;
}

const COMMANDS: CommandItem[] = [
  { id: "dash", title: "Visão Executiva & Métricas KPI", category: "Navegação", path: "/dashboard", icon: <LayoutDashboard className="w-4 h-4 text-amber-400" /> },
  { id: "crm", title: "CRM Jurídico & Funil de Oportunidades", category: "Navegação", path: "/dashboard/crm", icon: <Briefcase className="w-4 h-4 text-emerald-400" /> },
  { id: "oab", title: "Hub OAB — Guia de Inscrição & SUA", category: "Navegação", path: "/oab-hub/sua-guide", icon: <Scale className="w-4 h-4 text-blue-400" /> },
  { id: "calc", title: "Calculadora de Reforma Tributária (IBS/CBS)", category: "Ferramentas", path: "/dashboard/calculadora", icon: <Calculator className="w-4 h-4 text-purple-400" /> },
  { id: "conf", title: "Verificação Prévia de Éti-Conflitos", category: "Compliance", path: "/dashboard/conflitos", icon: <ShieldAlert className="w-4 h-4 text-rose-400" /> },
  { id: "sign", title: "Assinaturas Digitais & Hashes SHA-256", category: "Compliance", path: "/dashboard/assinaturas", icon: <FileSignature className="w-4 h-4 text-teal-400" /> },
  { id: "portal", title: "Portal Transparente do Cliente (IA)", category: "Atendimento", path: "/portal", icon: <Users className="w-4 h-4 text-cyan-400" /> },
  { id: "pet", title: "Gerador AI de Petições & Peças", category: "Inteligência", path: "/dashboard/petitions", icon: <FileText className="w-4 h-4 text-indigo-400" /> },
  { id: "juri", title: "Jurimetria & Análise Preditiva", category: "Analytics", path: "/dashboard/analytics", icon: <BarChart3 className="w-4 h-4 text-yellow-400" /> }
];

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const filteredCommands = COMMANDS.filter((cmd) =>
    cmd.title.toLowerCase().includes(query.toLowerCase()) ||
    cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (path: string) => {
    setIsOpen(false);
    setQuery("");
    router.push(path);
  };

  const handleListKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % (filteredCommands.length || 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % (filteredCommands.length || 1));
    } else if (e.key === "Enter" && filteredCommands[selectedIndex]) {
      e.preventDefault();
      handleSelect(filteredCommands[selectedIndex].path);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-zinc-900/90 border border-zinc-700/70 hover:border-amber-500/50 text-zinc-300 hover:text-white px-3.5 py-2 rounded-full shadow-2xl backdrop-blur-md text-xs font-medium transition-all group hover:scale-105"
        title="Atalho rápido (Cmd+K / Ctrl+K)"
      >
        <Command className="w-3.5 h-3.5 text-amber-400 group-hover:rotate-12 transition-transform" />
        <span>Comandos</span>
        <kbd className="bg-zinc-800 border border-zinc-700 px-1.5 py-0.5 rounded text-[10px] text-zinc-400 font-mono">⌘K</kbd>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-md flex items-start justify-center pt-20 p-4 animate-in fade-in duration-200">
      <div
        className="w-full max-w-xl bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden"
        onKeyDown={handleListKeyDown}
      >
        <div className="flex items-center px-4 border-b border-zinc-800 bg-zinc-950/50">
          <Search className="w-5 h-5 text-zinc-400 mr-3" />
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Digite um comando, tela ou funcionalidade... (ex: OAB, CRM, Calculadora)"
            className="w-full py-4 bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none"
            autoFocus
          />
          <button onClick={() => setIsOpen(false)} className="p-1 hover:bg-zinc-800 rounded-lg text-zinc-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-xs text-zinc-500">
              Nenhum comando encontrado para "{query}"
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => (
              <button
                key={cmd.id}
                onClick={() => handleSelect(cmd.path)}
                onMouseEnter={() => setSelectedIndex(idx)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs transition-colors ${
                  idx === selectedIndex ? "bg-amber-500/10 border border-amber-500/30 text-amber-300" : "text-zinc-300 hover:bg-zinc-800/60"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="p-1.5 bg-zinc-800/80 rounded-lg border border-zinc-700/50">{cmd.icon}</div>
                  <span className="font-medium">{cmd.title}</span>
                </div>
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono">{cmd.category}</span>
              </button>
            ))
          )}
        </div>

        <div className="px-4 py-2 bg-zinc-950 border-t border-zinc-800/80 flex items-center justify-between text-[11px] text-zinc-500 font-mono">
          <div className="flex items-center gap-2">
            <span><kbd className="bg-zinc-800 px-1 rounded">↑↓</kbd> navegar</span>
            <span><kbd className="bg-zinc-800 px-1 rounded">↵</kbd> selecionar</span>
          </div>
          <span>LegalTech SaaS High-Performance Engine</span>
        </div>
      </div>
    </div>
  );
}
