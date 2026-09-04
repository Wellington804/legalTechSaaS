"""Bounded polling of configured judicial subscriptions; no deadline is derived here."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.models.controladoria import ControladoriaMonitoringSubscription
from app.models.user import User
from app.models.workspace import WorkspaceCase
from app.schemas.controladoria import JudicialEventCreate
from app.services.audit_service import AuditService
from app.services.controladoria_provider import (
    EscavadorMonitoringProvider,
    JudicialProviderError,
    ProviderFetchPage,
    monitoring_provider,
    parse_escavador_callback,
)
from app.services.controladoria_service import record_judicial_event
from app.services.push_service import enqueue_user_push


logger = logging.getLogger(__name__)
MAX_DJEN_PAGES_PER_POLL = 100


async def _fetch_with_backoff(provider, *, tribunal: str, process_number: str, cursor: str | None) -> ProviderFetchPage:
    """Bounded provider retry; recurring beat remains the longer recovery path."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return await provider.fetch_page(
                tribunal=tribunal,
                process_number=process_number,
                cursor=cursor,
            )
        except JudicialProviderError as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    raise JudicialProviderError("fonte judicial indisponivel apos novas tentativas") from last_error


async def _fetch_subscription_snapshot(
    provider,
    *,
    source_kind: str,
    tribunal: str,
    process_number: str,
    cursor: str | None,
) -> ProviderFetchPage:
    if source_kind != "djen":
        return await _fetch_with_backoff(
            provider, tribunal=tribunal, process_number=process_number, cursor=cursor
        )
    events = []
    next_cursor = None
    seen_cursors: set[str] = set()
    for _ in range(MAX_DJEN_PAGES_PER_POLL):
        page = await _fetch_with_backoff(
            provider,
            tribunal=tribunal,
            process_number=process_number,
            cursor=next_cursor,
        )
        events.extend(page.events)
        if page.next_cursor is None:
            return ProviderFetchPage(events=events, next_cursor=None)
        if page.next_cursor in seen_cursors:
            raise JudicialProviderError("paginacao DJEN repetida")
        seen_cursors.add(page.next_cursor)
        next_cursor = page.next_cursor
    raise JudicialProviderError("consulta DJEN excedeu o limite oficial de 10.000 resultados")


async def _mark_failed(tenant_id: str, subscription_id: str, code: str) -> None:
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        subscription = await db.scalar(
            select(ControladoriaMonitoringSubscription).where(
                ControladoriaMonitoringSubscription.id == subscription_id,
                ControladoriaMonitoringSubscription.tenant_id == tenant_id,
            ).with_for_update()
        )
        if subscription:
            subscription.last_checked_at = datetime.now(timezone.utc)
            subscription.last_error_code = code


async def _poll_subscription(tenant_id: str, subscription_id: str) -> dict:
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        snapshot = (await db.execute(
            select(
                ControladoriaMonitoringSubscription.source_kind,
                ControladoriaMonitoringSubscription.provider_subscription_id,
                ControladoriaMonitoringSubscription.provider_cursor,
                ControladoriaMonitoringSubscription.tribunal,
                ControladoriaMonitoringSubscription.process_number,
                WorkspaceCase.responsible_user_id,
            ).join(
                WorkspaceCase,
                (WorkspaceCase.id == ControladoriaMonitoringSubscription.case_id)
                & (WorkspaceCase.tenant_id == ControladoriaMonitoringSubscription.tenant_id),
            ).where(
                ControladoriaMonitoringSubscription.id == subscription_id,
                ControladoriaMonitoringSubscription.tenant_id == tenant_id,
                ControladoriaMonitoringSubscription.status == "active",
            )
        )).mappings().one_or_none()
    if not snapshot:
        return {"status": "ignored", "imported": 0}

    provider = monitoring_provider(snapshot["source_kind"], settings, tribunal=snapshot["tribunal"])
    if isinstance(provider, EscavadorMonitoringProvider) and not snapshot["provider_subscription_id"]:
        provider_subscription_id = await provider.ensure_monitor(
            tribunal=snapshot["tribunal"], process_number=snapshot["process_number"]
        )
        async with AsyncSessionLocal() as db, db.begin():
            await _set_tenant_context(db, tenant_id)
            subscription = await db.scalar(select(ControladoriaMonitoringSubscription).where(
                ControladoriaMonitoringSubscription.id == subscription_id,
                ControladoriaMonitoringSubscription.tenant_id == tenant_id,
                ControladoriaMonitoringSubscription.status == "active",
            ).with_for_update())
            if not subscription:
                return {"status": "ignored", "imported": 0}
            if not subscription.provider_subscription_id:
                subscription.provider_subscription_id = provider_subscription_id
    page = await _fetch_subscription_snapshot(
        provider,
        source_kind=snapshot["source_kind"],
        tribunal=snapshot["tribunal"],
        process_number=snapshot["process_number"],
        cursor=snapshot["provider_cursor"],
    )
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        user = await db.scalar(select(User).where(
            User.id == snapshot["responsible_user_id"],
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        ))
        subscription = await db.scalar(select(ControladoriaMonitoringSubscription).where(
            ControladoriaMonitoringSubscription.id == subscription_id,
            ControladoriaMonitoringSubscription.tenant_id == tenant_id,
            ControladoriaMonitoringSubscription.status == "active",
        ).with_for_update())
        if not user or not subscription:
            raise JudicialProviderError("assinatura sem responsavel ativo")

        imported = 0
        for source_event in page.events:
            event, created = await record_judicial_event(
                db,
                user,
                JudicialEventCreate(
                    case_id=subscription.case_id,
                    subscription_id=subscription.id,
                    source_kind=snapshot["source_kind"],
                    source_event_id=source_event.source_event_id,
                    source_url=source_event.source_url,
                    title=source_event.title,
                    source_content=source_event.source_content,
                    source_metadata=source_event.source_metadata,
                    occurred_at=source_event.occurred_at,
                    retrieved_at=source_event.retrieved_at,
                ),
            )
            if created:
                imported += 1
                await enqueue_user_push(
                    db,
                    tenant_id=tenant_id,
                    user_id=user.id,
                    event_key=event.id,
                    kind="judicial_movement",
                    case_id=subscription.case_id,
                )
        now = datetime.now(timezone.utc)
        subscription.last_checked_at = now
        subscription.last_success_at = now
        subscription.last_error_code = None
        subscription.provider_cursor = page.next_cursor
        if imported:
            await AuditService.log_action(
                db,
                tenant_id,
                user.id,
                "CONTROLADORIA_EVENTS_IMPORTED",
                "controladoria_monitoring_subscriptions",
                subscription.id,
                {"imported": imported},
            )
    return {"status": "ok", "imported": imported}


async def _ingest_escavador_callback(payload: dict) -> dict:
    delivery = parse_escavador_callback(payload)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            text(
                "SELECT * FROM controladoria_escavador_webhook_targets("
                ":process_number, :provider_subscription_id)"
            ),
            {
                "process_number": delivery.process_number,
                "provider_subscription_id": delivery.provider_subscription_id,
            },
        )).all()

    imported = 0
    matched = 0
    for row in rows:
        async with AsyncSessionLocal() as db, db.begin():
            await _set_tenant_context(db, row.tenant_id)
            snapshot = (await db.execute(
                select(
                    ControladoriaMonitoringSubscription,
                    WorkspaceCase.responsible_user_id,
                ).join(
                    WorkspaceCase,
                    (WorkspaceCase.id == ControladoriaMonitoringSubscription.case_id)
                    & (WorkspaceCase.tenant_id == ControladoriaMonitoringSubscription.tenant_id),
                ).where(
                    ControladoriaMonitoringSubscription.id == row.subscription_id,
                    ControladoriaMonitoringSubscription.tenant_id == row.tenant_id,
                    ControladoriaMonitoringSubscription.source_kind == "escavador",
                    ControladoriaMonitoringSubscription.status == "active",
                    ControladoriaMonitoringSubscription.process_number == delivery.process_number,
                ).with_for_update()
            )).one_or_none()
            if not snapshot:
                continue
            subscription, responsible_user_id = snapshot
            user = await db.scalar(select(User).where(
                User.id == responsible_user_id,
                User.tenant_id == row.tenant_id,
                User.is_active.is_(True),
            ))
            if not user:
                raise JudicialProviderError("assinatura sem responsavel ativo")
            if not subscription.provider_subscription_id:
                subscription.provider_subscription_id = delivery.provider_subscription_id

            event, created = await record_judicial_event(
                db,
                user,
                JudicialEventCreate(
                    case_id=subscription.case_id,
                    subscription_id=subscription.id,
                    source_kind="escavador",
                    source_event_id=delivery.event.source_event_id,
                    source_url=delivery.event.source_url,
                    title=delivery.event.title,
                    source_content=delivery.event.source_content,
                    source_metadata=delivery.event.source_metadata,
                    occurred_at=delivery.event.occurred_at,
                    retrieved_at=delivery.event.retrieved_at,
                ),
            )
            matched += 1
            now = datetime.now(timezone.utc)
            subscription.last_checked_at = now
            subscription.last_success_at = now
            subscription.last_error_code = None
            if created:
                imported += 1
                await enqueue_user_push(
                    db,
                    tenant_id=row.tenant_id,
                    user_id=user.id,
                    event_key=event.id,
                    kind="judicial_movement",
                    case_id=subscription.case_id,
                )
                await AuditService.log_action(
                    db,
                    row.tenant_id,
                    user.id,
                    "CONTROLADORIA_EVENTS_IMPORTED",
                    "controladoria_monitoring_subscriptions",
                    subscription.id,
                    {"imported": 1, "ingestion_method": "callback"},
                )
    return {"status": "ok", "matched": matched, "imported": imported}


async def _poll_subscription_safely(tenant_id: str, subscription_id: str) -> dict:
    try:
        return await _poll_subscription(tenant_id, subscription_id)
    except Exception:
        logger.warning("Judicial monitoring deferred; no legal deadline was created")
        await _mark_failed(tenant_id, subscription_id, "provider_or_account_unavailable")
        return {"status": "failed", "imported": 0}


async def _poll_controladoria():
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(text("SELECT * FROM controladoria_monitoring_candidates(50)"))).all()
        result = {"status": "ok", "checked": 0, "imported": 0, "failed": 0}
        for row in rows:
            result["checked"] += 1
            outcome = await _poll_subscription_safely(row.tenant_id, row.subscription_id)
            result["imported"] += outcome["imported"]
            if outcome["status"] == "failed":
                result["failed"] += 1
        return result
    finally:
        await engine.dispose()


@celery_app.task(name="controladoria.poll_datajud", soft_time_limit=240, time_limit=270)
def poll_datajud():
    return asyncio.run(_poll_controladoria())


@celery_app.task(name="controladoria.poll_subscription", soft_time_limit=45, time_limit=60)
def poll_subscription(tenant_id: str, subscription_id: str):
    try:
        return asyncio.run(_poll_subscription_safely(tenant_id, subscription_id))
    finally:
        asyncio.run(engine.dispose())


@celery_app.task(
    name="controladoria.ingest_escavador_callback",
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 5},
    soft_time_limit=45,
    time_limit=60,
)
def ingest_escavador_callback(payload: dict):
    try:
        return asyncio.run(_ingest_escavador_callback(payload))
    finally:
        asyncio.run(engine.dispose())
