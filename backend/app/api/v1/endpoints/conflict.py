from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.conflict import ConflictCheck
from app.services.audit_service import AuditService

router = APIRouter()

class ConflictCheckRequest(BaseModel):
    entity_name: str
    cpf_cnpj: str = None
    check_type: str = "GLOBAL_ETHICAL"

@router.post("/check")
async def run_conflict_check(
    req: Request,
    check_in: ConflictCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    tenant_id = getattr(req.state, "tenant_id", "default-tenant")

    # Mocked intelligent ethical search simulation
    has_conflict = False
    risk_score = 0.05
    matched_records = []

    # Simple demonstration logic
    if "conflito" in check_in.entity_name.lower():
        has_conflict = True
        risk_score = 0.85
        matched_records = [{"party": "Empresa Opponent Ltda", "role": "Réu", "process_no": "0001234-88.2025.8.02.0001"}]

    record = ConflictCheck(
        tenant_id=tenant_id,
        entity_name=check_in.entity_name,
        cpf_cnpj=check_in.cpf_cnpj,
        check_type=check_in.check_type,
        has_conflict=has_conflict,
        risk_score=risk_score,
        matched_records=matched_records,
        checked_by_user_id="user-demo"
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    await AuditService.log_action(
        db=db,
        tenant_id=tenant_id,
        user_id="user-demo",
        action="CONFLICT_CHECK_EXECUTED",
        resource_type="conflict_checks",
        resource_id=record.id,
        details={"entity": check_in.entity_name, "has_conflict": has_conflict}
    )

    return {
        "status": "success",
        "has_conflict": has_conflict,
        "risk_score": risk_score,
        "matched_records": matched_records
    }
