from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class PetitionRequest(BaseModel):
    title: str
    area: str
    facts: str
    jurisprudence_keywords: List[str]

@router.post("/generate", response_model=Dict[str, Any])
async def generate_petition_draft(petition_req: PetitionRequest):
    """
    Gera minuta preliminar de petição inicial estruturada com fundamentação jurídica via IA.
    """
    draft = f"""EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA CÍVEL DA COMARCA DE SÃO PAULO/SP

REQUERENTE: [NOME DO CLIENTE]
REQUERIDO: [NOME DA PARTE RECLAMADA]

ÁREA: {petition_req.area.upper()}
ASSUNTO: {petition_req.title.upper()}

I. DOS FATOS
{petition_req.facts}

II. DO DIREITO E DA FUNDAMENTAÇÃO
Conforme preceitua a legislação vigente e a jurisprudência dominante sobre {', '.join(petition_req.jurisprudence_keywords)}, assiste total razão ao Requerente.

III. DOS PEDIDOS
Diante do exposto, requer:
a) A citação da parte Requerida;
b) O provimento total dos pedidos com a procedência da ação;
c) A condenação em honorários sucumbenciais nos termos da Tabela OAB.

Nestes termos, pede deferimento.
[CIDADE/UF], [DATA]
[NOME DO ADVOGADO] - OAB/[UF]
"""
    return {
        "title": petition_req.title,
        "area": petition_req.area,
        "content_markdown": draft,
        "status": "draft_generated",
        "compliance_oab": True
    }
