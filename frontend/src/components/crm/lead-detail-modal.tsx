"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Clock,
  DollarSign,
  User,
  MessageSquare,
  Trash2,
  CheckCircle2,
  ArrowRight,
  Sparkles,
  Edit3,
  Check,
} from "lucide-react";
import { LeadData } from "./new-lead-modal";
import { formatCurrency } from "@/lib/utils";

interface LeadDetailModalProps {
  lead: LeadData | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateStage: (leadId: string, newStageId: LeadData["stageId"]) => void;
  onDeleteLead: (leadId: string) => void;
  onUpdateNotes: (leadId: string, notes: string) => void;
}

export function LeadDetailModal({
  lead,
  isOpen,
  onClose,
  onUpdateStage,
  onDeleteLead,
  onUpdateNotes,
}: LeadDetailModalProps) {
  const [notesInput, setNotesInput] = useState("");
  const [isEditingNotes, setIsEditingNotes] = useState(false);

  useEffect(() => {
    if (lead) {
      setNotesInput(lead.notes || "");
    }
  }, [lead]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !lead) return null;

  const stages: { id: LeadData["stageId"]; label: string }[] = [
    { id: "novos", label: "Novos Leads" },
    { id: "qualificacao", label: "Em Qualificação" },
    { id: "proposta", label: "Proposta Enviada" },
    { id: "fechado", label: "Contrato Fechado" },
  ];

  const handleSaveNotes = () => {
    onUpdateNotes(lead.id, notesInput);
    setIsEditingNotes(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400 flex items-center justify-center font-bold text-sm">
              <User className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-zinc-100">{lead.name}</h2>
                <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded">
                  {lead.type}
                </span>
                {lead.temperature && (
                  <span className="px-2 py-0.5 bg-amber-950/80 text-amber-400 border border-amber-800/60 text-[10px] font-mono rounded">
                    {lead.temperature === "Quente" ? "🔥 Quente" : lead.temperature === "Morno" ? "⚡ Morno" : "❄️ Frio"}
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">Cadastrado em {lead.date}</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs">
          {/* Main Info */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3">
            <div className="flex justify-between items-start">
              <div>
                <span className="text-[10px] font-mono text-zinc-500 uppercase block">Serviço Pretendido</span>
                <h3 className="text-sm font-bold text-zinc-100 mt-0.5">{lead.subject}</h3>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-mono text-zinc-500 uppercase block">Valor Estimado</span>
                <span className="text-lg font-extrabold text-emerald-400 font-mono">
                  {formatCurrency(lead.value)}
                </span>
              </div>
            </div>
          </div>

          {/* Stage Controls */}
          <div className="space-y-2">
            <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
              Mover de Estágio no Funil
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {stages.map((stg) => {
                const isCurrent = lead.stageId === stg.id;
                return (
                  <button
                    key={stg.id}
                    onClick={() => onUpdateStage(lead.id, stg.id)}
                    className={`py-2 px-2.5 rounded-xl text-xs font-semibold border transition-all flex flex-col items-center justify-center text-center ${
                      isCurrent
                        ? "bg-blue-600 border-blue-500 text-white shadow-md shadow-blue-950"
                        : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                    }`}
                  >
                    <span>{stg.label}</span>
                    {isCurrent && <CheckCircle2 className="w-3 h-3 mt-1 text-white" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Notes Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
                Anotações & Histórico do Cliente
              </label>
              {!isEditingNotes && (
                <button
                  onClick={() => setIsEditingNotes(true)}
                  className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center space-x-1"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  <span>Editar Anotações</span>
                </button>
              )}
            </div>

            {isEditingNotes ? (
              <div className="space-y-2">
                <textarea
                  rows={4}
                  value={notesInput}
                  onChange={(e) => setNotesInput(e.target.value)}
                  className="w-full bg-zinc-950 border border-blue-500 rounded-xl p-3 text-xs text-zinc-200 focus:outline-none resize-none"
                  placeholder="Escreva anotações ou detalhes sobre as reuniões com este lead..."
                />
                <div className="flex justify-end space-x-2">
                  <button
                    onClick={() => setIsEditingNotes(false)}
                    className="px-3 py-1.5 bg-zinc-800 text-zinc-300 rounded-lg text-xs"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={handleSaveNotes}
                    className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-bold flex items-center space-x-1"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Salvar</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 min-h-[80px] text-zinc-300 leading-relaxed whitespace-pre-wrap">
                {lead.notes || <span className="text-zinc-500 italic">Nenhuma anotação registrada ainda.</span>}
              </div>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-between">
          <button
            onClick={() => {
              if (confirm(`Deseja excluir permanentemente a oportunidade "${lead.name}"?`)) {
                onDeleteLead(lead.id);
                onClose();
              }
            }}
            className="px-3 py-2 text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            <span>Excluir Oportunidade</span>
          </button>

          <button
            onClick={onClose}
            className="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
