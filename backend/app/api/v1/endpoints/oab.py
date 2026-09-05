from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_tenant_write
from app.models.user import User
from app.schemas.oab import (
    OABChecklistItemCreate,
    OABChecklistItemResponse,
    OABChecklistItemUpdate,
    OABEnrollmentCreate,
    OABEnrollmentList,
    OABEnrollmentResponse,
    OABEnrollmentUpdate,
    OABSourceList,
)
from app.services.audit_service import AuditService
from app.services.oab_service import OABNotFoundError, OABRequestConflictError, OABRevisionConflictError, OABService, PROVISION_URL, SOURCE_NOTICE, list_sources
from app.services.workspace_service import require_role


def require_oab_role(user: CurrentUser) -> None:
    require_role(user, {"admin", "partner", "lawyer"})


router = APIRouter(dependencies=[Depends(require_oab_role)])


def conflict() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registro alterado em outra sessao. Recarregue e tente novamente.")


async def audit(db: AsyncSession, request: Request, user: User, action: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
    await AuditService.log_action(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )


async def response_for(db: AsyncSession, enrollment, user: User, checklist=None) -> OABEnrollmentResponse:
    if checklist is None:
        checklist = await OABService.list_checklist(db, user.tenant_id, user.id, enrollment.id)
    return OABEnrollmentResponse.model_validate({
        **{column.name: getattr(enrollment, column.name) for column in enrollment.__table__.columns},
        "checklist": [OABChecklistItemResponse.model_validate(item) for item in checklist],
        "source_notice": SOURCE_NOTICE,
        "provision_url": PROVISION_URL,
    })


@router.get("/sources", response_model=OABSourceList)
async def sources(query: str | None = Query(default=None, max_length=80)):
    items = list_sources(query)
    return {"items": items, "count": len(items)}


@router.get("/enrollments", response_model=OABEnrollmentList)
async def enrollments(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    records = await OABService.list_enrollments(db, current_user.tenant_id, current_user.id)
    checklist_by_enrollment = {}
    for item in await OABService.list_owner_checklist(db, current_user.tenant_id, current_user.id):
        checklist_by_enrollment.setdefault(item.enrollment_id, []).append(item)
    items = [
        await response_for(db, record, current_user, checklist_by_enrollment.get(record.id, []))
        for record in records
    ]
    return {"items": items, "count": len(items)}


@router.post("/enrollments", response_model=OABEnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    payload: OABEnrollmentCreate,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    try:
        enrollment, reused = await OABService.create_enrollment(db, current_user.tenant_id, current_user.id, payload)
    except OABRequestConflictError:
        raise HTTPException(status_code=409, detail="Identificador de repetição já usado com outros dados.")
    if not reused:
        await audit(db, request, current_user, "OAB_ENROLLMENT_CREATED", "oab_enrollments", enrollment.id, {"uf": enrollment.uf, "type": enrollment.enrollment_type})
    result = await response_for(db, enrollment, current_user)
    await db.commit()
    return result


@router.patch("/enrollments/{enrollment_id}", response_model=OABEnrollmentResponse)
async def update_enrollment(
    enrollment_id: str,
    payload: OABEnrollmentUpdate,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    try:
        enrollment = await OABService.update_enrollment(db, current_user.tenant_id, current_user.id, enrollment_id, payload)
    except OABNotFoundError:
        raise HTTPException(status_code=404, detail="Acompanhamento de inscricao nao encontrado.")
    except OABRevisionConflictError:
        raise conflict()
    await audit(db, request, current_user, "OAB_ENROLLMENT_UPDATED", "oab_enrollments", enrollment.id, {"fields": sorted(payload.model_fields_set - {"expected_revision"})})
    result = await response_for(db, enrollment, current_user)
    await db.commit()
    return result


@router.post("/enrollments/{enrollment_id}/checklist", response_model=OABChecklistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_checklist_item(
    enrollment_id: str,
    payload: OABChecklistItemCreate,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    try:
        item, reused = await OABService.add_checklist_item(db, current_user.tenant_id, current_user.id, enrollment_id, payload)
    except OABNotFoundError:
        raise HTTPException(status_code=404, detail="Acompanhamento de inscricao nao encontrado.")
    except OABRequestConflictError:
        raise HTTPException(status_code=409, detail="Identificador de repetição já usado com outros dados.")
    if not reused:
        await audit(db, request, current_user, "OAB_CHECKLIST_ITEM_CREATED", "oab_enrollment_checklist_items", item.id, {"enrollment_id": enrollment_id})
    await db.commit()
    return item


@router.patch("/enrollments/{enrollment_id}/checklist/{item_id}", response_model=OABChecklistItemResponse)
async def update_checklist_item(
    enrollment_id: str,
    item_id: str,
    payload: OABChecklistItemUpdate,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    try:
        item = await OABService.update_checklist_item(db, current_user.tenant_id, current_user.id, enrollment_id, item_id, payload)
    except OABNotFoundError:
        raise HTTPException(status_code=404, detail="Item do checklist nao encontrado.")
    except OABRevisionConflictError:
        raise conflict()
    await audit(db, request, current_user, "OAB_CHECKLIST_ITEM_UPDATED", "oab_enrollment_checklist_items", item.id, {"enrollment_id": enrollment_id, "fields": sorted(payload.model_fields_set - {"expected_revision"})})
    await db.commit()
    return item


@router.delete("/enrollments/{enrollment_id}/checklist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist_item(
    enrollment_id: str,
    item_id: str,
    request: Request,
    *,
    expected_revision: int = Query(ge=1),
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    try:
        await OABService.delete_checklist_item(db, current_user.tenant_id, current_user.id, enrollment_id, item_id, expected_revision)
    except OABNotFoundError:
        raise HTTPException(status_code=404, detail="Item do checklist nao encontrado.")
    except OABRevisionConflictError:
        raise conflict()
    await audit(db, request, current_user, "OAB_CHECKLIST_ITEM_DELETED", "oab_enrollment_checklist_items", item_id, {"enrollment_id": enrollment_id})
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
