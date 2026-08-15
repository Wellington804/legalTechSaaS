"use client";

import React, { useState, useEffect } from "react";
import { X, Plus, Users, DollarSign, MessageSquare, Tag, Check, Sparkles } from "lucide-react";

export interface LeadData {
  id: string;
  name: string;
  type: "WhatsApp" | "E-mail" | "Formulário" | "Recomendação" | "Telefone";
  subject: string;
  value: number; // Em números para somatória
  date: string;
  stageId: "novos" | "qualificacao" | "proposta" | "fechado";
  notes?: string;
  temperature?: "Quente" | "Morno" | "Frio";
}

interface NewLeadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddLead: (lead: LeadData) => void;
}

export function NewLeadModal({ isOpen, onClose, onAddLead }: NewLeadModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    type: "WhatsApp" as LeadData["type"],
    subject: "",
    value: "",
    stageId: "novos" as LeadData["stageId"],
    temperature: "Quente" as LeadData["temperature"],
    notes: "",
  });

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.subject.trim()) return;

    const numericVal = parseFloat(formData.value.replace(/[^0-9,.]/g, "").replace(",", ".")) || 0;

    const newLead: LeadData = {
      id: Date.now().toString(),
      name: formData.name.trim(),
      type: formData.type,
      subject: formData.subject.trim(),
      value: numericVal,
      date: "Hoje, " + new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
      stageId: formData.stageId,
      temperature: formData.temperature,
      notes: formData.notes.trim(),
    };

    onAddLead(newLead);
    setFormData({
      name: "",
      type: "WhatsApp",
      subject: "",
      value: "",
      stageId: "novos",
      temperature: "Quente",
      notes: "",
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/90">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                Cadastrar Novo Lead / Oportunidade
              </h2>
              <p className="text-xs text-zinc-400">
                Adicione uma nova oportunidade jurídica ao seu funil de CRM
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          <div>
            <label className="text-zinc-300 font-semibold block mb-1">
              Nome do Cliente ou Empresa <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="Ex: Dra. Mariana Alencar ou Construtora Beta Ltda."
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-300 font-semibold block mb-1">Canal de Origem</label>
              <select
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value as LeadData["type"] })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option value="WhatsApp" className="bg-zinc-900">WhatsApp</option>
                <option value="E-mail" className="bg-zinc-900">E-mail</option>
                <option value="Formulário" className="bg-zinc-900">Formulário Público</option>
                <option value="Recomendação" className="bg-zinc-900">Recomendação</option>
                <option value="Telefone" className="bg-zinc-900">Telefone / Presencial</option>
              </select>
            </div>

            <div>
              <label className="text-zinc-300 font-semibold block mb-1">Estágio Inicial</label>
              <select
                value={formData.stageId}
                onChange={(e) => setFormData({ ...formData, stageId: e.target.value as LeadData["stageId"] })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option value="novos" className="bg-zinc-900">Novos Leads / Contato Inicial</option>
                <option value="qualificacao" className="bg-zinc-900">Em Qualificação & Análise</option>
                <option value="proposta" className="bg-zinc-900">Proposta Enviada</option>
                <option value="fechado" className="bg-zinc-900">Contrato Fechado</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-zinc-300 font-semibold block mb-1">
              Assunto / Serviço Pretendido <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="Ex: Registro OAB Originária, Parecer IBS/CBS, Contrato SUA"
              value={formData.subject}
              onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-zinc-300 font-semibold block mb-1">Valor Estimado (R$)</label>
              <input
                type="text"
                placeholder="Ex: 3500.00"
                value={formData.value}
                onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs font-mono text-emerald-400 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="text-zinc-300 font-semibold block mb-1">Temperatura do Lead</label>
              <select
                value={formData.temperature}
                onChange={(e) => setFormData({ ...formData, temperature: e.target.value as LeadData["temperature"] })}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option value="Quente" className="bg-zinc-900">🔥 Quente (Decisão Rápida)</option>
                <option value="Morno" className="bg-zinc-900">⚡ Morno (Em Avaliação)</option>
                <option value="Frio" className="bg-zinc-900">❄️ Frio (Longo Prazo)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-zinc-300 font-semibold block mb-1">Observações Inicial / Anotações</label>
            <textarea
              rows={3}
              placeholder="Anotações sobre a primeira conversa, necessidades do cliente..."
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>

          <div className="pt-3 border-t border-zinc-800 flex items-center justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-blue-950 transition-all flex items-center space-x-1.5"
            >
              <Check className="w-4 h-4" />
              <span>Cadastrar Oportunidade</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
