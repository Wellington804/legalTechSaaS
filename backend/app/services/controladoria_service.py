"""Authorization-aware commands for the judicial control desk.

The provider layer may collect evidence, but only these commands turn it into
tenant data. No command computes a legal deadline; a supplied suggestion can
become a workspace task only through ``approve_deadline_and_create_task``.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.controladoria import (
    ControladoriaDeadlineReview,
    ControladoriaJudicialEvent,
    ControladoriaMonitoringSubscription,
    ControladoriaWorkflowRun,
    ControladoriaWorkflowRunItem,
    ControladoriaWorkflowTemplate,
    ControladoriaWorkflowTemplateStep,
)
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceTask
from app.schemas.controladoria import (
    DeadlineSuggestionCreate,
    JudicialEventCreate,
    MonitoringSubscriptionCreate,
    SUPPORTED_DATAJUD_TRIBUNALS,
    WorkflowRunCreate,
    WorkflowRunItemUpdate,
    WorkflowTemplateCreate,
)
from app.services.workspace_service import (
    active_tenant_user,
    case_access_clause,
    get_case,
    require_case_write,
    require_role,
)


CONTROLADORIA_TRIAGE_ROLES = {"admin", "partner", "lawyer", "paralegal"}
WORKFLOW_TEMPLATE_ROLES = {"admin", "partner"}
T = TypeVar("T")


def _not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} nao encontrado.")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def normalize_cnj(value: str | None) -> str:
    number = re.sub(r"\D", "", value or "")
    if len(number) != 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O caso precisa ter numero CNJ com 20 digitos para monitoramento.",
        )
    return number


STATE_COURTS = {
    "01": "tjac", "02": "tjal", "03": "tjap", "04": "tjam", "05": "tjba", "06": "tjce",
    "07": "tjdft", "08": "tjes", "09": "tjgo", "10": "tjma", "11": "tjmt", "12": "tjms",
    "13": "tjmg", "14": "tjpa", "15": "tjpb", "16": "tjpr", "17": "tjpe", "18": "tjpi",
    "19": "tjrj", "20": "tjrn", "21": "tjrs", "22": "tjro", "23": "tjrr", "24": "tjsc",
    "25": "tjse", "26": "tjsp", "27": "tjto",
}
ELECTORAL_COURTS = {code: f"tre-{court[2:]}" for code, court in STATE_COURTS.items()}
MILITARY_COURTS = {"13": "tjmmg", "21": "tjmrs", "26": "tjmsp"}


def infer_datajud_tribunal(process_number: str | None, court: str | None = None) -> str | None:
    """Infer the official DataJud alias from a CNJ number, with court text as a safe fallback."""
    number = re.sub(r"\D", "", process_number or "")
    if len(number) == 20:
        justice, region = number[13], number[14:16]
        if justice == "3":
            return "stj"
        if justice == "4" and region in {f"0{i}" for i in range(1, 7)}:
            return f"trf{int(region)}"
        if justice == "5" and region.isdigit() and 1 <= int(region) <= 24:
            return f"trt{int(region)}"
        if justice == "6":
            return ELECTORAL_COURTS.get(region)
        if justice == "7":
            return "stm"
        if justice == "8":
            return STATE_COURTS.get(region)
        if justice == "9":
            return MILITARY_COURTS.get(region)
    normalized_court = re.sub(r"[^a-z0-9-]", "", (court or "").casefold())
    for alias in sorted(SUPPORTED_DATAJUD_TRIBUNALS, key=len, reverse=True):
        if alias.replace("-", "") in normalized_court.replace("-", ""):
            return alias
    return None


def event_dedupe_key(case_id: str, payload: JudicialEventCreate) -> str:
    """Stable per-source-event identity, scoped by the bound case."""
    material = "\x1f".join(
        (
            case_id,
            payload.source_kind,
            payload.source_event_id,
            payload.occurred_at.isoformat() if payload.occurred_at else "",
            payload.title,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def case_scoped_statement(model: type[T], user: User):
    """Select a case-bound model only when the caller has the case ACL."""
    return (
        select(model)
        .join(
            WorkspaceCase,
            and_(WorkspaceCase.id == model.case_id, WorkspaceCase.tenant_id == model.tenant_id),
        )
        .where(model.tenant_id == user.tenant_id, case_access_clause(user))
    )


async def get_subscription(
    db: AsyncSession, user: User, subscription_id: str, *, for_update: bool = False
) -> ControladoriaMonitoringSubscription:
    statement = case_scoped_statement(ControladoriaMonitoringSubscription, user).where(
        ControladoriaMonitoringSubscription.id == subscription_id
    )
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise _not_found("Assinatura de monitoramento")
    return record


async def get_event(
    db: AsyncSession, user: User, event_id: str, *, for_update: bool = False
) -> ControladoriaJudicialEvent:
    statement = case_scoped_statement(ControladoriaJudicialEvent, user).where(
        ControladoriaJudicialEvent.id == event_id
    )
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise _not_found("Evento judicial")
    return record


async def get_deadline_review(
    db: AsyncSession, user: User, review_id: str, *, for_update: bool = False
) -> ControladoriaDeadlineReview:
    statement = case_scoped_statement(ControladoriaDeadlineReview, user).where(
        ControladoriaDeadlineReview.id == review_id
    )
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise _not_found("Revisao de prazo")
    return record


async def get_workflow_template(
    db: AsyncSession, user: User, template_id: str, *, for_update: bool = False
) -> ControladoriaWorkflowTemplate:
    statement = select(ControladoriaWorkflowTemplate).where(
        ControladoriaWorkflowTemplate.id == template_id,
        ControladoriaWorkflowTemplate.tenant_id == user.tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise _not_found("Template de workflow")
    return record


async def get_workflow_run(
    db: AsyncSession, user: User, run_id: str, *, for_update: bool = False
) -> ControladoriaWorkflowRun:
    statement = case_scoped_statement(ControladoriaWorkflowRun, user).where(
        ControladoriaWorkflowRun.id == run_id
    )
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise _not_found("Execucao de workflow")
    return record


async def get_workflow_run_item(
    db: AsyncSession, user: User, run_id: str, item_id: str, *, for_update: bool = False
) -> ControladoriaWorkflowRunItem:
    statement = (
        select(ControladoriaWorkflowRunItem)
        .join(
            ControladoriaWorkflowRun,
            and_(
                ControladoriaWorkflowRun.id == ControladoriaWorkflowRunItem.workflow_run_id,
                ControladoriaWorkflowRun.tenant_id == ControladoriaWorkflowRunItem.tenant_id,
            ),
        )
        .join(
            WorkspaceCase,
            and_(
                WorkspaceCase.id == ControladoriaWorkflowRun.case_id,
                WorkspaceCase.tenant_id == ControladoriaWorkflowRun.tenant_id,
            ),
        )
        .where(
            ControladoriaWorkflowRunItem.id == item_id,
            ControladoriaWorkflowRunItem.workflow_run_id == run_id,
            ControladoriaWorkflowRunItem.tenant_id == user.tenant_id,
            case_access_clause(user),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise _not_found("Item de checklist")
    return record


async def create_monitoring_subscription(
    db: AsyncSession, user: User, payload: MonitoringSubscriptionCreate, *, source_kind: str = "datajud"
) -> tuple[ControladoriaMonitoringSubscription, bool]:
    case = await get_case(db, user, payload.case_id)
    require_case_write(user, case)
    process_number = normalize_cnj(case.number)
    tribunal = payload.tribunal or infer_datajud_tribunal(case.number, case.court)
    if not tribunal:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nao foi possivel identificar o tribunal. Confira o numero CNJ ou informe o tribunal.",
        )
    existing = await db.scalar(
        select(ControladoriaMonitoringSubscription).where(
            ControladoriaMonitoringSubscription.tenant_id == user.tenant_id,
            ControladoriaMonitoringSubscription.case_id == case.id,
            ControladoriaMonitoringSubscription.source_kind == source_kind,
            ControladoriaMonitoringSubscription.tribunal == tribunal,
        )
    )
    if existing:
        return existing, False
    record = ControladoriaMonitoringSubscription(
        tenant_id=user.tenant_id,
        case_id=case.id,
        tribunal=tribunal,
        process_number=process_number,
        source_kind=source_kind,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(ControladoriaMonitoringSubscription).where(
                ControladoriaMonitoringSubscription.tenant_id == user.tenant_id,
                ControladoriaMonitoringSubscription.case_id == case.id,
                ControladoriaMonitoringSubscription.source_kind == source_kind,
                ControladoriaMonitoringSubscription.tribunal == tribunal,
            )
        )
        if existing:
            return existing, False
        raise
    return record, True


async def set_subscription_status(
    db: AsyncSession, user: User, subscription_id: str, new_status: str
) -> ControladoriaMonitoringSubscription:
    record = await get_subscription(db, user, subscription_id, for_update=True)
    case = await get_case(db, user, record.case_id)
    require_case_write(user, case)
    record.status = new_status
    record.updated_by_user_id = user.id
    await db.flush()
    return record


async def record_judicial_event(
    db: AsyncSession,
    user: User,
    payload: JudicialEventCreate,
    *,
    created_by_user_id: str | None = None,
) -> tuple[ControladoriaJudicialEvent, bool]:
    """Persist one source-attributed event without deriving legal effects."""
    require_role(user, CONTROLADORIA_TRIAGE_ROLES)
    case = await get_case(db, user, payload.case_id)
    if payload.subscription_id:
        subscription = await get_subscription(db, user, payload.subscription_id)
        if subscription.case_id != case.id or subscription.status == "disabled":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assinatura nao corresponde ao caso.")
    dedupe_key = event_dedupe_key(case.id, payload)
    existing = await db.scalar(
        select(ControladoriaJudicialEvent).where(
            ControladoriaJudicialEvent.tenant_id == user.tenant_id,
            ControladoriaJudicialEvent.dedupe_key == dedupe_key,
        )
    )
    if existing:
        return existing, False
    record = ControladoriaJudicialEvent(
        tenant_id=user.tenant_id,
        dedupe_key=dedupe_key,
        created_by_user_id=created_by_user_id if created_by_user_id is not None else user.id,
        **payload.model_dump(),
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(ControladoriaJudicialEvent).where(
                ControladoriaJudicialEvent.tenant_id == user.tenant_id,
                ControladoriaJudicialEvent.dedupe_key == dedupe_key,
            )
        )
        if existing:
            return existing, False
        raise
    return record, True


async def triage_judicial_event(
    db: AsyncSession, user: User, event_id: str, *, triage_status: str, note: str | None
) -> ControladoriaJudicialEvent:
    require_role(user, CONTROLADORIA_TRIAGE_ROLES)
    event = await get_event(db, user, event_id, for_update=True)
    if event.triage_status != "pending":
        if event.triage_status == triage_status:
            return event
        raise _conflict("O evento judicial ja foi triado.")
    event.triage_status = triage_status
    event.triage_note = note
    event.triaged_at = datetime.now(timezone.utc)
    event.triaged_by_user_id = user.id
    await db.flush()
    return event


async def create_deadline_suggestion(
    db: AsyncSession, user: User, payload: DeadlineSuggestionCreate
) -> tuple[ControladoriaDeadlineReview, bool]:
    event = await get_event(db, user, payload.event_id, for_update=True)
    case = await get_case(db, user, event.case_id)
    require_case_write(user, case)
    if event.triage_status != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O evento precisa ser revisado antes de sugerir um prazo.",
        )
    existing = await db.scalar(
        select(ControladoriaDeadlineReview).where(
            ControladoriaDeadlineReview.tenant_id == user.tenant_id,
            ControladoriaDeadlineReview.event_id == event.id,
        )
    )
    if existing:
        return existing, False
    if payload.assigned_user_id:
        await active_tenant_user(db, user.tenant_id, payload.assigned_user_id)
    record = ControladoriaDeadlineReview(
        tenant_id=user.tenant_id,
        case_id=event.case_id,
        event_id=event.id,
        suggested_by_user_id=user.id,
        **payload.model_dump(),
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(ControladoriaDeadlineReview).where(
                ControladoriaDeadlineReview.tenant_id == user.tenant_id,
                ControladoriaDeadlineReview.event_id == event.id,
            )
        )
        if existing:
            return existing, False
        raise
    return record, True


async def approve_deadline_and_create_task(
    db: AsyncSession, user: User, review_id: str, *, note: str
) -> tuple[ControladoriaDeadlineReview, WorkspaceTask]:
    """The sole path from a suggested date to a deadline task."""
    review = await get_deadline_review(db, user, review_id, for_update=True)
    case = await get_case(db, user, review.case_id)
    require_case_write(user, case)
    if review.status != "suggested":
        raise _conflict("A revisao de prazo ja recebeu decisao humana.")
    if review.assigned_user_id:
        await active_tenant_user(db, user.tenant_id, review.assigned_user_id)
    task = WorkspaceTask(
        tenant_id=user.tenant_id,
        case_id=review.case_id,
        title=review.title,
        kind="deadline",
        due_at=review.suggested_due_at,
        assigned_user_id=review.assigned_user_id,
        manually_reviewed=True,
        notes=f"Controladoria: prazo aprovado por revisao humana. Fundamentacao: {review.suggested_basis}",
    )
    db.add(task)
    await db.flush()
    review.status = "approved"
    review.review_note = note
    review.reviewed_by_user_id = user.id
    review.reviewed_at = datetime.now(timezone.utc)
    review.task_id = task.id
    await db.flush()
    return review, task


async def reject_deadline_suggestion(
    db: AsyncSession, user: User, review_id: str, *, note: str
) -> ControladoriaDeadlineReview:
    review = await get_deadline_review(db, user, review_id, for_update=True)
    case = await get_case(db, user, review.case_id)
    require_case_write(user, case)
    if review.status != "suggested":
        raise _conflict("A revisao de prazo ja recebeu decisao humana.")
    review.status = "rejected"
    review.review_note = note
    review.reviewed_by_user_id = user.id
    review.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    return review


async def workflow_template_steps(
    db: AsyncSession, user: User, template_id: str
) -> list[ControladoriaWorkflowTemplateStep]:
    await get_workflow_template(db, user, template_id)
    return (
        await db.execute(
            select(ControladoriaWorkflowTemplateStep)
            .where(
                ControladoriaWorkflowTemplateStep.tenant_id == user.tenant_id,
                ControladoriaWorkflowTemplateStep.template_id == template_id,
            )
            .order_by(ControladoriaWorkflowTemplateStep.position.asc())
        )
    ).scalars().all()


async def create_workflow_template(
    db: AsyncSession, user: User, payload: WorkflowTemplateCreate
) -> ControladoriaWorkflowTemplate:
    require_role(user, WORKFLOW_TEMPLATE_ROLES)
    existing = await db.scalar(
        select(ControladoriaWorkflowTemplate).where(
            ControladoriaWorkflowTemplate.tenant_id == user.tenant_id,
            ControladoriaWorkflowTemplate.name == payload.name,
            ControladoriaWorkflowTemplate.version == payload.version,
        )
    )
    if existing:
        raise _conflict("Ja existe template com este nome e versao.")
    template = ControladoriaWorkflowTemplate(
        tenant_id=user.tenant_id,
        name=payload.name,
        case_type=payload.case_type,
        version=payload.version,
        description=payload.description,
        created_by_user_id=user.id,
    )
    db.add(template)
    await db.flush()
    for step in payload.steps:
        db.add(
            ControladoriaWorkflowTemplateStep(
                tenant_id=user.tenant_id,
                template_id=template.id,
                **step.model_dump(),
            )
        )
    await db.flush()
    return template


async def start_workflow_run(
    db: AsyncSession, user: User, payload: WorkflowRunCreate
) -> ControladoriaWorkflowRun:
    template = await get_workflow_template(db, user, payload.template_id)
    if not template.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Template de workflow inativo.")
    case = await get_case(db, user, payload.case_id)
    require_case_write(user, case)
    steps = await workflow_template_steps(db, user, template.id)
    if not steps:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Template sem checklist.")
    run = ControladoriaWorkflowRun(
        tenant_id=user.tenant_id,
        case_id=case.id,
        template_id=template.id,
        template_name=template.name,
        template_version=template.version,
        started_by_user_id=user.id,
    )
    db.add(run)
    await db.flush()
    for step in steps:
        db.add(
            ControladoriaWorkflowRunItem(
                tenant_id=user.tenant_id,
                workflow_run_id=run.id,
                position=step.position,
                title=step.title,
                instructions=step.instructions,
                is_required=step.is_required,
            )
        )
    await db.flush()
    return run


async def workflow_run_items(
    db: AsyncSession, user: User, run_id: str
) -> list[ControladoriaWorkflowRunItem]:
    await get_workflow_run(db, user, run_id)
    return (
        await db.execute(
            select(ControladoriaWorkflowRunItem)
            .where(
                ControladoriaWorkflowRunItem.tenant_id == user.tenant_id,
                ControladoriaWorkflowRunItem.workflow_run_id == run_id,
            )
            .order_by(ControladoriaWorkflowRunItem.position.asc())
        )
    ).scalars().all()


async def resolve_workflow_run_item(
    db: AsyncSession,
    user: User,
    run_id: str,
    item_id: str,
    payload: WorkflowRunItemUpdate,
) -> ControladoriaWorkflowRunItem:
    require_role(user, CONTROLADORIA_TRIAGE_ROLES)
    run = await get_workflow_run(db, user, run_id, for_update=True)
    case = await get_case(db, user, run.case_id)
    require_case_write(user, case)
    if run.status != "open":
        raise _conflict("O workflow nao esta aberto.")
    item = await get_workflow_run_item(db, user, run_id, item_id, for_update=True)
    if item.revision != payload.expected_revision:
        raise _conflict("O item foi alterado por outra sessao.")
    if item.status != "pending":
        raise _conflict("O item de checklist ja foi resolvido.")
    item.status = payload.status
    item.resolution_note = payload.resolution_note
    item.resolved_by_user_id = user.id
    item.resolved_at = datetime.now(timezone.utc)
    item.revision += 1
    await db.flush()
    return item


async def complete_workflow_run(
    db: AsyncSession, user: User, run_id: str, *, expected_revision: int
) -> ControladoriaWorkflowRun:
    run = await get_workflow_run(db, user, run_id, for_update=True)
    case = await get_case(db, user, run.case_id)
    require_case_write(user, case)
    if run.revision != expected_revision:
        raise _conflict("O workflow foi alterado por outra sessao.")
    if run.status != "open":
        raise _conflict("O workflow ja foi encerrado.")
    pending_required = await db.scalar(
        select(ControladoriaWorkflowRunItem.id).where(
            ControladoriaWorkflowRunItem.tenant_id == user.tenant_id,
            ControladoriaWorkflowRunItem.workflow_run_id == run.id,
            ControladoriaWorkflowRunItem.is_required.is_(True),
            ControladoriaWorkflowRunItem.status == "pending",
        )
    )
    if pending_required:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conclua ou justifique todos os itens obrigatorios antes de encerrar.",
        )
    run.status = "completed"
    run.completed_by_user_id = user.id
    run.completed_at = datetime.now(timezone.utc)
    run.revision += 1
    await db.flush()
    return run
