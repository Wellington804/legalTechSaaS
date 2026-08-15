"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Search, X, FileText, User, ShieldAlert, BookOpen, ArrowRight, CornerDownLeft, ArrowUp, ArrowDown } from "lucide-react";

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function GlobalSearchModal({ isOpen, onClose }: GlobalSearchModalProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();

  const mockResults = [
    {
      type: "Petição AI",
      title: "Petição Inicial - Ação de Restituição Tributária (IBS/CBS)",
      category: "Módulo 3: Petições",
      link: "/dashboard/petitions/editor",
      icon: FileText,
    },
    {
      type: "Conflito Ético",
      title: "Verificação Global de Conflito de Interesses - Empresa Alpha Corp",
      category: "Módulo 5: Compliance",
      link: "/dashboard/conflitos",
      icon: ShieldAlert,
    },
    {
      type: "OAB Hub",
      title: "Checklist de Inscrição Originária OAB/SP & Requisitos FGV",
      category: "Módulo 12: Hub OAB",
      link: "/oab-hub/checklist",
      icon: BookOpen,
    },
    {
      type: "Cliente",
      title: "Carlos Eduardo Silva - CPF 123.456.789-00",
      category: "Módulo 2: CRM",
      link: "/dashboard/crm",
      icon: User,
    },
  ];

  const filtered = query.trim()
    ? mockResults.filter(
        (r) =>
          r.title.toLowerCase().includes(query.toLowerCase()) ||
          r.category.toLowerCase().includes(query.toLowerCase())
      )
    : mockResults;

  // Resetar o índice selecionado quando a busca mudar
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Teclas de atalho: ESC para fechar, setas Cima/Baixo para navegar e ENTER para selecionar
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (filtered.length > 0 ? (prev + 1) % filtered.length : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (filtered.length > 0 ? (prev - 1 + filtered.length) % filtered.length : 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered.length > 0 && filtered[selectedIndex]) {
          const selected = filtered[selectedIndex];
          router.push(selected.link);
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filtered, selectedIndex, onClose, router]);

  if (!isOpen) return null;

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-start justify-center pt-20 p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl space-y-0"
      >
        {/* Search Input Bar */}
        <div className="p-4 border-b border-zinc-800 flex items-center space-x-3 bg-zinc-900/90">
          <Search className="w-5 h-5 text-blue-400 shrink-0" />
          <input
            type="text"
            autoFocus
            placeholder="Busca Semântica GED com pgvector (ex: petição tributária, contrato SUA, CPF)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none"
          />
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 p-1 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="p-3 max-h-96 overflow-y-auto space-y-1">
          {filtered.length > 0 ? (
            filtered.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={idx}
                  onClick={() => {
                    router.push(item.link);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between p-3 rounded-xl transition-all cursor-pointer ${
                    isSelected
                      ? "bg-blue-600/20 text-blue-200 border border-blue-500/40 shadow-sm"
                      : "hover:bg-zinc-900/80 text-zinc-300 border border-transparent"
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`p-2 rounded-lg border transition-colors ${
                        isSelected
                          ? "bg-blue-600 text-white border-blue-400"
                          : "bg-zinc-900 border-zinc-800 text-blue-400"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <p className={`text-xs font-semibold ${isSelected ? "text-blue-200 font-bold" : "text-zinc-200"}`}>
                        {item.title}
                      </p>
                      <span className="text-[10px] text-zinc-500 font-mono">{item.category}</span>
                    </div>
                  </div>
                  <div
                    className={`flex items-center space-x-1 text-xs ${
                      isSelected ? "text-blue-300 font-bold" : "text-zinc-500"
                    }`}
                  >
                    <span>Acessar</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-8 text-center text-xs text-zinc-500">
              Nenhum resultado encontrado no repositório pgvector para "{query}".
            </div>
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="p-3 bg-zinc-900/90 border-t border-zinc-800 flex items-center justify-between text-[11px] text-zinc-400 font-mono">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1">
              <span className="px-1.5 py-0.5 bg-zinc-950 border border-zinc-800 rounded text-zinc-300">ESC</span>
              <span>para fechar</span>
            </div>
            <div className="flex items-center space-x-1">
              <span className="px-1 py-0.5 bg-zinc-950 border border-zinc-800 rounded text-zinc-300 flex items-center">
                <ArrowUp className="w-2.5 h-2.5" />
                <ArrowDown className="w-2.5 h-2.5" />
              </span>
              <span>para navegar</span>
            </div>
          </div>

          <div className="flex items-center space-x-1">
            <span className="px-1.5 py-0.5 bg-blue-950 border border-blue-800 text-blue-300 rounded font-bold flex items-center gap-1">
              <CornerDownLeft className="w-3 h-3" /> Enter
            </span>
            <span>para selecionar</span>
          </div>
        </div>
      </div>
    </div>
  );
}
