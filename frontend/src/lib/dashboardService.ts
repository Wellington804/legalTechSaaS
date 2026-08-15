import { fetchApi } from "./api";

export interface KPIMetrics {
  processos: string;
  processosChange: string;
  conflitos: string;
  conflitosChange: string;
  contratos: string;
  contratosChange: string;
  faturamento: number;
  faturamentoChange: string;
}

export interface AuditLogItem {
  action: string;
  detail: string;
  time: string;
  hash: string;
}

export interface CriticalTaskItem {
  title: string;
  dept: string;
  deadline: string;
  priority: string;
  color: string;
}

export interface DashboardSummary {
  period: "Hoje" | "Semana" | "Mês" | "Ano";
  kpi: KPIMetrics;
  auditLogs: AuditLogItem[];
  criticalTasks: CriticalTaskItem[];
}

export const FALLBACK_PERIOD_DATA: Record<"Hoje" | "Semana" | "Mês" | "Ano", KPIMetrics> = {
  Hoje: {
    processos: "38",
    processosChange: "+2 hoje",
    conflitos: "5",
    conflitosChange: "100% Ético",
    contratos: "2",
    contratosChange: "+1 hoje",
    faturamento: 18500,
    faturamentoChange: "+4.2%",
  },
  Semana: {
    processos: "142",
    processosChange: "+8 esta sem.",
    conflitos: "28",
    conflitosChange: "100% Ético",
    contratos: "12",
    contratosChange: "+15%",
    faturamento: 125000,
    faturamentoChange: "+6.8%",
  },
  Mês: {
    processos: "1,420",
    processosChange: "+12.5%",
    conflitos: "328",
    conflitosChange: "100% Ético",
    contratos: "84",
    contratosChange: "+18%",
    faturamento: 485000,
    faturamentoChange: "+8.2%",
  },
  Ano: {
    processos: "4,850",
    processosChange: "+24.1%",
    conflitos: "1,240",
    conflitosChange: "100% Ético",
    contratos: "410",
    contratosChange: "+32%",
    faturamento: 2890000,
    faturamentoChange: "+14.5%",
  },
};

export async function getDashboardSummary(period: "Hoje" | "Semana" | "Mês" | "Ano"): Promise<KPIMetrics> {
  try {
    const data: DashboardSummary = await fetchApi(`/dashboard/summary?period=${period}`);
    return data.kpi;
  } catch (error) {
    console.warn(`[DashboardService] API Backend indisponível (${error}). Usando fallback de cache local para período '${period}'.`);
    return FALLBACK_PERIOD_DATA[period];
  }
}
