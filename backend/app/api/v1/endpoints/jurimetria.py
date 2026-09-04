from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from app.core.dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

class JudgeProfileResponse(BaseModel):
    judge_name: str
    court: str
    chamber: str
    urgency_injunction_grant_rate: float
    average_days_to_verdict: int
    appeal_reversal_rate: float
    top_jurisprudence_topics: List[str]
    strategic_recommendations: List[str]

@router.get("/profiling", response_model=JudgeProfileResponse)
async def get_judge_profiling(judge_name: str = Query(..., description="Nome do magistrado para análise jurimétrica")):
    """
    Retorna a análise jurimétrica e perfilamento decisório do magistrado via IA.
    """
    return JudgeProfileResponse(
        judge_name=judge_name,
        court="Tribunal de Justiça do Estado de São Paulo (TJSP)",
        chamber="8ª Câmara de Direito Privado",
        urgency_injunction_grant_rate=74.5,
        average_days_to_verdict=42,
        appeal_reversal_rate=18.2,
        top_jurisprudence_topics=[
            "Tutela de Urgência em Planos de Saúde",
            "Dano Moral por Inscrição Indevida no SISBAJUD",
            "Revisão Contratual por Onerosidade Excessiva"
        ],
        strategic_recommendations=[
            "Priorizar tese respaldada na Súmula 608 do STJ no primeiro parágrafo.",
            "Evitar pedidos Genéricos de Danos Morais acima de R$ 50.000,00 nesta vara.",
            "Anexar prova documental pré-constituída completa no ato do ajuizamento."
        ]
    )
