import { create } from "zustand";

export interface OabSeccionalData {
  code: string;
  uf: string;
  name: string;
  region: "Sudeste" | "Sul" | "Nordeste" | "Centro-Oeste" | "Norte";
  baseAnuidade: number;
  taxaRequerimento: number;
  taxaCartao: number;
}

export const OAB_SECCIONAIS: OabSeccionalData[] = [
  { code: "OAB/AC", uf: "AC", name: "Acre", region: "Norte", baseAnuidade: 890, taxaRequerimento: 220, taxaCartao: 160 },
  { code: "OAB/AL", uf: "AL", name: "Alagoas", region: "Nordeste", baseAnuidade: 920, taxaRequerimento: 240, taxaCartao: 170 },
  { code: "OAB/AP", uf: "AP", name: "Amapá", region: "Norte", baseAnuidade: 880, taxaRequerimento: 210, taxaCartao: 150 },
  { code: "OAB/AM", uf: "AM", name: "Amazonas", region: "Norte", baseAnuidade: 930, taxaRequerimento: 250, taxaCartao: 180 },
  { code: "OAB/BA", uf: "BA", name: "Bahia", region: "Nordeste", baseAnuidade: 950, taxaRequerimento: 260, taxaCartao: 180 },
  { code: "OAB/CE", uf: "CE", name: "Ceará", region: "Nordeste", baseAnuidade: 940, taxaRequerimento: 250, taxaCartao: 175 },
  { code: "OAB/DF", uf: "DF", name: "Distrito Federal", region: "Centro-Oeste", baseAnuidade: 950, taxaRequerimento: 250, taxaCartao: 180 },
  { code: "OAB/ES", uf: "ES", name: "Espírito Santo", region: "Sudeste", baseAnuidade: 980, taxaRequerimento: 260, taxaCartao: 185 },
  { code: "OAB/GO", uf: "GO", name: "Goiás", region: "Centro-Oeste", baseAnuidade: 960, taxaRequerimento: 250, taxaCartao: 180 },
  { code: "OAB/MA", uf: "MA", name: "Maranhão", region: "Nordeste", baseAnuidade: 910, taxaRequerimento: 230, taxaCartao: 170 },
  { code: "OAB/MT", uf: "MT", name: "Mato Grosso", region: "Centro-Oeste", baseAnuidade: 990, taxaRequerimento: 270, taxaCartao: 190 },
  { code: "OAB/MS", uf: "MS", name: "Mato Grosso do Sul", region: "Centro-Oeste", baseAnuidade: 970, taxaRequerimento: 260, taxaCartao: 180 },
  { code: "OAB/MG", uf: "MG", name: "Minas Gerais", region: "Sudeste", baseAnuidade: 920, taxaRequerimento: 240, taxaCartao: 170 },
  { code: "OAB/PA", uf: "PA", name: "Pará", region: "Norte", baseAnuidade: 940, taxaRequerimento: 250, taxaCartao: 175 },
  { code: "OAB/PB", uf: "PB", name: "Paraíba", region: "Nordeste", baseAnuidade: 900, taxaRequerimento: 230, taxaCartao: 165 },
  { code: "OAB/PR", uf: "PR", name: "Paraná", region: "Sul", baseAnuidade: 980, taxaRequerimento: 260, taxaCartao: 180 },
  { code: "OAB/PE", uf: "PE", name: "Pernambuco", region: "Nordeste", baseAnuidade: 960, taxaRequerimento: 250, taxaCartao: 180 },
  { code: "OAB/PI", uf: "PI", name: "Piauí", region: "Nordeste", baseAnuidade: 890, taxaRequerimento: 220, taxaCartao: 160 },
  { code: "OAB/RJ", uf: "RJ", name: "Rio de Janeiro", region: "Sudeste", baseAnuidade: 1150, taxaRequerimento: 290, taxaCartao: 200 },
  { code: "OAB/RN", uf: "RN", name: "Rio Grande do Norte", region: "Nordeste", baseAnuidade: 930, taxaRequerimento: 240, taxaCartao: 175 },
  { code: "OAB/RS", uf: "RS", name: "Rio Grande do Sul", region: "Sul", baseAnuidade: 1000, taxaRequerimento: 270, taxaCartao: 190 },
  { code: "OAB/RO", uf: "RO", name: "Rondônia", region: "Norte", baseAnuidade: 910, taxaRequerimento: 230, taxaCartao: 170 },
  { code: "OAB/RR", uf: "RR", name: "Roraima", region: "Norte", baseAnuidade: 870, taxaRequerimento: 210, taxaCartao: 155 },
  { code: "OAB/SC", uf: "SC", name: "Santa Catarina", region: "Sul", baseAnuidade: 1050, taxaRequerimento: 280, taxaCartao: 195 },
  { code: "OAB/SP", uf: "SP", name: "São Paulo", region: "Sudeste", baseAnuidade: 1015, taxaRequerimento: 250, taxaCartao: 180 },
  { code: "OAB/SE", uf: "SE", name: "Sergipe", region: "Nordeste", baseAnuidade: 910, taxaRequerimento: 230, taxaCartao: 165 },
  { code: "OAB/TO", uf: "TO", name: "Tocantins", region: "Norte", baseAnuidade: 920, taxaRequerimento: 240, taxaCartao: 170 },
];

export interface ChecklistItem {
  id: string;
  item_code: string;
  title: string;
  is_completed: boolean;
  file_url?: string;
}

export interface FeeState {
  seccional: string;
  monthOfRegistration: number;
  isJovemAdvogado: boolean;
  registerSua: boolean;
}

export interface HonorarioItem {
  id: string;
  area: string;
  servico: string;
  valorBase: number;
  exito: string;
}

export const INITIAL_HONORARIOS: HonorarioItem[] = [
  { id: "1", area: "Cível / Consumidor", servico: "Ação de Indenização por Danos Morais", valorBase: 3500, exito: "20% a 30%" },
  { id: "2", area: "Trabalhista", servico: "Reclamatória Trabalhista Completa", valorBase: 2800, exito: "20% a 30%" },
  { id: "3", area: "Societário / SUA", servico: "Elaboração e Registro de Contrato SUA", valorBase: 1950, exito: "N/A" },
  { id: "4", area: "Consultoria Preventiva", servico: "Parecer Jurídico Formal", valorBase: 1500, exito: "N/A" },
  { id: "5", area: "Contratual", servico: "Redação e Revisão de Contrato Comercial Complexo", valorBase: 2200, exito: "N/A" },
  { id: "6", area: "Família e Sucessões", servico: "Inventário Extrajudicial em Cartório", valorBase: 4500, exito: "8% a 15%" },
];

interface OabStore {
  seccional: string;
  setSeccional: (sec: string) => void;
  checklist: ChecklistItem[];
  setChecklist: (items: ChecklistItem[]) => void;
  toggleChecklist: (id: string) => void;
  feeState: FeeState;
  setFeeState: (update: Partial<FeeState>) => void;
  // Tabela Ética de Honorários
  honorariosList: HonorarioItem[];
  selectedYear: number;
  reajustePercentual: number;
  setSelectedYear: (year: number) => void;
  setReajustePercentual: (percent: number) => void;
  updateHonorario: (id: string, novoValorBase: number) => void;
  resetHonorarios: () => void;
}

export const useOabStore = create<OabStore>((set) => ({
  seccional: "OAB/SP",
  setSeccional: (sec) => set((state) => ({
    seccional: sec,
    feeState: { ...state.feeState, seccional: sec }
  })),
  checklist: [
    { id: "1", item_code: "CERTIFICADO_FGV", title: "Certificado de Aprovação no Exame de Ordem (FGV/OAB)", is_completed: true },
    { id: "2", item_code: "DIPLOMA", title: "Diploma ou Certidão de Graduação/Colação de Grau com Histórico Escolar", is_completed: true },
    { id: "3", item_code: "RG_CPF", title: "Documento de Identidade Oficial (RG) e CPF", is_completed: true },
    { id: "4", item_code: "TITULO_ELEITOR", title: "Título de Eleitor e Certidão de Quitação Eleitoral", is_completed: false },
    { id: "5", item_code: "RESERVISTA", title: "Certificado de Reservista ou Dispensa de Incorporação (masculino)", is_completed: false },
    { id: "6", item_code: "RESIDENCIA", title: "Comprovante de Residência Atualizado", is_completed: true },
    { id: "7", item_code: "CERTIDOES_NEGATIVAS", title: "Certidões Negativas Criminal/Cível (Justiça Estadual, Federal e Eleitoral)", is_completed: false },
    { id: "8", item_code: "FOTOS_3X4", title: "Duas Fotos 3x4 Oficiais (fundo branco, traje formal)", is_completed: false },
  ],
  setChecklist: (items) => set({ checklist: items }),
  toggleChecklist: (id) =>
    set((state) => ({
      checklist: state.checklist.map((item) =>
        item.id === id ? { ...item, is_completed: !item.is_completed } : item
      ),
    })),
  feeState: {
    seccional: "OAB/SP",
    monthOfRegistration: 1,
    isJovemAdvogado: true,
    registerSua: false,
  },
  setFeeState: (update) =>
    set((state) => ({
      feeState: { ...state.feeState, ...update },
      ...(update.seccional ? { seccional: update.seccional } : {}),
    })),
  // Honorarios State Implementation
  honorariosList: INITIAL_HONORARIOS,
  selectedYear: 2026,
  reajustePercentual: 0,
  setSelectedYear: (year) => set({ selectedYear: year }),
  setReajustePercentual: (percent) => set({ reajustePercentual: percent }),
  updateHonorario: (id, novoValorBase) =>
    set((state) => ({
      honorariosList: state.honorariosList.map((item) =>
        item.id === id ? { ...item, valorBase: novoValorBase } : item
      ),
    })),
  resetHonorarios: () =>
    set({
      honorariosList: INITIAL_HONORARIOS,
      reajustePercentual: 0,
      selectedYear: 2026,
    }),
}));


