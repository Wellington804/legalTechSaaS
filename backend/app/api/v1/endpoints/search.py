from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any
from app.core.dependencies import CurrentUser

router = APIRouter()

@router.get("/", response_model=Dict[str, Any])
async def universal_vector_search(
    current_user: CurrentUser,
    q: str = Query(..., min_length=2, description="Termo ou vetor de busca semantica"),
):
    """
    Realiza busca vetorial semantica universal em acervos de documentos, processos e guias OAB (pgvector).
    """
    mock_results = [
        {
            "id": "doc_101",
            "title": "Petição Inicial - Restituição Tributária IBS/CBS",
            "type": "petition",
            "similarity_score": 0.94,
            "snippet": "Ação fundada no período de transição da Reforma Tributária..."
        },
        {
            "id": "oab_202",
            "title": "Checklist de Inscrição Originária OAB/SP",
            "type": "oab_guide",
            "similarity_score": 0.89,
            "snippet": "Exigências de certidões cíveis, criminais e certificado FGV..."
        },
        {
            "id": "client_303",
            "title": "Ficha Cadastral do Cliente - Carlos Eduardo",
            "type": "crm_lead",
            "similarity_score": 0.85,
            "snippet": "Contato via WhatsApp solicitando parecer sobre Sociedade SUA..."
        }
    ]

    return {
        "query": q,
        "tenant_id": current_user.tenant_id,
        "total_matches": len(mock_results),
        "results": mock_results
    }
