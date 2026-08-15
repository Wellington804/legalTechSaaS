"use client";

import React, { useState, useEffect } from "react";
import { Search, X, MapPin, Check, Filter } from "lucide-react";
import { OAB_SECCIONAIS, OabSeccionalData, useOabStore } from "@/store/useOabStore";
import { formatCurrency } from "@/lib/utils";

interface StateSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function StateSelectorModal({ isOpen, onClose }: StateSelectorModalProps) {
  const { feeState, setFeeState } = useOabStore();
  const [search, setSearch] = useState("");
  const [selectedRegion, setSelectedRegion] = useState<string>("Todas");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const regions = ["Todas", "Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"];

  const filteredSeccionais = OAB_SECCIONAIS.filter((sec) => {
    const matchesSearch =
      sec.code.toLowerCase().includes(search.toLowerCase()) ||
      sec.name.toLowerCase().includes(search.toLowerCase()) ||
      sec.uf.toLowerCase().includes(search.toLowerCase());
    
    const matchesRegion = selectedRegion === "Todas" || sec.region === selectedRegion;

    return matchesSearch && matchesRegion;
  });

  const handleSelect = (sec: OabSeccionalData) => {
    setFeeState({ seccional: sec.code });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90 backdrop-blur">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <MapPin className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                Seccionais da OAB (27 Unidades Federativas)
              </h2>
              <p className="text-xs text-zinc-400">
                Selecione o estado onde deseja realizar a sua Inscrição Originária ou Suplementar
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search & Region Filter Bar */}
        <div className="p-4 bg-zinc-950/50 border-b border-zinc-800 space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Buscar por estado (ex: São Paulo, OAB/MG, RJ, DF)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-10 pr-9 py-2.5 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              autoFocus
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Region Tabs */}
          <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 scrollbar-none">
            <span className="text-[11px] font-semibold text-zinc-500 mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Região:
            </span>
            {regions.map((reg) => (
              <button
                key={reg}
                onClick={() => setSelectedRegion(reg)}
                className={`px-3 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  selectedRegion === reg
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-zinc-900 text-zinc-400 border border-zinc-800/80 hover:bg-zinc-800 hover:text-zinc-200"
                }`}
              >
                {reg}
              </button>
            ))}
          </div>
        </div>

        {/* State Grid */}
        <div className="p-5 overflow-y-auto max-h-[50vh] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredSeccionais.length > 0 ? (
            filteredSeccionais.map((sec) => {
              const isSelected = feeState.seccional === sec.code;
              return (
                <button
                  key={sec.code}
                  onClick={() => handleSelect(sec)}
                  className={`p-3.5 rounded-xl border text-left transition-all duration-150 relative flex flex-col justify-between group ${
                    isSelected
                      ? "bg-blue-600/15 border-blue-500/70 text-white shadow-lg shadow-blue-950/50"
                      : "bg-zinc-950/60 border-zinc-800/80 text-zinc-300 hover:bg-zinc-800/60 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-xs font-black tracking-wider text-blue-400 font-mono">
                        {sec.code}
                      </span>
                      <h3 className="text-xs font-semibold text-zinc-100 mt-0.5 group-hover:text-white">
                        {sec.name} ({sec.uf})
                      </h3>
                    </div>
                    {isSelected && (
                      <span className="p-1 bg-blue-600 rounded-full text-white">
                        <Check className="w-3.5 h-3.5" />
                      </span>
                    )}
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-zinc-800/60 flex items-center justify-between text-[11px]">
                    <span className="text-zinc-500 font-medium px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800">
                      {sec.region}
                    </span>
                    <span className="text-zinc-400 font-mono">
                      Anuidade Base: <strong className="text-zinc-200">{formatCurrency(sec.baseAnuidade)}</strong>
                    </span>
                  </div>
                </button>
              );
            })
          ) : (
            <div className="col-span-full py-12 text-center text-zinc-500">
              <p className="text-sm">Nenhuma seccional da OAB encontrada com "{search}".</p>
              <button
                onClick={() => {
                  setSearch("");
                  setSelectedRegion("Todas");
                }}
                className="mt-2 text-xs text-blue-400 hover:underline font-semibold"
              >
                Limpar filtros de busca
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-between text-xs text-zinc-400">
          <span>
            Exibindo <strong>{filteredSeccionais.length}</strong> de 27 seccionais estaduais da OAB
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl font-medium transition-colors"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
