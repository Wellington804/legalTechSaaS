from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_tenant_write
from app.models.user import User
from app.schemas.crm import OpportunityArchive, OpportunityCreate, OpportunityListResponse, OpportunityResponse, OpportunityUpdate
from app.services.audit_service import AuditService
from app.services.crm import archive_opportunity, create_opportunity, list_opportunities, update_opportunity
from app.services.workspace_service import bounded_limit


router = APIRouter(dependencies=[Depends(get_current_user)])


async def commit_crm_mutation(
    db: AsyncSession,
    request: Request,
    user: User,
    action: str,
    opportunity_id: str,
    details: dict | None = None,
) -> None:
    await AuditService.log_action(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=action,
        resource_type="crm_opportunities",
        resource_id=opportunity_id,
        details=details or {},
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )
    await db.commit()


@router.get("/opportunities", response_model=OpportunityListResponse)
async def get_opportunities(
    stage: str | None = Query(default=None, pattern="^(new|qualified|proposal|won|lost)$"),
    owner_user_id: str | None = Query(default=None, max_length=64),
    include_archived: bool = False,
    limit: int = Query(default=200, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    items = await list_opportunities(
        db,
        current_user,
        stage=stage,
        owner_user_id=owner_user_id,
        include_archived=include_archived,
        limit=limit,
    )
    return OpportunityListResponse(items=[OpportunityResponse.model_validate(item) for item in items], limit=limit)


@router.post("/opportunities", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
async def post_opportunity(
    payload: OpportunityCreate,
    request: Request,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    opportunity, existing = await create_opportunity(db, current_user, payload)
    if not existing:
        await commit_crm_mutation(db, request, current_user, "CRM_OPPORTUNITY_CREATED", opportunity.id)
    return OpportunityResponse.model_validate(opportunity)


@router.put("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def put_opportunity(
    opportunity_id: str,
    payload: OpportunityUpdate,
    request: Request,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    opportunity, changed = await update_opportunity(db, current_user, opportunity_id, payload)
    if changed:
        fields = sorted(payload.model_dump(exclude_unset=True, exclude={"expected_revision"}))
        await commit_crm_mutation(
            db, request, current_user, "CRM_OPPORTUNITY_UPDATED", opportunity.id, {"fields": fields}
        )
    return OpportunityResponse.model_validate(opportunity)


@router.post("/opportunities/{opportunity_id}/archive", response_model=OpportunityResponse)
async def post_opportunity_archive(
    opportunity_id: str,
    payload: OpportunityArchive,
    request: Request,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    opportunity, changed = await archive_opportunity(
        db, current_user, opportunity_id, payload.expected_revision
    )
    if changed:
        await commit_crm_mutation(db, request, current_user, "CRM_OPPORTUNITY_ARCHIVED", opportunity.id)
    return OpportunityResponse.model_validate(opportunity)
