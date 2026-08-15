from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.database import get_db
from app.models.oab import OABApplication, OABChecklist, OABDeclaration
from app.schemas.oab import (
    OABApplicationCreate,
    FeeSimulationRequest,
    FeeSimulationResponse,
    DeclarationGenerateRequest
)
from app.services.oab_service import OABService
from app.services.audit_service import AuditService

router = APIRouter()

@router.post("/applications")
async def create_oab_application(
    req: Request,
    app_in: OABApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    tenant_id = getattr(req.state, "tenant_id", "default-tenant")
    user_id = "user-system-demo" # Fallback demo user ID

    app = await OABService.create_application(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        data=app_in.model_dump()
    )

    await AuditService.log_action(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="OAB_APPLICATION_CREATED",
        resource_type="oab_applications",
        resource_id=app.id,
        details={"seccional": app.seccional, "candidate": app.candidate_name}
    )

    return {"status": "success", "application_id": app.id, "protocol": app.protocol_number}

@router.get("/applications/{app_id}/checklist")
async def get_application_checklist(app_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OABChecklist).where(OABChecklist.application_id == app_id))
    items = result.scalars().all()
    return items

@router.post("/applications/{app_id}/checklist/{item_id}/toggle")
async def toggle_checklist_item(app_id: str, item_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OABChecklist).where(OABChecklist.id == item_id))
    chk = result.scalars().first()
    if not chk:
        raise HTTPException(status_code=404, detail="Item do checklist nao encontrado.")
    
    chk.is_completed = not chk.is_completed
    await db.commit()
    return {"status": "success", "is_completed": chk.is_completed}

@router.post("/simulate-fees", response_model=FeeSimulationResponse)
async def simulate_oab_fees(req: FeeSimulationRequest):
    return OABService.calculate_fees(req)

@router.post("/generate-declaration")
async def generate_declaration(
    req: Request,
    decl_in: DeclarationGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    tenant_id = getattr(req.state, "tenant_id", "default-tenant")
    text = OABService.generate_declaration_text(
        decl_type=decl_in.declaration_type,
        candidate_name=decl_in.candidate_name,
        cpf=decl_in.cpf,
        rg=decl_in.rg,
        address=decl_in.address,
        civil_status=decl_in.civil_status
    )

    decl = OABDeclaration(
        application_id=decl_in.application_id,
        declaration_type=decl_in.declaration_type,
        declarant_name=decl_in.candidate_name,
        cpf=decl_in.cpf,
        content_text=text,
        signed_digitally=True
    )
    db.add(decl)
    await db.commit()
    await db.refresh(decl)

    await AuditService.log_action(
        db=db,
        tenant_id=tenant_id,
        user_id="user-demo",
        action="OAB_DECLARATION_GENERATED",
        resource_type="oab_declarations",
        resource_id=decl.id,
        details={"type": decl.declaration_type}
    )

    return {
        "status": "success",
        "declaration_id": decl.id,
        "content_text": decl.content_text,
        "type": decl.declaration_type
    }
