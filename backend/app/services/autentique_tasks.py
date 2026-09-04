"""Durable asynchronous finalization for Autentique signed artifacts."""

import asyncio
import logging
import uuid

from sqlalchemy import text

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.services.operations import finalize_queued_autentique_event
from app.services.provider_costs import record_provider_usage


logger = logging.getLogger(__name__)


async def _process(event_id: str, tenant_id: str) -> str:
    try:
        async with AsyncSessionLocal() as db:
            await _set_tenant_context(db, tenant_id)
            usage_attempt = str(uuid.uuid4())
            result = await finalize_queued_autentique_event(db, tenant_id=tenant_id, event_id=event_id)
            if result in {"finalized", "provider_deferred", "validation_failed", "validation_deferred"}:
                await record_provider_usage(
                    db,
                    tenant_id=tenant_id,
                    provider="autentique",
                    metric="document_query",
                    idempotency_key=f"event:{event_id}:attempt:{usage_attempt}",
                )
            await db.commit()
            return result
    finally:
        await engine.dispose()


@celery_app.task(
    name="autentique.process_signature_event",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=50,
    time_limit=60,
)
def process_autentique_signature_event(event_id: str, tenant_id: str):
    try:
        return {"status": asyncio.run(_process(event_id, tenant_id))}
    except Exception:
        logger.warning("Autentique artifact finalization deferred")
        return {"status": "deferred"}


async def _candidates() -> list[tuple[str, str]]:
    try:
        async with AsyncSessionLocal() as db:
            rows = await db.execute(text("SELECT * FROM public.autentique_signature_event_candidates(:limit)"), {"limit": 200})
            return [(row.event_id, row.tenant_id) for row in rows]
    finally:
        await engine.dispose()


@celery_app.task(name="autentique.reconcile_signed_artifacts")
def reconcile_autentique_signed_artifacts():
    candidates = asyncio.run(_candidates())
    published = 0
    for event_id, tenant_id in candidates:
        try:
            process_autentique_signature_event.delay(event_id, tenant_id)
            published += 1
        except Exception:
            logger.warning("Autentique event publication deferred")
    return {"candidates": len(candidates), "published": published}
