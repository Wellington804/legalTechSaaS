import base64
import binascii
import hashlib
import hmac
import time
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    NotificationDelivery,
    NotificationEvent,
    NotificationProviderReceipt,
)


RESEND_IDEMPOTENCY_WINDOW_SECONDS = 24 * 60 * 60


def recipient_digest(recipient: str) -> str:
    return hashlib.sha256(recipient.encode("utf-8")).hexdigest()


def delivery_scope(delivery_id: str, tenant_id: str):
    return select(NotificationDelivery).where(
        NotificationDelivery.id == delivery_id,
        NotificationDelivery.tenant_id == tenant_id,
    )


async def create_or_get_delivery(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    resource_ref: str,
    recipient: str,
    channel: str,
) -> tuple[NotificationDelivery, bool]:
    identity = {
        "tenant_id": tenant_id,
        "resource_ref": resource_ref,
        "recipient_hash": recipient_digest(recipient),
        "channel": channel,
    }
    existing = (
        await db.execute(select(NotificationDelivery).filter_by(**identity))
    ).scalars().first()
    if existing:
        return existing, True

    delivery = NotificationDelivery(
        **identity,
        requested_by_user_id=user_id,
        recipient=recipient,
        status="queued",
    )
    try:
        async with db.begin_nested():
            db.add(delivery)
            await db.flush()
    except IntegrityError:
        existing = (
            await db.execute(select(NotificationDelivery).filter_by(**identity))
        ).scalars().first()
        if existing:
            return existing, True
        raise
    return delivery, False


async def get_tenant_delivery(
    db: AsyncSession, delivery_id: str, tenant_id: str
) -> NotificationDelivery | None:
    return (await db.execute(delivery_scope(delivery_id, tenant_id))).scalars().first()


def verify_resend_signature(
    raw_body: bytes,
    *,
    message_id: str,
    timestamp: str,
    signatures: str,
    secret: str,
    now: int | None = None,
    tolerance_seconds: int = 300,
) -> bool:
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs((int(time.time()) if now is None else now) - timestamp_int) > tolerance_seconds:
        return False
    if not message_id or len(message_id) > 255:
        return False

    encoded_secret = secret.removeprefix("whsec_")
    try:
        key = base64.b64decode(encoded_secret, validate=True)
    except (binascii.Error, ValueError):
        return False
    signed = f"{message_id}.{timestamp}.".encode("utf-8") + raw_body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    for candidate in signatures.split():
        if candidate.startswith("v1,") and hmac.compare_digest(candidate[3:], expected):
            return True
    return False


def provider_event_digest(provider: str, event_identity: str) -> str:
    return hashlib.sha256(f"{provider}:{event_identity}".encode("utf-8")).hexdigest()


def provider_message_digest(provider_message_id: str) -> str:
    return hashlib.sha256(provider_message_id.encode("utf-8")).hexdigest()


def resend_retry_window_open(
    provider_attempted_at: datetime | None, *, now: datetime | None = None
) -> bool:
    """Retries need a recorded first provider-attempt time; unknown is safer otherwise."""
    if provider_attempted_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if provider_attempted_at.tzinfo is None:
        provider_attempted_at = provider_attempted_at.replace(tzinfo=timezone.utc)
    return (now - provider_attempted_at).total_seconds() < RESEND_IDEMPOTENCY_WINDOW_SECONDS


def next_delivery_status(current: str, incoming: str) -> str:
    if incoming == "failed":
        return "failed"
    if current == "failed":
        return current
    if incoming == "delivered":
        return "delivered"
    if current == "delivered":
        return current
    return incoming


def _apply_receipt_to_delivery(
    db: AsyncSession,
    *,
    delivery: NotificationDelivery,
    provider: str,
    event_digest: str,
    event_type: str,
    status: str,
) -> None:
    db.add(
        NotificationEvent(
            delivery_id=delivery.id,
            provider=provider,
            event_digest=event_digest,
            event_type=event_type[:64],
        )
    )
    delivery.status = next_delivery_status(delivery.status, status)
    delivery.error_code = None if delivery.status in {"sent", "delivered"} else event_type[:64]
    now = datetime.now(timezone.utc)
    if status == "sent" and delivery.sent_at is None:
        delivery.sent_at = now
    if delivery.status == "delivered":
        delivery.delivered_at = now


async def _provider_delivery(
    db: AsyncSession, *, channel: str, provider_message_id: str
) -> tuple[NotificationDelivery | None, str | None]:
    tenant_id = None
    if db.bind and db.bind.dialect.name == "postgresql":
        tenant_id = await db.scalar(
            text("SELECT notification_tenant_for_provider(:channel, :message_id)"),
            {"channel": channel, "message_id": provider_message_id},
        )
        if not tenant_id:
            return None, None
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )
    query = select(NotificationDelivery).where(
        NotificationDelivery.channel == channel,
        NotificationDelivery.provider_message_id == provider_message_id,
    )
    if tenant_id:
        query = query.where(NotificationDelivery.tenant_id == tenant_id)
    delivery = (await db.execute(query.with_for_update())).scalars().first()
    return delivery, tenant_id


async def reconcile_provider_receipts(
    db: AsyncSession, delivery: NotificationDelivery
) -> int:
    """Attach early receipts after the worker has durably stored a provider message id."""
    if not delivery.provider_message_id:
        return 0
    provider = "resend" if delivery.channel == "email" else "evolution"
    receipts = (
        await db.execute(
            select(NotificationProviderReceipt)
            .where(
                NotificationProviderReceipt.provider == provider,
                NotificationProviderReceipt.provider_message_hash
                == provider_message_digest(delivery.provider_message_id),
                NotificationProviderReceipt.delivery_id.is_(None),
            )
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for receipt in receipts:
        receipt.tenant_id = delivery.tenant_id
        receipt.delivery_id = delivery.id
        _apply_receipt_to_delivery(
            db,
            delivery=delivery,
            provider=receipt.provider,
            event_digest=receipt.event_digest,
            event_type=receipt.event_type,
            status=receipt.status,
        )
    return len(receipts)


async def apply_provider_event(
    db: AsyncSession,
    *,
    provider: str,
    provider_message_id: str,
    event_identity: str,
    event_type: str,
    status: str,
    expected_tenant_id: str | None = None,
) -> bool:
    channel = "email" if provider == "resend" else "whatsapp"
    digest = provider_event_digest(provider, event_identity)
    if expected_tenant_id and db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": expected_tenant_id},
        )
    receipt = NotificationProviderReceipt(
        tenant_id=expected_tenant_id,
        provider=provider,
        provider_message_hash=provider_message_digest(provider_message_id),
        event_digest=digest,
        event_type=event_type[:64],
        status=status,
    )
    db.add(receipt)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    delivery, tenant_id = await _provider_delivery(
        db, channel=channel, provider_message_id=provider_message_id
    )
    if expected_tenant_id and tenant_id and tenant_id != expected_tenant_id:
        await db.rollback()
        return False
    if delivery:
        receipt.tenant_id = tenant_id or delivery.tenant_id
        receipt.delivery_id = delivery.id
        _apply_receipt_to_delivery(
            db,
            delivery=delivery,
            provider=provider,
            event_digest=digest,
            event_type=event_type,
            status=status,
        )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return False
    return True
