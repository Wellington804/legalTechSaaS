from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
import hashlib
import time
from app.core.dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

class ConflictCheckRequest(BaseModel):
    entity_name: str
    cpf_cnpj: Optional[str] = None
    entity_type: Optional[str] = "Pessoa Jurídica (PJ)"
    role: Optional[str] = "Cliente Potencial"
    check_type: str = "GLOBAL_ETHICAL"

@router.post("/check")
async def run_conflict_check(
    req: Request,
    check_in: ConflictCheckRequest
):
    # Simulated intelligent search matching OAB Arts. 17-22
    name_lower = check_in.entity_name.lower()
    has_conflict = False
    status = "SAFE"
    risk_score = 0.0
    matched_records = []
    notes = "Nenhum vínculo ético adverso encontrado na base do escritório ou nos processos cadastrados."
    oab_article = "Arts. 17 e 20 da Lei 8.906/94"

    if "carlos" in name_lower or "mendonça" in name_lower or "conflict" in name_lower:
        has_conflict = True
        status = "CONFLICT"
        risk_score = 0.98
        matched_records = [
            {
                "party": "Carlos Eduardo de Mendonça",
                "role": "Réu / Polo Passivo",
                "process_no": "Proc. 0001234-88.2025.8.26.0000",
                "court": "3ª Vara Cível de São Paulo",
                "link_type": "Parte contrária em litígio cível vigente patrocinado pela banca."
            }
        ]
        notes = "IMPEDIMENTO ÉTICO ABSOLUTO (Art. 18 OAB): A banca já atua no polo oposto em litígio vigente. Vedada aceitação do mandato."
    elif "silva" in name_lower or "construtora" in name_lower or "warning" in name_lower:
        has_conflict = False
        status = "WARNING"
        risk_score = 0.45
        matched_records = [
            {
                "party": "Silva Empreendimentos S/A",
                "role": "Sócio Minoritário",
                "process_no": "Proc. 1004589-12.2024.8.26.0100",
                "court": "2ª Vara do Trabalho de SP",
                "link_type": "Sócio minoritário consta em polo passivo de ação trabalhista patrocinada pela banca."
            }
        ]
        notes = "ALERTA DE SEGREDAMENTO ÉTICO (Art. 19 OAB): Sigilo de ex-cliente ativo nos últimos 5 anos. Requer anuência expressa dos sócios."

    # Generate SHA-256 proof hash
    raw_proof = f"{check_in.entity_name}:{check_in.cpf_cnpj}:{time.time()}"
    sha256_hash = hashlib.sha256(raw_proof.encode()).hexdigest().upper()

    return {
        "status": "success",
        "ethical_status": status,
        "has_conflict": has_conflict,
        "risk_score": risk_score,
        "matched_records": matched_records,
        "notes": notes,
        "oab_article": oab_article,
        "sha256_hash": sha256_hash,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

