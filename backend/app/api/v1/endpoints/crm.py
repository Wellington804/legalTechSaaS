from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class LeadCreate(BaseModel):
    name: str
    channel: str
    subject: str
    estimated_value: float

class LeadResponse(BaseModel):
    id: str
    name: str
    channel: str
    subject: str
    stage: str
    estimated_value: float

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
            "estimated_value": 2500.00
        },
        {
            "id": "lead_2",
            "name": "Empresa Beta Logística",
            "channel": "Formulário",
            "subject": "Contrato de Prestação de Serviços",
            "stage": "novos",
            "estimated_value": 8000.00
        },
        {
            "id": "lead_3",
            "name": "Dr. Roberto Faria",
            "channel": "E-mail",
            "subject": "Constituição de SUA Advocacia",
            "stage": "qualificacao",
            "estimated_value": 1950.00
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
        "estimated_value": lead.estimated_value
    }
