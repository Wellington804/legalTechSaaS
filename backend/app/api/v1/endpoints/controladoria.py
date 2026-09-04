"""Mounted HTTP boundary for the human-reviewed judicial control desk.

Provider polling remains asynchronous; request handlers only persist control
decisions, validate source availability, or enqueue bounded background work.
"""

import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import CurrentUser, require_tenant_write
from app.core.request_body import read_limited_body
from app.models.controladoria import (
    ControladoriaCalendarException,
    ControladoriaDeadlineReview,
    ControladoriaDeadlineRule,
    ControladoriaJudicialEvent,
    ControladoriaMonitoringSubscription,
    ControladoriaWorkflowRun,
    ControladoriaWorkflowTemplate,
)
from app.models.user import User
from app.schemas.controladoria import (
    CalendarExceptionCreate,
    CalendarExceptionResponse,
    ControladoriaListResponse,
    DeadlineCalculationCreate,
    DeadlineDecision,
    DeadlineReviewResponse,
    DeadlineRuleCreate,
    DeadlineRuleResponse,
    DeadlineRuleReview,
    DeadlineSuggestionCreate,
    JudicialEventCreate,
    JudicialEventResponse,
    JudicialEventTriage,
    MonitoringSubscriptionCreate,
    MonitoringSubscriptionResponse,
    MonitoringSubscriptionUpdate,
    JudicialProviderStatus,
    WorkflowRunComplete,
    WorkflowRunCreate,
    WorkflowRunItemResponse,
    WorkflowRunItemUpdate,
    WorkflowRunResponse,
    WorkflowTemplateCreate,
    WorkflowTemplateResponse,
)
from app.services.audit_service import AuditService
from app.services.controladoria_service import (
    calculate_deadline_suggestion,
    case_scoped_statement,
    complete_workflow_run,
    create_calendar_exception,
    create_deadline_rule,
    create_deadline_suggestion,
    create_monitoring_subscription,
    create_workflow_template,
    get_event,
    get_workflow_template,
    get_workflow_run,
    get_workflow_run_item,
    record_judicial_event,
    reject_deadline_suggestion,
    review_deadline_rule,
    resolve_workflow_run_item,
    set_subscription_status,
    start_workflow_run,
    triage_judicial_event,
    workflow_run_items,
    workflow_template_steps,
    approve_deadline_and_create_task,
    get_subscription,
)
from app.services.controladoria_provider import (
    JudicialProviderError,
    monitoring_provider,
    parse_escavador_callback,
    provider_configuration_status,
)
from app.services.workspace_service import bounded_limit, get_case, require_role


router = APIRouter()
public_router = APIRouter()
MANUAL_REFRESH_SECONDS = 300
MAX_ESCAVADOR_CALLBACK_BYTES = 64_000


def valid_escavador_callback_token(authorization: str | None) -> bool:
    expected = getattr(settings, "ESCAVADOR_CALLBACK_TOKEN", None)
    if not getattr(settings, "ESCAVADOR_ENABLED", False) or not expected or not authorization:
        return False
    scheme, separator, supplied = authorization.partition(" ")
    return bool(
        separator
        and scheme.casefold() == "bearer"
        and supplied
        and hmac.compare_digest(supplied, expected)
    )


def enqueue_escavador_callback(payload: dict) -> None:
    from app.services.controladoria_tasks import ingest_escavador_callback

    ingest_escavador_callback.delay(payload)


@public_router.post("/webhooks/escavador", status_code=status.HTTP_202_ACCEPTED)
async def escavador_webhook(
    request: Request,
    authorization: str | None = Header(default=None, max_length=2048),
):
    if not valid_escavador_callback_token(authorization):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Callback nao autorizado.")
    raw = await read_limited_body(request, MAX_ESCAVADOR_CALLBACK_BYTES, "Callback muito grande.")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Callback invalido.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Callback invalido.")
    if payload["event"] != "nova_movimentacao":
        return {"received": True, "queued": False, "reason": "event_not_actionable"}
    try:
        parse_escavador_callback(payload)
    except JudicialProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Callback invalido.") from exc
    try:
        enqueue_escavador_callback(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Callback temporariamente indisponivel.",
        ) from exc
    return {"received": True, "queued": True}


async def reserve_manual_refresh(tenant_id: str, subscription_id: str) -> str:
    from app.core.redis_cache import cache_manager

    client = cache_manager.redis_client
    if not client:
        raise HTTPException(status_code=503, detail="Controle de frequência indisponível.")
    key = f"legaltech:controladoria:manual:{tenant_id}:{subscription_id}"
    try:
        reserved = await client.set(key, "1", ex=MANUAL_REFRESH_SECONDS, nx=True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Controle de frequência indisponível.") from exc
    if not reserved:
        raise HTTPException(
            status_code=429,
            detail="Uma consulta já foi solicitada. Aguarde até 5 minutos para consultar novamente.",
        )
    return key


async def audit_and_commit(
    db: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    await AuditService.log_action(
        db,
        user.tenant_id,
        user.id,
        action,
        resource_type,
        resource_id,
        details,
    )
    await db.commit()


async def workflow_template_payload(
    db: AsyncSession, user: User, template: ControladoriaWorkflowTemplate
) -> WorkflowTemplateResponse:
    from app.schemas.controladoria import WorkflowTemplateStepResponse

    steps = await workflow_template_steps(db, user, template.id)
    return WorkflowTemplateResponse.model_validate(template).model_copy(
        update={"steps": [WorkflowTemplateStepResponse.model_validate(step) for step in steps]}
    )


async def workflow_run_payload(
    db: AsyncSession, user: User, run: ControladoriaWorkflowRun
) -> WorkflowRunResponse:
    items = await workflow_run_items(db, user, run.id)
    return WorkflowRunResponse.model_validate(run).model_copy(
        update={"items": [WorkflowRunItemResponse.model_validate(item) for item in items]}
    )


async def deadline_review_payload(
    db: AsyncSession, user: User, review: ControladoriaDeadlineReview
) -> DeadlineReviewResponse:
    event = await get_event(db, user, review.event_id)
    payload = {
        field: getattr(review, field)
        for field in DeadlineReviewResponse.model_fields
        if field != "event"
    }
    payload["event"] = JudicialEventResponse.model_validate(event)
    return DeadlineReviewResponse.model_validate(payload)


@router.get("/subscriptions", response_model=ControladoriaListResponse)
async def list_subscriptions(
    case_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if case_id:
        await get_case(db, current_user, case_id)
    statement = case_scoped_statement(ControladoriaMonitoringSubscription, current_user)
    if case_id:
        statement = statement.where(ControladoriaMonitoringSubscription.case_id == case_id)
    records = (
        await db.execute(
            statement.order_by(ControladoriaMonitoringSubscription.updated_at.desc()).limit(bounded_limit(limit))
        )
    ).scalars().all()
    return ControladoriaListResponse(
        items=[MonitoringSubscriptionResponse.model_validate(record) for record in records],
        limit=bounded_limit(limit),
    )


@router.get("/providers", response_model=list[JudicialProviderStatus])
async def list_provider_status(
    tribunal: str | None = Query(default=None, min_length=2, max_length=20),
    *,
    current_user: CurrentUser,
):
    del current_user
    try:
        return [
            JudicialProviderStatus.model_validate(item)
            for item in provider_configuration_status(settings, tribunal)
        ]
    except JudicialProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A configuracao de fontes judiciais precisa de revisao.",
        ) from exc


@router.post("/subscriptions", response_model=MonitoringSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: MonitoringSubscriptionCreate,
    response: Response,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    source_kind = payload.source_kind or settings.JUDICIAL_MONITORING_PROVIDER
    record, created = await create_monitoring_subscription(
        db, current_user, payload, source_kind=source_kind
    )
    try:
        monitoring_provider(source_kind, settings, tribunal=record.tribunal)
    except JudicialProviderError as exc:
        if created:
            await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A fonte escolhida ainda nao possui configuracao ou homologacao operacional.",
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
        return MonitoringSubscriptionResponse.model_validate(record)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_MONITORING_SUBSCRIBED",
        "controladoria_monitoring_subscriptions",
        record.id,
        {"case_id": record.case_id, "source_kind": record.source_kind, "tribunal": record.tribunal},
    )
    return MonitoringSubscriptionResponse.model_validate(record)


@router.put("/subscriptions/{subscription_id}", response_model=MonitoringSubscriptionResponse)
async def update_subscription(
    subscription_id: str,
    payload: MonitoringSubscriptionUpdate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await set_subscription_status(db, current_user, subscription_id, payload.status)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_MONITORING_STATUS_CHANGED",
        "controladoria_monitoring_subscriptions",
        record.id,
        {"status": record.status},
    )
    return MonitoringSubscriptionResponse.model_validate(record)


@router.post("/subscriptions/{subscription_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_subscription(
    subscription_id: str,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await get_subscription(db, current_user, subscription_id)
    case = await get_case(db, current_user, record.case_id)
    from app.services.workspace_service import require_case_write

    require_case_write(current_user, case)
    if record.status != "active":
        raise HTTPException(status_code=409, detail="Retome o acompanhamento antes de consultar.")
    key = await reserve_manual_refresh(current_user.tenant_id, record.id)
    try:
        await audit_and_commit(
            db,
            current_user,
            "CONTROLADORIA_MANUAL_REFRESH_REQUESTED",
            "controladoria_monitoring_subscriptions",
            record.id,
            {"case_id": record.case_id},
        )
        from app.services.controladoria_tasks import poll_subscription

        poll_subscription.delay(current_user.tenant_id, record.id)
    except Exception as exc:
        from app.core.redis_cache import cache_manager

        try:
            await cache_manager.redis_client.delete(key)
        except Exception:
            pass
        raise HTTPException(status_code=503, detail="A consulta não pôde ser iniciada. Tente novamente.") from exc
    return {
        "status": "queued",
        "retry_after_seconds": MANUAL_REFRESH_SECONDS,
        "message": "Consulta iniciada. Novas movimentações aparecerão após a conferência da fonte.",
    }


@router.get("/events", response_model=ControladoriaListResponse)
async def list_events(
    case_id: str | None = Query(default=None, max_length=64),
    triage_status: str | None = Query(default=None, pattern="^(pending|reviewed|discarded)$"),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if case_id:
        await get_case(db, current_user, case_id)
    statement = case_scoped_statement(ControladoriaJudicialEvent, current_user)
    if case_id:
        statement = statement.where(ControladoriaJudicialEvent.case_id == case_id)
    if triage_status:
        statement = statement.where(ControladoriaJudicialEvent.triage_status == triage_status)
    records = (
        await db.execute(
            statement.order_by(
                ControladoriaJudicialEvent.occurred_at.desc().nullslast(),
                ControladoriaJudicialEvent.retrieved_at.desc(),
            ).limit(bounded_limit(limit))
        )
    ).scalars().all()
    return ControladoriaListResponse(
        items=[JudicialEventResponse.model_validate(record) for record in records], limit=bounded_limit(limit)
    )


@router.post("/events", response_model=JudicialEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: JudicialEventCreate,
    response: Response,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record, created = await record_judicial_event(db, current_user, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
        return JudicialEventResponse.model_validate(record)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_EVENT_RECORDED",
        "controladoria_judicial_events",
        record.id,
        {"case_id": record.case_id, "source_kind": record.source_kind, "source_event_id": record.source_event_id},
    )
    return JudicialEventResponse.model_validate(record)


@router.post("/events/{event_id}/triage", response_model=JudicialEventResponse)
async def triage_event(
    event_id: str,
    payload: JudicialEventTriage,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await triage_judicial_event(
        db, current_user, event_id, triage_status=payload.status, note=payload.note
    )
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_EVENT_TRIAGED",
        "controladoria_judicial_events",
        record.id,
        {"status": record.triage_status},
    )
    return JudicialEventResponse.model_validate(record)


@router.get("/deadlines", response_model=ControladoriaListResponse)
async def list_deadline_reviews(
    case_id: str | None = Query(default=None, max_length=64),
    status_filter: str | None = Query(
        default=None, alias="status", pattern="^(suggested|first_approved|approved|rejected)$"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if case_id:
        await get_case(db, current_user, case_id)
    statement = case_scoped_statement(ControladoriaDeadlineReview, current_user)
    if case_id:
        statement = statement.where(ControladoriaDeadlineReview.case_id == case_id)
    if status_filter:
        statement = statement.where(ControladoriaDeadlineReview.status == status_filter)
    records = (
        await db.execute(
            statement.order_by(ControladoriaDeadlineReview.suggested_due_at.asc()).limit(bounded_limit(limit))
        )
    ).scalars().all()
    return ControladoriaListResponse(
        items=[await deadline_review_payload(db, current_user, record) for record in records],
        limit=bounded_limit(limit),
    )


@router.get("/deadline-rules", response_model=ControladoriaListResponse)
async def list_deadline_rules(
    status_filter: str | None = Query(
        default="active", alias="status", pattern="^(draft|active|rejected|retired)$"
    ),
    limit: int = Query(default=100, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    statement = select(ControladoriaDeadlineRule).where(
        ControladoriaDeadlineRule.tenant_id == current_user.tenant_id
    )
    if status_filter:
        statement = statement.where(ControladoriaDeadlineRule.status == status_filter)
    records = (
        await db.execute(
            statement.order_by(
                ControladoriaDeadlineRule.rule_key.asc(),
                ControladoriaDeadlineRule.version.desc(),
            ).limit(bounded_limit(limit))
        )
    ).scalars().all()
    return ControladoriaListResponse(
        items=[DeadlineRuleResponse.model_validate(record) for record in records],
        limit=bounded_limit(limit),
    )


@router.post("/deadline-rules", response_model=DeadlineRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: DeadlineRuleCreate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await create_deadline_rule(db, current_user, payload)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_DEADLINE_RULE_CREATED",
        "controladoria_deadline_rules",
        record.id,
        {"rule_key": record.rule_key, "version": record.version, "status": record.status},
    )
    return DeadlineRuleResponse.model_validate(record)


@router.post("/deadline-rules/{rule_id}/review", response_model=DeadlineRuleResponse)
async def review_rule(
    rule_id: str,
    payload: DeadlineRuleReview,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await review_deadline_rule(
        db, current_user, rule_id, decision=payload.decision, note=payload.note
    )
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_DEADLINE_RULE_REVIEWED",
        "controladoria_deadline_rules",
        record.id,
        {"decision": payload.decision, "version": record.version},
    )
    return DeadlineRuleResponse.model_validate(record)


@router.get("/calendar-exceptions", response_model=ControladoriaListResponse)
async def list_calendar_exceptions(
    limit: int = Query(default=100, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    records = (
        await db.execute(
            select(ControladoriaCalendarException)
            .where(ControladoriaCalendarException.tenant_id == current_user.tenant_id)
            .order_by(ControladoriaCalendarException.starts_on.desc())
            .limit(bounded_limit(limit))
        )
    ).scalars().all()
    return ControladoriaListResponse(
        items=[CalendarExceptionResponse.model_validate(record) for record in records],
        limit=bounded_limit(limit),
    )


@router.post(
    "/calendar-exceptions",
    response_model=CalendarExceptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_calendar_exception(
    payload: CalendarExceptionCreate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await create_calendar_exception(db, current_user, payload)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_CALENDAR_EXCEPTION_CREATED",
        "controladoria_calendar_exceptions",
        record.id,
        {
            "scope": f"{record.scope_kind}:{record.scope_code}",
            "kind": record.kind,
            "starts_on": record.starts_on.isoformat(),
            "ends_on": record.ends_on.isoformat(),
        },
    )
    return CalendarExceptionResponse.model_validate(record)


@router.post("/deadlines/calculate", response_model=DeadlineReviewResponse)
async def calculate_deadline(
    payload: DeadlineCalculationCreate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record, created = await calculate_deadline_suggestion(db, current_user, payload)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_DEADLINE_CALCULATED" if created else "CONTROLADORIA_DEADLINE_RECALCULATED",
        "controladoria_deadline_reviews",
        record.id,
        {
            "event_id": record.event_id,
            "rule_id": record.rule_id,
            "rule_version": record.rule_version,
            "calculation_revision": record.calculation_revision,
            "suggested_due_at": record.suggested_due_at.isoformat(),
        },
    )
    return await deadline_review_payload(db, current_user, record)


@router.post("/deadlines", response_model=DeadlineReviewResponse, status_code=status.HTTP_201_CREATED)
async def suggest_deadline(
    payload: DeadlineSuggestionCreate,
    response: Response,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record, created = await create_deadline_suggestion(db, current_user, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
        return await deadline_review_payload(db, current_user, record)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_DEADLINE_SUGGESTED",
        "controladoria_deadline_reviews",
        record.id,
        {"event_id": record.event_id, "suggested_due_at": record.suggested_due_at.isoformat()},
    )
    return await deadline_review_payload(db, current_user, record)


@router.post("/deadlines/{review_id}/decision", response_model=DeadlineReviewResponse)
async def decide_deadline(
    review_id: str,
    payload: DeadlineDecision,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    if payload.decision == "approved":
        record, task = await approve_deadline_and_create_task(
            db,
            current_user,
            review_id,
            note=payload.note,
            expected_calculation_revision=payload.expected_calculation_revision,
        )
        await audit_and_commit(
            db,
            current_user,
            "CONTROLADORIA_DEADLINE_APPROVED" if task else "CONTROLADORIA_DEADLINE_FIRST_APPROVED",
            "controladoria_deadline_reviews",
            record.id,
            (
                {"task_id": task.id, "due_at": task.due_at.isoformat(), "approval_stage": 2}
                if task
                else {"task_id": None, "approval_stage": 1}
            ),
        )
    else:
        record = await reject_deadline_suggestion(
            db,
            current_user,
            review_id,
            note=payload.note,
            expected_calculation_revision=payload.expected_calculation_revision,
        )
        await audit_and_commit(
            db,
            current_user,
            "CONTROLADORIA_DEADLINE_REJECTED",
            "controladoria_deadline_reviews",
            record.id,
            {},
        )
    return await deadline_review_payload(db, current_user, record)


@router.get("/workflow-templates", response_model=ControladoriaListResponse)
async def list_workflow_templates(
    case_type: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    records = (
        await db.execute(
            select(ControladoriaWorkflowTemplate)
            .where(
                ControladoriaWorkflowTemplate.tenant_id == current_user.tenant_id,
                ControladoriaWorkflowTemplate.is_active.is_(True),
                *(
                    (ControladoriaWorkflowTemplate.case_type == case_type,)
                    if case_type
                    else ()
                ),
            )
            .order_by(ControladoriaWorkflowTemplate.name.asc(), ControladoriaWorkflowTemplate.version.desc())
            .limit(bounded_limit(limit))
        )
    ).scalars().all()
    return ControladoriaListResponse(
        items=[await workflow_template_payload(db, current_user, record) for record in records],
        limit=bounded_limit(limit),
    )


@router.get("/workflow-templates/{template_id}", response_model=WorkflowTemplateResponse)
async def get_workflow_template_detail(
    template_id: str,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    template = await get_workflow_template(db, current_user, template_id)
    return await workflow_template_payload(db, current_user, template)


@router.post("/workflow-templates", response_model=WorkflowTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: WorkflowTemplateCreate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    template = await create_workflow_template(db, current_user, payload)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_WORKFLOW_TEMPLATE_CREATED",
        "controladoria_workflow_templates",
        template.id,
        {"version": template.version, "step_count": len(payload.steps)},
    )
    return await workflow_template_payload(db, current_user, template)


@router.get("/workflows", response_model=ControladoriaListResponse)
async def list_workflow_runs(
    case_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if case_id:
        await get_case(db, current_user, case_id)
    statement = case_scoped_statement(ControladoriaWorkflowRun, current_user)
    if case_id:
        statement = statement.where(ControladoriaWorkflowRun.case_id == case_id)
    records = (
        await db.execute(statement.order_by(ControladoriaWorkflowRun.updated_at.desc()).limit(bounded_limit(limit)))
    ).scalars().all()
    return ControladoriaListResponse(
        items=[await workflow_run_payload(db, current_user, record) for record in records],
        limit=bounded_limit(limit),
    )


@router.post("/workflows", response_model=WorkflowRunResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_run(
    payload: WorkflowRunCreate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await start_workflow_run(db, current_user, payload)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_WORKFLOW_STARTED",
        "controladoria_workflow_runs",
        record.id,
        {"case_id": record.case_id, "template_id": record.template_id},
    )
    return await workflow_run_payload(db, current_user, record)


@router.get("/workflows/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run_detail(
    run_id: str,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    run = await get_workflow_run(db, current_user, run_id)
    return await workflow_run_payload(db, current_user, run)


@router.post("/workflows/{run_id}/items/{item_id}", response_model=WorkflowRunItemResponse)
async def resolve_workflow_item(
    run_id: str,
    item_id: str,
    payload: WorkflowRunItemUpdate,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await resolve_workflow_run_item(db, current_user, run_id, item_id, payload)
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_WORKFLOW_ITEM_RESOLVED",
        "controladoria_workflow_run_items",
        record.id,
        {"workflow_run_id": run_id, "status": record.status},
    )
    return WorkflowRunItemResponse.model_validate(record)


@router.post("/workflows/{run_id}/complete", response_model=WorkflowRunResponse)
async def complete_workflow(
    run_id: str,
    payload: WorkflowRunComplete,
    *,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await complete_workflow_run(
        db, current_user, run_id, expected_revision=payload.expected_revision
    )
    await audit_and_commit(
        db,
        current_user,
        "CONTROLADORIA_WORKFLOW_COMPLETED",
        "controladoria_workflow_runs",
        record.id,
        {},
    )
    return await workflow_run_payload(db, current_user, record)
    create_calendar_exception,
    create_deadline_rule,
    get_deadline_rule,
    review_deadline_rule,
