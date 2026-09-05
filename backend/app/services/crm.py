from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import CRMOpportunity
from app.models.operations import PublicIntake
from app.models.user import User
from app.models.workspace import WorkspaceCase
from app.schemas.crm import OpportunityCreate, OpportunityUpdate
from app.services.workspace_service import CASE_MANAGER_ROLES, active_tenant_user, case_access_clause, get_case, get_client, require_role


CRM_READ_ROLES = CASE_MANAGER_ROLES | {"paralegal"}


def conflict(message: str = "Oportunidade alterada por outra sessao.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def opportunity_statement(user: User, *, include_archived: bool = False):
    statement = (
        select(CRMOpportunity)
        .outerjoin(
            WorkspaceCase,
            and_(
                WorkspaceCase.tenant_id == CRMOpportunity.tenant_id,
                WorkspaceCase.id == CRMOpportunity.case_id,
            ),
        )
        .where(
            CRMOpportunity.tenant_id == user.tenant_id,
            or_(CRMOpportunity.case_id.is_(None), case_access_clause(user, WorkspaceCase)),
        )
    )
    if not include_archived:
        statement = statement.where(CRMOpportunity.archived_at.is_(None))
    return statement


async def get_opportunity(
    db: AsyncSession,
    user: User,
    opportunity_id: str,
    *,
    for_update: bool = False,
) -> CRMOpportunity:
    statement = opportunity_statement(user, include_archived=True).where(CRMOpportunity.id == opportunity_id)
    if for_update:
        statement = statement.with_for_update(of=CRMOpportunity)
    opportunity = await db.scalar(statement)
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade nao encontrada.")
    return opportunity


async def validate_opportunity_links(
    db: AsyncSession,
    user: User,
    *,
    client_id: str | None,
    case_id: str | None,
    intake_id: str | None,
    owner_user_id: str | None,
) -> dict[str, str | None]:
    if intake_id:
        intake = await db.scalar(
            select(PublicIntake).where(PublicIntake.tenant_id == user.tenant_id, PublicIntake.id == intake_id)
        )
        if not intake:
            raise HTTPException(status_code=422, detail="Atendimento nao encontrado.")
        if intake.converted_client_id:
            if client_id and client_id != intake.converted_client_id:
                raise HTTPException(status_code=422, detail="O atendimento nao pertence ao cliente informado.")
            client_id = intake.converted_client_id
        if intake.converted_case_id:
            if case_id and case_id != intake.converted_case_id:
                raise HTTPException(status_code=422, detail="O atendimento nao pertence ao processo informado.")
            case_id = intake.converted_case_id
    if case_id:
        case = await get_case(db, user, case_id)
        if client_id and client_id != case.client_id:
            raise HTTPException(status_code=422, detail="O processo nao pertence ao cliente informado.")
        client_id = case.client_id
    if client_id:
        await get_client(db, user, client_id)
    if owner_user_id:
        owner = await active_tenant_user(db, user.tenant_id, owner_user_id)
        if owner.role not in CASE_MANAGER_ROLES:
            raise HTTPException(status_code=422, detail="Responsavel deve ser advogado, socio ou administrador.")
    return {
        "client_id": client_id,
        "case_id": case_id,
        "intake_id": intake_id,
        "owner_user_id": owner_user_id,
    }


def opportunity_values_match(opportunity: CRMOpportunity, values: dict) -> bool:
    return all(getattr(opportunity, field) == value for field, value in values.items())


def validate_next_action(next_action: str | None, next_action_at: datetime | None) -> None:
    if next_action_at and not next_action:
        raise HTTPException(status_code=422, detail="Informe a proxima acao quando houver data.")


async def list_opportunities(
    db: AsyncSession,
    user: User,
    *,
    stage: str | None,
    owner_user_id: str | None,
    include_archived: bool,
    limit: int,
) -> list[CRMOpportunity]:
    require_role(user, CRM_READ_ROLES)
    statement = opportunity_statement(user, include_archived=include_archived)
    if stage:
        statement = statement.where(CRMOpportunity.stage == stage)
    if owner_user_id:
        statement = statement.where(CRMOpportunity.owner_user_id == owner_user_id)
    return (
        await db.execute(
            statement.order_by(CRMOpportunity.next_action_at.asc().nullslast(), CRMOpportunity.updated_at.desc()).limit(limit)
        )
    ).scalars().all()


async def create_opportunity(
    db: AsyncSession,
    user: User,
    payload: OpportunityCreate,
) -> tuple[CRMOpportunity, bool]:
    require_role(user, CASE_MANAGER_ROLES)
    values = payload.model_dump(exclude={"request_id"})
    values.update(await validate_opportunity_links(db, user, **{key: values[key] for key in ("client_id", "case_id", "intake_id", "owner_user_id")}))
    validate_next_action(values["next_action"], values["next_action_at"])
    request_id = str(payload.request_id)
    existing = await db.scalar(
        select(CRMOpportunity).where(
            CRMOpportunity.tenant_id == user.tenant_id,
            CRMOpportunity.request_id == request_id,
        )
    )
    if existing:
        if opportunity_values_match(existing, values):
            return existing, True
        raise conflict("Chave de repeticao ja usada para outra oportunidade.")
    opportunity = CRMOpportunity(
        tenant_id=user.tenant_id,
        request_id=request_id,
        created_by_user_id=user.id,
        **values,
    )
    try:
        async with db.begin_nested():
            db.add(opportunity)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(CRMOpportunity).where(
                CRMOpportunity.tenant_id == user.tenant_id,
                CRMOpportunity.request_id == request_id,
            )
        )
        if existing and opportunity_values_match(existing, values):
            return existing, True
        if existing:
            raise conflict("Chave de repeticao ja usada para outra oportunidade.")
        raise
    return opportunity, False


async def update_opportunity(
    db: AsyncSession,
    user: User,
    opportunity_id: str,
    payload: OpportunityUpdate,
) -> tuple[CRMOpportunity, bool]:
    require_role(user, CASE_MANAGER_ROLES)
    opportunity = await get_opportunity(db, user, opportunity_id, for_update=True)
    if opportunity.archived_at:
        raise conflict("Oportunidade arquivada nao pode ser alterada.")
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
    if not changes:
        raise HTTPException(status_code=422, detail="Nenhuma alteracao informada.")
    link_fields = ("client_id", "case_id", "intake_id", "owner_user_id")
    if any(key in changes for key in link_fields):
        links = {key: changes.get(key, getattr(opportunity, key)) for key in link_fields}
        changes.update(await validate_opportunity_links(db, user, **links))
    next_action = changes.get("next_action", opportunity.next_action)
    next_action_at = changes.get("next_action_at", opportunity.next_action_at)
    validate_next_action(next_action, next_action_at)
    if opportunity.revision != payload.expected_revision:
        if opportunity_values_match(opportunity, changes):
            return opportunity, False
        raise conflict()
    if opportunity_values_match(opportunity, changes):
        return opportunity, False
    for field, value in changes.items():
        if field in {"title", "stage", "source"} and value is None:
            continue
        setattr(opportunity, field, value)
    opportunity.revision += 1
    await db.flush()
    return opportunity, True


async def archive_opportunity(
    db: AsyncSession,
    user: User,
    opportunity_id: str,
    expected_revision: int,
) -> tuple[CRMOpportunity, bool]:
    require_role(user, CASE_MANAGER_ROLES)
    opportunity = await get_opportunity(db, user, opportunity_id, for_update=True)
    if opportunity.archived_at:
        return opportunity, False
    if opportunity.revision != expected_revision:
        raise conflict()
    opportunity.archived_at = datetime.now(timezone.utc)
    opportunity.revision += 1
    await db.flush()
    return opportunity, True
