import hashlib
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from app.core.celery_app import celery_app

logger = logging.getLogger("celery_tasks")
NOTIFICATION_RECOVERY_HEARTBEAT_KEY = "legaltech:notifications:recovery-heartbeat"


def _retry_delay(attempts: int) -> int:
    from app.core.config import settings

    return min(
        int(getattr(settings, "NOTIFICATION_RETRY_DELAY_SECONDS", 60)),
        2 ** min(attempts, 10),
    )


async def _set_tenant(db, tenant_id: str) -> None:
    from sqlalchemy import text

    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )


async def _delivery_context(delivery_id: str, tenant_id: str) -> dict:
    """Load case-bound content after claiming, never while an outbound call is pending."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.notification import NotificationDelivery

    try:
        from app.services.engagement_service import delivery_context
    except ModuleNotFoundError as exc:
        if exc.name != "app.services.engagement_service":
            raise
        return {}

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_tenant(db, tenant_id)
            delivery = (
                await db.execute(
                    select(NotificationDelivery).where(
                        NotificationDelivery.id == delivery_id,
                        NotificationDelivery.tenant_id == tenant_id,
                    )
                )
            ).scalars().first()
            return await delivery_context(db, delivery) if delivery else {}


async def _claim_notification(delivery_id: str, tenant_id: str):
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    # Load FK targets for SQLAlchemy's standalone Celery mapper registry.
    from app.models.tenant import Tenant  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.notification import NotificationDelivery
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_tenant(db, tenant_id)
            delivery = (
                await db.execute(
                    select(NotificationDelivery)
                    .where(
                        NotificationDelivery.id == delivery_id,
                        NotificationDelivery.tenant_id == tenant_id,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if not delivery:
                return "ignored", None

            now = datetime.now(timezone.utc)
            processing_timeout = timedelta(
                seconds=int(getattr(settings, "NOTIFICATION_PROCESSING_TIMEOUT_SECONDS", 900))
            )
            max_attempts = int(getattr(settings, "NOTIFICATION_MAX_DELIVERY_ATTEMPTS", 5))
            if delivery.status == "processing":
                started_at = delivery.processing_started_at
                if started_at and started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                if started_at and now - started_at < processing_timeout:
                    return "busy", None
                if delivery.channel == "whatsapp":
                    # Evolution has no idempotency contract: never resend ambiguity.
                    delivery.status = "unknown"
                    delivery.error_code = "worker_outcome_unknown"
                    delivery.processing_started_at = None
                    return "unknown", None
                from app.services.notification_service import resend_retry_window_open

                provider_attempted_at = delivery.provider_attempted_at or started_at
                if not resend_retry_window_open(provider_attempted_at, now=now):
                    delivery.status = "unknown"
                    delivery.error_code = "email_idempotency_window_expired"
                    delivery.processing_started_at = None
                    return "unknown", None
            elif delivery.status == "queued":
                if delivery.next_attempt_at and delivery.next_attempt_at > now:
                    return "busy", None
            else:
                return "ignored", None

            if delivery.attempts >= max_attempts:
                delivery.status = "unknown" if delivery.provider_attempted_at else "failed"
                delivery.error_code = "delivery_attempt_limit_reached"
                delivery.processing_started_at = None
                return delivery.status, None

            from app.services.notification_providers import provider_is_configured

            if not provider_is_configured(delivery.channel):
                # Preserve durable work for Beat after an operator enables the provider.
                delivery.status = "queued"
                delivery.error_code = "provider_disabled"
                delivery.next_attempt_at = now + timedelta(
                    seconds=int(getattr(settings, "NOTIFICATION_RETRY_DELAY_SECONDS", 60))
                )
                return "blocked", None

            delivery.status = "processing"
            delivery.processing_started_at = now
            delivery.next_attempt_at = None
            delivery.attempts += 1
            delivery.error_code = None
            if delivery.channel == "email" and delivery.provider_attempted_at is None:
                delivery.provider_attempted_at = now
            return "claimed", (delivery.channel, delivery.recipient, delivery.attempts)


async def _process_notification(delivery_id: str, tenant_id: str, can_retry: bool) -> str:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.notification import NotificationDelivery
    from app.services.notification_providers import send_evolution, send_resend

    claim_status, claim = await _claim_notification(delivery_id, tenant_id)
    if claim_status != "claimed":
        return claim_status

    channel, recipient, claimed_attempt = claim
    context = await _delivery_context(delivery_id, tenant_id)
    if context is None:
        from app.core.config import settings

        if settings.is_hardened_environment and not settings.UNBOUND_NOTIFICATION_DISPATCH_ENABLED:
            await _block_unbound_notification(delivery_id, tenant_id, claimed_attempt)
            return "blocked"
        context = {}

    if channel == "email":
        # Resend deduplicates the delivery id for 24 hours.
        result = await send_resend(
            delivery_id,
            recipient,
            text=context.get("text") if context else None,
            subject=context.get("subject") if context else None,
        )
    else:
        result = await send_evolution(
            recipient,
            text=context.get("text") if context else None,
            instance_id=context.get("evolution_instance_id") if context else None,
            api_key=context.get("evolution_api_key") if context else None,
        )

    async with AsyncSessionLocal() as db:
        async with db.begin():
            from app.core.config import settings

            await _set_tenant(db, tenant_id)
            delivery = (
                await db.execute(
                    select(NotificationDelivery)
                    .where(
                        NotificationDelivery.id == delivery_id,
                        NotificationDelivery.tenant_id == tenant_id,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if not delivery or delivery.attempts != claimed_attempt:
                return "ignored"
            if delivery.status != "processing" and not (
                channel == "whatsapp"
                and delivery.status == "unknown"
                and delivery.error_code == "worker_outcome_unknown"
            ):
                return "ignored"
            final_status = result.status
            if result.retryable:
                if delivery.attempts >= int(
                    getattr(settings, "NOTIFICATION_MAX_DELIVERY_ATTEMPTS", 5)
                ):
                    final_status = "unknown"
                else:
                    final_status = "queued"
            delivery.status = final_status
            delivery.provider_message_id = result.message_id
            delivery.error_code = result.error_code
            delivery.processing_started_at = None
            delivery.next_attempt_at = (
                datetime.now(timezone.utc) + timedelta(seconds=_retry_delay(delivery.attempts))
                if final_status == "queued"
                else None
            )
            if final_status == "sent":
                delivery.sent_at = datetime.now(timezone.utc)
            if result.message_id:
                from app.services.notification_service import reconcile_provider_receipts

                await reconcile_provider_receipts(db, delivery)
            return "retry" if final_status == "queued" and can_retry else final_status


async def _block_unbound_notification(
    delivery_id: str, tenant_id: str, claimed_attempt: int
) -> None:
    """Do not let a legacy, unbound outbox row bypass the production API gate."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.notification import NotificationDelivery

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_tenant(db, tenant_id)
            delivery = (
                await db.execute(
                    select(NotificationDelivery)
                    .where(
                        NotificationDelivery.id == delivery_id,
                        NotificationDelivery.tenant_id == tenant_id,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if delivery and delivery.status == "processing" and delivery.attempts == claimed_attempt:
                delivery.status = "failed"
                delivery.error_code = "unbound_resource_blocked"
                delivery.processing_started_at = None
                delivery.next_attempt_at = None


async def _process_notification_isolated(delivery_id: str, tenant_id: str, can_retry: bool) -> str:
    from app.core.database import engine

    try:
        return await _process_notification(delivery_id, tenant_id, can_retry)
    finally:
        # ponytail: Celery is synchronous; dispose per task to avoid reusing asyncpg
        # connections across the separate event loops created by asyncio.run().
        await engine.dispose()


async def _mark_unhandled_notification(delivery_id: str, tenant_id: str) -> None:
    from sqlalchemy import select

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.notification import NotificationDelivery
    from app.models.tenant import Tenant  # noqa: F401
    from app.models.user import User  # noqa: F401

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await _set_tenant(db, tenant_id)
            delivery = (
                await db.execute(
                    select(NotificationDelivery)
                    .where(
                        NotificationDelivery.id == delivery_id,
                        NotificationDelivery.tenant_id == tenant_id,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if delivery and delivery.status == "processing":
                from app.services.notification_service import resend_retry_window_open

                if (
                    delivery.channel == "email"
                    and delivery.attempts < int(
                        getattr(settings, "NOTIFICATION_MAX_DELIVERY_ATTEMPTS", 5)
                    )
                    and resend_retry_window_open(delivery.provider_attempted_at)
                ):
                    delivery.status = "queued"
                    delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                        seconds=_retry_delay(delivery.attempts)
                    )
                else:
                    delivery.status = "unknown"
                    delivery.next_attempt_at = None
                delivery.error_code = "worker_exception"
                delivery.processing_started_at = None


async def _mark_unhandled_notification_isolated(delivery_id: str, tenant_id: str) -> None:
    from app.core.database import engine

    try:
        await _mark_unhandled_notification(delivery_id, tenant_id)
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="tasks.process_notification",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=4,
)
def process_notification_task(self, delivery_id: str, tenant_id: str):
    try:
        result = asyncio.run(
            _process_notification_isolated(
                delivery_id, tenant_id, self.request.retries < self.max_retries
            )
        )
    except Exception as exc:
        try:
            asyncio.run(_mark_unhandled_notification_isolated(delivery_id, tenant_id))
        except Exception:
            logger.exception("Unable to finalize failed notification %s", delivery_id)
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc, countdown=_retry_delay(self.request.retries + 1)
            )
        raise
    if result == "retry":
        raise self.retry(countdown=_retry_delay(self.request.retries + 1))
    return {"delivery_id": delivery_id, "status": result}


async def _notification_recovery_candidates() -> list[tuple[str, str]]:
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        async with db.begin():
            rows = await db.execute(
                text(
                    "SELECT delivery_id, tenant_id "
                    "FROM notification_recovery_candidates(:batch_size, :timeout_seconds)"
                ),
                {
                    "batch_size": int(
                        getattr(settings, "NOTIFICATION_RECONCILE_BATCH_SIZE", 100)
                    ),
                    "timeout_seconds": int(
                        getattr(settings, "NOTIFICATION_PROCESSING_TIMEOUT_SECONDS", 900)
                    ),
                },
            )
            return [(row.delivery_id, row.tenant_id) for row in rows]


async def _notification_recovery_candidates_isolated() -> list[tuple[str, str]]:
    from app.core.database import engine

    try:
        return await _notification_recovery_candidates()
    finally:
        # Beat also enters through asyncio.run(), so it must not retain asyncpg loops.
        await engine.dispose()


async def _record_notification_recovery_heartbeat() -> None:
    """Emit an aggregate liveness signal after Beat work reaches a worker."""
    import redis.asyncio as aioredis

    from app.core.config import settings

    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        # No delivery, tenant, recipient, or provider data is placed in Redis.
        await client.set(
            NOTIFICATION_RECOVERY_HEARTBEAT_KEY,
            str(int(datetime.now(timezone.utc).timestamp())),
            ex=180,
        )
    finally:
        await client.aclose()


@celery_app.task(name="tasks.reconcile_notification_deliveries")
def reconcile_notification_deliveries_task():
    """Republish durable queued/stale work; duplicate publications are harmless claims."""
    candidates = asyncio.run(_notification_recovery_candidates_isolated())
    published = 0
    for delivery_id, tenant_id in candidates:
        try:
            process_notification_task.delay(delivery_id, tenant_id)
            published += 1
        except Exception:
            logger.exception("Unable to publish recovered notification %s", delivery_id)
    # A new heartbeat requires both Beat publication and successful worker execution.
    asyncio.run(_record_notification_recovery_heartbeat())
    return {"candidates": len(candidates), "published": published}

@celery_app.task(name="tasks.generate_audit_hash")
def generate_audit_hash_task(tenant_id: str, user_id: str, action: str, resource_type: str, details: dict):
    """
    Calcula o hash de auditoria em background para garantir imutabilidade sem travar o worker HTTP.
    """
    timestamp_str = datetime.now(timezone.utc).isoformat()
    payload = f"{tenant_id}:{user_id}:{action}:{resource_type}:{timestamp_str}:{json.dumps(details or {})}"
    sha256_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    logger.info(f"[Celery Audit] Log processado para Tenant {tenant_id} - Hash: {sha256_hash[:16]}...")
    return {
        "tenant_id": tenant_id,
        "action": action,
        "hash": f"sha256-{sha256_hash}",
        "processed_at": timestamp_str
    }


async def _purge_expired_ai_conversations() -> int:
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal, engine
    try:
        async with AsyncSessionLocal() as db, db.begin():
            return int(await db.scalar(text("SELECT purge_expired_ai_conversations(500)")) or 0)
    finally:
        await engine.dispose()


@celery_app.task(name="tasks.purge_expired_ai_conversations")
def purge_expired_ai_conversations_task():
    return {"purged": asyncio.run(_purge_expired_ai_conversations())}
