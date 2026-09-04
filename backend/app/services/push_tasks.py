"""At-least-once job publication, durable claims, conservative external delivery status."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.push import PushDelivery, PushSubscription
from app.services.push_provider import send_push
from app.services.push_service import decrypt_subscription, delivery_is_authorized, revoke_subscription


logger = logging.getLogger(__name__)
PROCESSING_TIMEOUT = 120


async def _set_tenant(db, tenant_id):
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT set_config('app.current_tenant', :tenant_id, true)"), {"tenant_id": tenant_id})


async def _claim_delivery(delivery_id, tenant_id):
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_tenant(db, tenant_id)
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.tenant_id == tenant_id, PushDelivery.id == delivery_id))
            if not delivery:
                return "ignored", None
            # Match the unsubscribe lock order: subscription, then its outbox rows.
            subscription = await db.scalar(select(PushSubscription).where(PushSubscription.id == delivery.subscription_id,
                PushSubscription.tenant_id == tenant_id, PushSubscription.user_id == delivery.user_id).with_for_update())
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.tenant_id == tenant_id, PushDelivery.id == delivery_id).with_for_update().execution_options(populate_existing=True))
            now = datetime.now(timezone.utc)
            if delivery.status == "processing":
                if delivery.processing_started_at and delivery.processing_started_at > now - timedelta(seconds=PROCESSING_TIMEOUT):
                    return "busy", None
                delivery.status = "unknown"
                delivery.error_code = "worker_outcome_unknown"
                delivery.processing_started_at = None
                return "unknown", None
            if delivery.status != "queued":
                return "ignored", None
            if delivery.expires_at <= now:
                delivery.status, delivery.error_code = "expired", "event_expired"
                return "expired", None
            if delivery.next_attempt_at and delivery.next_attempt_at > now:
                return "busy", None
            if not settings.WEB_PUSH_ENABLED:
                delivery.next_attempt_at = now + timedelta(minutes=1)
                return "blocked", None
            if not subscription or not await delivery_is_authorized(db, delivery, subscription):
                delivery.status, delivery.error_code = "cancelled", "authority_revoked"
                return "cancelled", None
            if delivery.attempts >= 3:
                delivery.status, delivery.error_code = "failed", "attempt_limit"
                return "failed", None
            try:
                credentials = decrypt_subscription(subscription.credentials_encrypted)
            except (ValueError, RuntimeError):
                delivery.status, delivery.error_code = "failed", "invalid_stored_subscription"
                return "failed", None
            delivery.status = "processing"
            delivery.attempts += 1
            delivery.processing_started_at = now
            delivery.next_attempt_at = None
            delivery.error_code = None
            return "claimed", (credentials, delivery.attempts, max(0, int((delivery.expires_at - now).total_seconds())))


async def _process_delivery(delivery_id, tenant_id):
    status, claim = await _claim_delivery(delivery_id, tenant_id)
    if status != "claimed":
        return status
    credentials, claimed_attempt, ttl = claim
    # The database transaction is closed before any external network request.
    result = send_push(credentials, delivery_id, ttl=ttl)
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_tenant(db, tenant_id)
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.tenant_id == tenant_id, PushDelivery.id == delivery_id))
            if not delivery:
                return "ignored"
            subscription = await db.scalar(select(PushSubscription).where(PushSubscription.tenant_id == tenant_id, PushSubscription.id == delivery.subscription_id).with_for_update())
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.tenant_id == tenant_id, PushDelivery.id == delivery_id).with_for_update().execution_options(populate_existing=True))
            if not delivery or delivery.status != "processing" or delivery.attempts != claimed_attempt:
                return "ignored"
            status = result.status
            if result.retryable:
                status = "queued" if claimed_attempt < 3 else "failed"
            delivery.status = status
            delivery.error_code = result.error_code
            delivery.processing_started_at = None
            delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=60 * 2 ** (claimed_attempt - 1)) if status == "queued" else None
            if status == "accepted":
                delivery.accepted_at = datetime.now(timezone.utc)
            if status == "expired":
                if subscription:
                    await revoke_subscription(db, subscription)
            return status


async def _isolated_process(delivery_id, tenant_id):
    try:
        return await _process_delivery(delivery_id, tenant_id)
    finally:
        # Celery enters with asyncio.run; pooled connections cannot cross event loops.
        await engine.dispose()


@celery_app.task(name="push.process_delivery", acks_late=True, reject_on_worker_lost=True, soft_time_limit=45, time_limit=60)
def process_push_delivery(delivery_id: str, tenant_id: str):
    try:
        return {"status": asyncio.run(_isolated_process(delivery_id, tenant_id))}
    except Exception:
        # Recovery changes a stale claim to unknown; do not resend an ambiguous request.
        # Never serialize provider exceptions, which can include credentials/endpoint URLs.
        logger.warning("Push job interrupted; durable recovery will reconcile its claim")
        return {"status": "unknown"}


async def _candidates():
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                rows = await db.execute(text("SELECT delivery_id, tenant_id FROM push_recovery_candidates(:limit, :timeout)"), {"limit": 100, "timeout": PROCESSING_TIMEOUT})
                return [(row.delivery_id, row.tenant_id) for row in rows]
    finally:
        await engine.dispose()


async def _heartbeat():
    import redis.asyncio as aioredis
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.set("legaltech:push:recovery-heartbeat", str(int(datetime.now(timezone.utc).timestamp())), ex=180)
    finally:
        await client.aclose()


@celery_app.task(name="push.dispatch_pending")
def dispatch_pending_push():
    candidates = asyncio.run(_candidates())
    published = 0
    for delivery_id, tenant_id in candidates:
        try:
            process_push_delivery.delay(delivery_id, tenant_id)
            published += 1
        except Exception:
            logger.warning("Push publication deferred; durable outbox retained")
    asyncio.run(_heartbeat())
    return {"candidates": len(candidates), "published": published}
