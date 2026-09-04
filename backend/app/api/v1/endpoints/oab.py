from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.models.oab import OABApplication, OABChecklist, OABDeclaration
from app.schemas.oab import (
    OABApplicationCreate,
    FeeSimulationRequest,
    FeeSimulationResponse,
    DeclarationGenerateRequest
)
from app.services.oab_service import OABService
from app.services.audit_service import AuditService

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.post("/applications")
async def create_oab_application(
    app_in: OABApplicationCreate,
    req: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    app = await OABService.create_application(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        data=app_in.model_dump()
    )

    await AuditService.log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="OAB_APPLICATION_CREATED",
        resource_type="oab_applications",
        resource_id=app.id,
        details={"seccional": app.seccional},
        ip_address=req.client.host if req.client else None,
        user_agent=(req.headers.get("user-agent") or "")[:512] or None,
    )
    await db.commit()

    return {
        "status": "draft",
        "application_id": app.id,
        "protocol": None,
        "internal_reference": app.id,
    }

@router.get("/applications/{app_id}/checklist")
async def get_application_checklist(
    app_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    application = await db.scalar(
        select(OABApplication).where(
            OABApplication.id == app_id,
            OABApplication.tenant_id == current_user.tenant_id,
        )
    )
    if not application:
        raise HTTPException(status_code=404, detail="Requerimento OAB nao encontrado.")
    result = await db.execute(select(OABChecklist).where(OABChecklist.application_id == app_id))
    items = result.scalars().all()
    return items

@router.post("/applications/{app_id}/checklist/{item_id}/toggle")
async def toggle_checklist_item(
    app_id: str,
    item_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OABChecklist)
        .join(OABApplication, OABApplication.id == OABChecklist.application_id)
        .where(
            OABChecklist.id == item_id,
            OABChecklist.application_id == app_id,
            OABApplication.tenant_id == current_user.tenant_id,
        )
    )
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
    decl_in: DeclarationGenerateRequest,
    req: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    application = await db.scalar(
        select(OABApplication).where(
            OABApplication.id == decl_in.application_id,
            OABApplication.tenant_id == current_user.tenant_id,
        )
    )
    if not application:
        raise HTTPException(status_code=404, detail="Requerimento OAB nao encontrado.")

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
        signed_digitally=False
    )
    db.add(decl)
    await db.flush()

    await AuditService.log_action(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="OAB_DECLARATION_GENERATED",
        resource_type="oab_declarations",
        resource_id=decl.id,
        details={"type": decl.declaration_type},
        ip_address=req.client.host if req.client else None,
        user_agent=(req.headers.get("user-agent") or "")[:512] or None,
    )
    await db.commit()

    return {
        "status": "draft",
        "signed_digitally": False,
        "declaration_id": decl.id,
        "content_text": decl.content_text,
        "type": decl.declaration_type
    }
