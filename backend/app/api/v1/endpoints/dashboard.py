from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class KPIMetricsResponse(BaseModel):
    processos: str
    processosChange: str
    conflitos: str
    conflitosChange: str
    contratos: str
    contratosChange: str
    faturamento: float
    faturamentoChange: str

class AuditLogResponse(BaseModel):
    action: str
    detail: str
    time: str
    hash: str

class CriticalTaskResponse(BaseModel):
    title: str
    dept: str
    deadline: str
    priority: str
    color: str

class DashboardSummaryResponse(BaseModel):
    period: str
    kpi: KPIMetricsResponse
    auditLogs: List[AuditLogResponse]
    criticalTasks: List[CriticalTaskResponse]

# Banco de dados em memória / simulado para os tenants
PERIOD_METRICS = {
    "Hoje": {
        "processos": "38",
        "processosChange": "+2 hoje",
        "conflitos": "5",
        "conflitosChange": "100% Ético",
        "contratos": "2",
        "contratosChange": "+1 hoje",
        "faturamento": 18500.0,
        "faturamentoChange": "+4.2%",
    },
    "Semana": {
        "processos": "142",
        "processosChange": "+8 esta sem.",
        "conflitos": "28",
        "conflitosChange": "100% Ético",
        "contratos": "12",
        "contratosChange": "+15%",
        "faturamento": 125000.0,
        "faturamentoChange": "+6.8%",
    },
    "Mês": {
        "processos": "1,420",
        "processosChange": "+12.5%",
        "conflitos": "328",
        "conflitosChange": "100% Ético",
        "contratos": "84",
        "contratosChange": "+18%",
        "faturamento": 485000.0,
        "faturamentoChange": "+8.2%",
    },
    "Ano": {
        "processos": "4,850",
        "processosChange": "+24.1%",
        "conflitos": "1,240",
        "conflitosChange": "100% Ético",
        "contratos": "410",
        "contratosChange": "+32%",
        "faturamento": 2890000.0,
        "faturamentoChange": "+14.5%",
    },
}

DEFAULT_AUDIT_LOGS = [
    { "action": "OAB_SECCIONAL_SELECTED", "detail": "Seccional alterada para OAB/SP", "time": "Há 2 min", "hash": "sha256-f89a12..." },
    { "action": "CHECKLIST_ITEM_VALIDATED", "detail": "4 de 8 documentos aprovados", "time": "Há 12 min", "hash": "sha256-a4f9e1..." },
    { "action": "PIX_PAYMENT_GENERATED", "detail": "Guia OAB SP emitida no Pix", "time": "Há 34 min", "hash": "sha256-99b8c2..." },
    { "action": "CRM_LEAD_STAGE_UPDATED", "detail": "Oportunidade movida para Contrato Fechado", "time": "Há 1 hora", "hash": "sha256-3c7d91..." },
]

DEFAULT_CRITICAL_TASKS = [
    { "title": "Protocolar Inscrição na CSA/OAB", "dept": "Hub OAB", "deadline": "Hoje, 17:00", "priority": "Alta", "color": "text-rose-400 border-rose-900/60 bg-rose-950/40" },
    { "title": "Acompanhar Proposta Parecer IBS/CBS", "dept": "CRM", "deadline": "Amanhã, 12:00", "priority": "Média", "color": "text-amber-400 border-amber-900/60 bg-amber-950/40" },
    { "title": "Validar Certidão Negativa Estadual", "dept": "Checklist", "deadline": "Em 3 dias", "priority": "Normal", "color": "text-blue-400 border-blue-900/60 bg-blue-950/40" },
]

@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(period: str = Query("Semana", description="Período das métricas: Hoje, Semana, Mês, Ano")):
    """
    Retorna o resumo consolidado de Métricas Executivas, Audit Logs e Prazos Críticos por período.
    """
    if period not in PERIOD_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Período inválido '{period}'. Opções válidas: Hoje, Semana, Mês, Ano."
        )

    return {
        "period": period,
        "kpi": PERIOD_METRICS[period],
        "auditLogs": DEFAULT_AUDIT_LOGS,
        "criticalTasks": DEFAULT_CRITICAL_TASKS
    }
