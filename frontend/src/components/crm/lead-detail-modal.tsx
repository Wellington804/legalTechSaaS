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
  Tag,
  Save,
  Flame,
  Zap,
  Snowflake,
  Phone,
  Mail,
  FileText,
  Share2,
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
  onUpdateLead?: (updatedLead: LeadData) => void;
}

export function LeadDetailModal({
  lead,
  isOpen,
  onClose,
  onUpdateStage,
  onDeleteLead,
  onUpdateNotes,
  onUpdateLead,
}: LeadDetailModalProps) {
  // Form states for full editing
  const [name, setName] = useState("");
  const [type, setType] = useState<LeadData["type"]>("WhatsApp");
  const [temperature, setTemperature] = useState<LeadData["temperature"]>("Quente");
  const [subject, setSubject] = useState("");
  const [valueInput, setValueInput] = useState("");
  const [stageId, setStageId] = useState<LeadData["stageId"]>("novos");
  const [notesInput, setNotesInput] = useState("");
  const [isSavedRecently, setIsSavedRecently] = useState(false);

  // Sync state when lead changes or modal opens
  useEffect(() => {
    if (lead) {
      setName(lead.name || "");
      setType(lead.type || "WhatsApp");
      setTemperature(lead.temperature || "Quente");
      setSubject(lead.subject || "");
      setValueInput(lead.value ? lead.value.toString() : "0");
      setStageId(lead.stageId || "novos");
      setNotesInput(lead.notes || "");
    }
  }, [lead, isOpen]);

  // Check if form was modified compared to lead prop
  const isDirty = lead && (
    name !== lead.name ||
    type !== lead.type ||
    temperature !== lead.temperature ||
    subject !== lead.subject ||
    parseFloat(valueInput.replace(/[^0-9,.]/g, "").replace(",", ".")) !== lead.value ||
    stageId !== lead.stageId ||
    notesInput !== (lead.notes || "")
  );

  const handleSaveAll = () => {
    if (!lead) return;
    const numericVal = parseFloat(valueInput.replace(/[^0-9,.]/g, "").replace(",", ".")) || 0;

    const updated: LeadData = {
      ...lead,
      name: name.trim() || lead.name,
      type,
      temperature,
      subject: subject.trim() || lead.subject,
      value: numericVal,
      stageId,
      notes: notesInput.trim(),
    };

    if (onUpdateLead) {
      onUpdateLead(updated);
    } else {
      if (stageId !== lead.stageId) onUpdateStage(lead.id, stageId);
      if (notesInput !== lead.notes) onUpdateNotes(lead.id, notesInput);
    }

    setIsSavedRecently(true);
    setTimeout(() => setIsSavedRecently(false), 2000);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "s" && isOpen) {
        e.preventDefault();
        handleSaveAll();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, name, type, temperature, subject, valueInput, stageId, notesInput, lead]);

  if (!isOpen || !lead) return null;

  const stages: { id: LeadData["stageId"]; label: string }[] = [
    { id: "novos", label: "Novos Leads" },
    { id: "qualificacao", label: "Em Qualificação" },
    { id: "proposta", label: "Proposta Enviada" },
    { id: "fechado", label: "Contrato Fechado" },
  ];

  const channelOptions: LeadData["type"][] = [
    "WhatsApp",
    "E-mail",
    "Formulário",
    "Recomendação",
    "Telefone",
  ];

  const tempOptions: LeadData["temperature"][] = ["Quente", "Morno", "Frio"];

  const currentNumericValue = parseFloat(valueInput.replace(/[^0-9,.]/g, "").replace(",", ".")) || 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90">
          <div className="flex items-center space-x-3 flex-1 pr-4">
            <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400 flex items-center justify-center font-bold text-sm shrink-0">
              <User className="w-5 h-5" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                {/* Editable Lead Name */}
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Nome do Cliente / Empresa"
                  className="bg-zinc-950/80 hover:bg-zinc-950 border border-transparent hover:border-zinc-700 focus:border-blue-500 text-base font-bold text-zinc-100 rounded-lg px-2 py-0.5 focus:outline-none transition-colors max-w-[240px] sm:max-w-xs"
                />

                {/* Editable Channel Badge */}
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value as LeadData["type"])}
                  className="bg-blue-950 text-blue-400 border border-blue-800 text-[11px] font-mono rounded px-2 py-1 focus:outline-none cursor-pointer hover:bg-blue-900/80 transition-colors"
                >
                  {channelOptions.map((ch) => (
                    <option key={ch} value={ch} className="bg-zinc-900 text-zinc-200">
                      {ch}
                    </option>
                  ))}
                </select>

                {/* Editable Temperature Badge */}
                <select
                  value={temperature}
                  onChange={(e) => setTemperature(e.target.value as LeadData["temperature"])}
                  className="bg-amber-950/80 text-amber-400 border border-amber-800/60 text-[11px] font-mono rounded px-2 py-1 focus:outline-none cursor-pointer hover:bg-amber-900/80 transition-colors"
                >
                  {tempOptions.map((t) => (
                    <option key={t} value={t} className="bg-zinc-900 text-zinc-200">
                      {t === "Quente" ? "🔥 Quente" : t === "Morno" ? "⚡ Morno" : "❄️ Frio"}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center space-x-2 text-xs text-zinc-400">
                <span>Cadastrado em {lead.date}</span>
                {isDirty && (
                  <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded font-mono animate-pulse">
                    Modificado
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs">
          {/* Main Editable Info Box */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-mono text-zinc-500 uppercase block mb-1">
                  Serviço Pretendido
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Ex: Parecer Tributário IBS/CBS"
                  className="w-full bg-zinc-900 border border-zinc-800 hover:border-zinc-700 focus:border-blue-500 rounded-lg p-2 text-xs font-bold text-zinc-100 focus:outline-none transition-colors"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-zinc-500 uppercase block mb-1">
                  Valor Estimado (R$)
                </label>
                <div className="relative flex items-center">
                  <span className="absolute left-2.5 text-xs text-emerald-500 font-bold font-mono">
                    R$
                  </span>
                  <input
                    type="text"
                    value={valueInput}
                    onChange={(e) => setValueInput(e.target.value)}
                    placeholder="0.00"
                    className="w-full bg-zinc-900 border border-zinc-800 hover:border-zinc-700 focus:border-emerald-500 rounded-lg py-2 pl-9 pr-3 text-sm font-extrabold text-emerald-400 font-mono focus:outline-none transition-colors text-right"
                  />
                </div>
                <p className="text-[10px] text-zinc-500 font-mono text-right mt-1">
                  Formatado: {formatCurrency(currentNumericValue)}
                </p>
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
                const isCurrent = stageId === stg.id;
                return (
                  <button
                    key={stg.id}
                    type="button"
                    onClick={() => setStageId(stg.id)}
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
            <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block">
              Anotações & Histórico do Cliente
            </label>
            <textarea
              rows={4}
              value={notesInput}
              onChange={(e) => setNotesInput(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 hover:border-zinc-700 focus:border-blue-500 rounded-xl p-3 text-xs text-zinc-200 focus:outline-none resize-none transition-colors"
              placeholder="Escreva anotações ou detalhes sobre as reuniões com este lead..."
            />
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-zinc-800 bg-zinc-950/80 flex items-center justify-between">
          <button
            type="button"
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

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-xl text-xs font-semibold transition-colors"
            >
              Cancelar / Fechar
            </button>

            <button
              type="button"
              onClick={handleSaveAll}
              disabled={!isDirty && !isSavedRecently}
              className={`px-5 py-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all shadow-md ${
                isSavedRecently
                  ? "bg-emerald-500 text-zinc-950 border border-emerald-400"
                  : isDirty
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/50"
                  : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              }`}
            >
              {isSavedRecently ? (
                <>
                  <Check className="w-4 h-4" />
                  <span>Salvo com Sucesso!</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Salvar Alterações</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

