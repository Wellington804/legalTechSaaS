"""Celery entrypoints for webhook-triggered and periodic reconciliation."""

import asyncio
import logging

from sqlalchemy import select, text

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.models.external_integrations import CalendarConnection
from app.services.calendar_sync import renew_watch_if_needed, synchronize_connection


logger = logging.getLogger(__name__)


async def _process(connection_id: str, tenant_id: str) -> dict:
    try:
        async with AsyncSessionLocal() as db:
            await _set_tenant_context(db, tenant_id)
            connection = await db.scalar(
                select(CalendarConnection).where(
                    CalendarConnection.tenant_id == tenant_id,
                    CalendarConnection.id == connection_id,
                )
            )
            if not connection:
                return {"status": "ignored"}
            await renew_watch_if_needed(db, connection)
            result = await synchronize_connection(db, tenant_id, connection_id)
            return {"status": "synchronized", **result}
    finally:
        await engine.dispose()


@celery_app.task(
    name="calendar.process_connection",
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=90,
    time_limit=120,
)
def process_calendar_connection(connection_id: str, tenant_id: str):
    try:
        return asyncio.run(_process(connection_id, tenant_id))
    except Exception:
        logger.warning("Calendar reconciliation failed; periodic reconciliation will retry")
        return {"status": "deferred"}


async def _candidates() -> list[tuple[str, str]]:
    try:
        async with AsyncSessionLocal() as db:
            rows = await db.execute(text("SELECT * FROM public.calendar_reconciliation_candidates(:limit)"), {"limit": 200})
            return [(row.connection_id, row.tenant_id) for row in rows]
    finally:
        await engine.dispose()


@celery_app.task(name="calendar.reconcile_active")
def reconcile_active_calendars():
    candidates = asyncio.run(_candidates())
    published = 0
    for connection_id, tenant_id in candidates:
        try:
            process_calendar_connection.delay(connection_id, tenant_id)
            published += 1
        except Exception:
            logger.warning("Calendar job publication deferred")
    return {"candidates": len(candidates), "published": published}
