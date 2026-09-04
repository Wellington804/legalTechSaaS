from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import List, Optional
from app.services.tasks import generate_audit_hash_task
from app.core.dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

class LeadCreate(BaseModel):
    name: str
    channel: str
    subject: str
    estimated_value: float
    temperature: Optional[str] = "Quente"
    notes: Optional[str] = ""

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    channel: Optional[str] = None
    subject: Optional[str] = None
    stage: Optional[str] = None
    estimated_value: Optional[float] = None
    temperature: Optional[str] = None
    notes: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    name: str
    channel: str
    subject: str
    stage: str
    estimated_value: float
    temperature: Optional[str] = "Quente"
    notes: Optional[str] = ""

class PipelineEventTrigger(BaseModel):
    event_type: str # "SIGNATURE_COMPLETED", "CHECKLIST_APPROVED", "PAYMENT_RECEIVED"
    lead_id: str
    target_stage: Optional[str] = "fechados"
    metadata: Optional[dict] = {}

@router.get("/leads", response_model=List[LeadResponse])
async def list_crm_leads():
    """
    Retorna os leads do funil de vendas Omnichannel CRM do escritório.
    """
    return [
        {
            "id": "lead_1",
            "name": "Mariana Alencar",
            "channel": "WhatsApp",
            "subject": "Dúvida sobre Registro OAB Originária",
            "stage": "novos",
            "estimated_value": 2500.00,
            "temperature": "Quente",
            "notes": "Candidata aprovada no Exame da OAB."
        },
        {
            "id": "lead_2",
            "name": "Empresa Beta Logística",
            "channel": "Formulário",
            "subject": "Contrato de Prestação de Serviços",
            "stage": "novos",
            "estimated_value": 8000.00,
            "temperature": "Morno",
            "notes": "Enviou formulário pelo site."
        },
        {
            "id": "lead_3",
            "name": "Dr. Roberto Faria",
            "channel": "E-mail",
            "subject": "Constituição de SUA Advocacia",
            "stage": "qualificacao",
            "estimated_value": 1950.00,
            "temperature": "Quente",
            "notes": "Quer abrir CNPJ Sociedade Unipessoal."
        }
    ]

@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(lead: LeadCreate):
    """
    Cadastra novo lead vindo de formulário público ou webhook de WhatsApp.
    """
    return {
        "id": "lead_new_99",
        "name": lead.name,
        "channel": lead.channel,
        "subject": lead.subject,
        "stage": "novos",
        "estimated_value": lead.estimated_value,
        "temperature": lead.temperature or "Quente",
        "notes": lead.notes or ""
    }

@router.put("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: str, lead_data: LeadUpdate):
    """
    Atualiza integralmente as informações de um lead/oportunidade existente.
    """
    return {
        "id": lead_id,
        "name": lead_data.name or "Lead Atualizado",
        "channel": lead_data.channel or "WhatsApp",
        "subject": lead_data.subject or "Serviço Atualizado",
        "stage": lead_data.stage or "novos",
        "estimated_value": lead_data.estimated_value if lead_data.estimated_value is not None else 0.0,
        "temperature": lead_data.temperature or "Quente",
        "notes": lead_data.notes or ""
    }

@router.post("/auto-trigger")
async def trigger_pipeline_automation(trigger: PipelineEventTrigger, request: Request):
    """
    Passo 4.1 — Automação de Workflow Legal: Avança o lead de estático no CRM e gera tarefa Celery ao confirmar assinatura.
    """
    # Envia tarefa de auditoria em background no Celery
    generate_audit_hash_task.delay(
        tenant_id=request.state.tenant_id,
        user_id=request.state.user_id,
        action=f"AUTOMATED_PIPELINE_{trigger.event_type}",
        resource_type="crm_leads",
        details=trigger.metadata or {}
    )

    return {
        "status": "success",
        "lead_id": trigger.lead_id,
        "previous_stage": "proposta",
        "new_stage": trigger.target_stage or "fechados",
        "automated_event": trigger.event_type,
        "message": f"Lead {trigger.lead_id} movido automaticamente para '{trigger.target_stage}' por disparo de evento {trigger.event_type}!"
    }
