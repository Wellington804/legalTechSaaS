from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class OABChecklistSchema(BaseModel):
    id: Optional[str] = None
    item_code: str
    title: str
    is_completed: bool = False
    file_url: Optional[str] = None
    verification_notes: Optional[str] = None

class OABApplicationCreate(BaseModel):
    seccional: str = Field(..., example="OAB/SP")
    candidate_name: str
    cpf: str
    rg: str
    fgv_exam_number: Optional[str] = None

class OABApplicationResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    seccional: str
    candidate_name: str
    cpf: str
    rg: str
    status: str
    fgv_exam_number: Optional[str]
    protocol_number: Optional[str]
    created_at: datetime

class FeeSimulationRequest(BaseModel):
    seccional: str
    month_of_registration: int = 1 # 1 to 12
    is_jovem_advogado: bool = True
    register_sua: bool = False

class FeeSimulationResponse(BaseModel):
    seccional: str
    req_fee: float
    card_fee: float
    anuidade_bruta: float
    anuidade_proporcional: float
    desconto_jovem_advogado: float
    desconto_sua: float
    total_estimado: float

class DeclarationGenerateRequest(BaseModel):
    application_id: str
    declaration_type: str # IDONEIDADE_MORAL ou NAO_INCOMPATIBILIDADE
    candidate_name: str
    cpf: str
    rg: str
    address: str
    civil_status: str
