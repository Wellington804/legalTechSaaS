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
from app.services.controladoria_provider import JudicialProviderError, monitoring_provider
from app.services.controladoria_service import record_judicial_event
from app.services.push_service import enqueue_user_push


logger = logging.getLogger(__name__)


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

    provider = monitoring_provider(snapshot["source_kind"], settings)
    events = await provider.fetch(
        tribunal=snapshot["tribunal"], process_number=snapshot["process_number"]
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
        for source_event in events:
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
