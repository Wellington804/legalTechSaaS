"use client";

import React, { useState } from "react";
import {
  Users,
  Plus,
  Filter,
  Search,
  Clock,
  DollarSign,
  TrendingUp,
  Award,
  CheckCircle2,
  Check,
  X,
  MessageSquare,
  Sparkles,
  Phone,
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { NewLeadModal, LeadData } from "@/components/crm/new-lead-modal";
import { LeadDetailModal } from "@/components/crm/lead-detail-modal";

export default function CRMPage() {
  const [leads, setLeads] = useState<LeadData[]>([
    {
      id: "1",
      name: "Mariana Alencar",
      type: "WhatsApp",
      subject: "Dúvida sobre Registro OAB Originária",
      value: 2500,
      date: "Hoje, 09:30",
      stageId: "novos",
      temperature: "Quente",
      notes: "Candidata aprovada no Exame da OAB. Quer entrada imediata na OAB/SP com desconto de Jovem Advogada.",
    },
    {
      id: "2",
      name: "Empresa Beta Logística",
      type: "Formulário",
      subject: "Contrato de Prestação de Serviços",
      value: 8000,
      date: "Hoje, 10:15",
      stageId: "novos",
      temperature: "Morno",
      notes: "Enviou formulário pelo site. Solicita revisão contratual para frota de transporte.",
    },
    {
      id: "3",
      name: "Dr. Roberto Faria",
      type: "E-mail",
      subject: "Constituição de SUA Advocacia",
      value: 1950,
      date: "Ontem, 16:40",
      stageId: "qualificacao",
      temperature: "Quente",
      notes: "Quer abrir CNPJ Sociedade Unipessoal para reduzir tributação do Simples Nacional de 27.5% para 4.5%.",
    },
    {
      id: "4",
      name: "Construtora Horizonte",
      type: "WhatsApp",
      subject: "Parecer Tributário IBS/CBS",
      value: 15000,
      date: "11 de Ago",
      stageId: "proposta",
      temperature: "Quente",
      notes: "Proposta de parecer de transição da Reforma Tributária enviada ao diretor jurídico.",
    },
    {
      id: "5",
      name: "Camila Guimarães",
      type: "Recomendação",
      subject: "Inventário & Partilha de Bens",
      value: 12000,
      date: "10 de Ago",
      stageId: "fechado",
      temperature: "Quente",
      notes: "Contrato assinado via Assinatura Eletrônica. Pagamento efetuado via Pix.",
    },
  ]);

  const [search, setSearch] = useState("");
  const [selectedChannel, setSelectedChannel] = useState<string>("Todos");
  const [isNewLeadModalOpen, setIsNewLeadModalOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<LeadData | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const columns: { id: LeadData["stageId"]; title: string }[] = [
    { id: "novos", title: "Novos Leads / Contato Inicial" },
    { id: "qualificacao", title: "Em Qualificação & Análise" },
    { id: "proposta", title: "Proposta Enviada" },
    { id: "fechado", title: "Contrato Fechado" },
  ];

  const channels = ["Todos", "WhatsApp", "E-mail", "Formulário", "Recomendação", "Telefone"];

  // Métricas Calculadas
  const totalPipeline = leads.reduce((acc, l) => acc + l.value, 0);
  const totalFechado = leads.filter((l) => l.stageId === "fechado").reduce((acc, l) => acc + l.value, 0);
  const activeCount = leads.filter((l) => l.stageId !== "fechado").length;
  const ticketMedio = leads.length > 0 ? totalPipeline / leads.length : 0;

  // Filtragem em Tempo Real
  const filteredLeads = leads.filter((l) => {
    const matchesSearch =
      l.name.toLowerCase().includes(search.toLowerCase()) ||
      l.subject.toLowerCase().includes(search.toLowerCase());
    const matchesChannel = selectedChannel === "Todos" || l.type === selectedChannel;
    return matchesSearch && matchesChannel;
  });

  const handleAddLead = (newLead: LeadData) => {
    setLeads((prev) => [newLead, ...prev]);
    showToast(`Oportunidade "${newLead.name}" cadastrada com sucesso!`);
  };

  const handleUpdateStage = (leadId: string, newStageId: LeadData["stageId"]) => {
    setLeads((prev) =>
      prev.map((l) => (l.id === leadId ? { ...l, stageId: newStageId } : l))
    );
    if (selectedLead && selectedLead.id === leadId) {
      setSelectedLead((prev) => (prev ? { ...prev, stageId: newStageId } : null));
    }
    const stageNames: Record<LeadData["stageId"], string> = {
      novos: "Novos Leads",
      qualificacao: "Em Qualificação",
      proposta: "Proposta Enviada",
      fechado: "Contrato Fechado 🎉",
    };
    showToast(`Estágio alterado para "${stageNames[newStageId]}"!`);
  };

  const handleDeleteLead = (leadId: string) => {
    setLeads((prev) => prev.filter((l) => l.id !== leadId));
    showToast("Oportunidade removida do CRM.");
  };

  const handleUpdateNotes = (leadId: string, notes: string) => {
    setLeads((prev) =>
      prev.map((l) => (l.id === leadId ? { ...l, notes } : l))
    );
    if (selectedLead && selectedLead.id === leadId) {
      setSelectedLead((prev) => (prev ? { ...prev, notes } : null));
    }
    showToast("Anotações salvas com sucesso!");
  };

  const handleUpdateLead = (updatedLead: LeadData) => {
    setLeads((prev) =>
      prev.map((l) => (l.id === updatedLead.id ? updatedLead : l))
    );
    setSelectedLead(updatedLead);
    showToast(`Oportunidade "${updatedLead.name}" atualizada com sucesso!`);
  };

  return (
    <div className="p-6 md:p-8 space-y-8 max-w-7xl mx-auto">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 border border-emerald-500 text-white px-4 py-3 rounded-xl shadow-xl flex items-center space-x-2 text-xs font-semibold animate-in slide-in-from-bottom-5 duration-200">
          <Sparkles className="w-4 h-4 text-emerald-200" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
              CRM & Funil de Vendas Omnichannel
            </h1>
            <span className="px-2.5 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded-full font-bold">
              PRO
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Gestão de leads, propostas e captação de clientes da advocacia em tempo real.
          </p>
        </div>

        <button
          onClick={() => setIsNewLeadModalOpen(true)}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold text-xs shadow-lg shadow-blue-950 transition-all flex items-center space-x-2 self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Novo Lead / Oportunidade</span>
        </button>
      </div>

      {/* Metrics Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">VGV Em Prospecção</span>
            <h3 className="text-xl font-extrabold text-zinc-100 mt-0.5 font-mono">
              {formatCurrency(totalPipeline)}
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
            <DollarSign className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Receita Fechada</span>
            <h3 className="text-xl font-extrabold text-emerald-400 mt-0.5 font-mono">
              {formatCurrency(totalFechado)}
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Leads Ativos</span>
            <h3 className="text-xl font-extrabold text-zinc-100 mt-0.5 font-mono">
              {activeCount} <span className="text-xs font-normal text-zinc-500">em progresso</span>
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center">
            <Users className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-4 flex items-center justify-between">
          <div>
            <span className="text-[11px] text-zinc-500 font-mono uppercase">Ticket Médio</span>
            <h3 className="text-xl font-extrabold text-amber-400 mt-0.5 font-mono">
              {formatCurrency(ticketMedio)}
            </h3>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center">
            <Award className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 bg-zinc-950 border border-zinc-800/80 rounded-2xl p-3">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por cliente, empresa ou assunto do caso..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-2 pl-9 pr-4 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        {/* Channel Filter Badges */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          <Filter className="w-3.5 h-3.5 text-zinc-500 mr-1 shrink-0" />
          {channels.map((ch) => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all ${
                selectedChannel === ch
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 border border-zinc-800"
              }`}
            >
              {ch}
            </button>
          ))}
        </div>
      </div>

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-start">
        {columns.map((col) => {
          const colLeads = filteredLeads.filter((l) => l.stageId === col.id);
          const colTotal = colLeads.reduce((acc, l) => acc + l.value, 0);

          return (
            <div
              key={col.id}
              className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 min-h-[500px] flex flex-col space-y-4"
            >
              {/* Column Header */}
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div>
                  <h3 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
                    {col.title}
                  </h3>
                  <span className="text-[10px] text-zinc-500 font-mono mt-0.5 block">
                    VGV: {formatCurrency(colTotal)}
                  </span>
                </div>
                <span className="px-2.5 py-0.5 bg-zinc-950 border border-zinc-800 text-xs font-mono text-blue-400 rounded-full font-bold">
                  {colLeads.length}
                </span>
              </div>

              <div className="space-y-3 flex-1 overflow-y-auto pr-1">
                {colLeads.length > 0 ? (
                  colLeads.map((lead) => (
                    <div
                      key={lead.id}
                      onClick={() => setSelectedLead(lead)}
                      className="p-4 bg-zinc-950 border border-zinc-800/90 rounded-xl hover:border-blue-500/70 transition-all space-y-3 cursor-pointer group shadow-sm hover:shadow-md hover:scale-[1.01]"
                    >
                      <div className="flex items-start justify-between">
                        <span className="px-2 py-0.5 bg-blue-950 text-blue-400 border border-blue-800 text-[10px] font-mono rounded font-medium">
                          {lead.type}
                        </span>
                        <span className="text-[10px] text-zinc-500 flex items-center space-x-1 font-mono">
                          <Clock className="w-3 h-3 text-zinc-600" />
                          <span>{lead.date}</span>
                        </span>
                      </div>

                      <div>
                        <h4 className="text-xs font-bold text-zinc-100 group-hover:text-blue-400 transition-colors">
                          {lead.name}
                        </h4>
                        <p className="text-[11px] text-zinc-400 mt-0.5 line-clamp-2 leading-relaxed">
                          {lead.subject}
                        </p>
                      </div>

                      {lead.temperature && (
                        <div className="flex items-center space-x-1 text-[10px] font-mono">
                          <span className="text-zinc-500">Status:</span>
                          <span className="text-amber-400">
                            {lead.temperature === "Quente" ? "🔥 Quente" : lead.temperature === "Morno" ? "⚡ Morno" : "❄️ Frio"}
                          </span>
                        </div>
                      )}

                      <div className="pt-2.5 border-t border-zinc-900 flex justify-between items-center text-xs">
                        <span className="text-[10px] text-zinc-500">Valor Estimado</span>
                        <span className="font-mono font-extrabold text-emerald-400">
                          {formatCurrency(lead.value)}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="h-40 flex items-center justify-center text-center p-4 border border-dashed border-zinc-800 rounded-xl text-zinc-600 text-xs">
                    <span>Nenhuma oportunidade nesta etapa.</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Modals */}
      <NewLeadModal
        isOpen={isNewLeadModalOpen}
        onClose={() => setIsNewLeadModalOpen(false)}
        onAddLead={handleAddLead}
      />

      <LeadDetailModal
        lead={selectedLead}
        isOpen={!!selectedLead}
        onClose={() => setSelectedLead(null)}
        onUpdateStage={handleUpdateStage}
        onDeleteLead={handleDeleteLead}
        onUpdateNotes={handleUpdateNotes}
        onUpdateLead={handleUpdateLead}
      />
    </div>
  );
}
