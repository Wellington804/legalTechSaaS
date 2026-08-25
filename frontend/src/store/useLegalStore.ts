import { create } from "zustand";

export interface CRMLead {
  id: string;
  title: string;
  client: string;
  value: number;
  stage: "LEAD" | "QUALIFIED" | "PROPOSAL" | "CLOSED";
}

export interface OABChecklistItem {
  id: string;
  code: string;
  title: string;
  completed: boolean;
}

interface LegalStoreState {
  leads: CRMLead[];
  checklists: OABChecklistItem[];
  
  // Optimistic Actions
  moveLeadStage: (leadId: string, newStage: CRMLead["stage"]) => void;
  toggleChecklistItem: (itemId: string) => void;
  setLeads: (leads: CRMLead[]) => void;
  setChecklists: (items: OABChecklistItem[]) => void;
}

export const useLegalStore = create<LegalStoreState>((set) => ({
  leads: [
    { id: "lead-1", title: "Restituição Tributária PIS/COFINS", client: "Empresa Alfa LTDA", value: 45000, stage: "LEAD" },
    { id: "lead-2", title: "Parecer Reforma Tributária IBS/CBS", client: "Beta Indústria S.A.", value: 120000, stage: "PROPOSAL" },
    { id: "lead-3", title: "Defesa Fiscal ICMS/ST", client: "Gama Logística", value: 78000, stage: "QUALIFIED" },
    { id: "lead-4", title: "Planejamento Tributário Holdings", client: "Família Silva", value: 35000, stage: "CLOSED" }
  ],
  checklists: [
    { id: "chk-1", code: "CERTIFICADO_FGV", title: "Certificado de Aprovação no Exame OAB (FGV)", completed: true },
    { id: "chk-2", code: "DIPLOMA", title: "Diploma ou Certidão de Graduação em Direito", completed: true },
    { id: "chk-3", code: "RG_CPF", title: "Documento de Identidade Oficial (RG) e CPF", completed: true },
    { id: "chk-4", code: "TITULO_ELEITOR", title: "Título de Eleitor e Quitação Eleitoral", completed: false },
    { id: "chk-5", code: "CERTIDOES_NEGATIVAS", title: "Certidões Negativas Cível e Criminal", completed: false }
  ],

  moveLeadStage: (leadId, newStage) => {
    set((state) => ({
      leads: state.leads.map((l) => (l.id === leadId ? { ...l, stage: newStage } : l))
    }));
  },

  toggleChecklistItem: (itemId) => {
    set((state) => ({
      checklists: state.checklists.map((c) => (c.id === itemId ? { ...c, completed: !c.completed } : c))
    }));
  },

  setLeads: (leads) => set({ leads }),
  setChecklists: (items) => set({ checklists: items })
}));
