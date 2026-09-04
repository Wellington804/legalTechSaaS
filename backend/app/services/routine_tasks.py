"""Beat polls durable reminders; errors preserve scheduled state for the next poll."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.services.routine_service import dispatch_reminder

logger = logging.getLogger(__name__)


async def _heartbeat():
    import redis.asyncio as aioredis
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.set("legaltech:routines:recovery-heartbeat", str(int(datetime.now(timezone.utc).timestamp())), ex=180)
    finally:
        await client.aclose()


async def _dispatch_reminders():
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(text("SELECT reminder_id, tenant_id FROM routine_reminder_candidates(100)"))).all()
        results = {"due": 0, "cancelled": 0, "ignored": 0, "deferred": 0}
        for row in rows:
            try:
                async with AsyncSessionLocal() as db:
                    async with db.begin():
                        await _set_tenant_context(db, row.tenant_id)
                        status = await dispatch_reminder(db, row.reminder_id, row.tenant_id)
                        results[status] += 1
            except Exception:
                # Never log task titles, case identifiers or provider credentials.
                logger.warning("Reminder dispatch deferred; durable schedule retained")
                results["deferred"] += 1
        if not results["deferred"]:
            await _heartbeat()
        return results
    finally:
        await engine.dispose()


@celery_app.task(name="routines.dispatch_reminders", soft_time_limit=90, time_limit=120)
def dispatch_reminders():
    return asyncio.run(_dispatch_reminders())
