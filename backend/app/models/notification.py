import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_notification_delivery_tenant_id"),
        UniqueConstraint(
            "tenant_id",
            "resource_ref",
            "recipient_hash",
            "channel",
            name="uq_notification_delivery_identity",
        ),
        UniqueConstraint(
            "channel",
            "provider_message_id",
            name="uq_notification_provider_message",
        ),
        CheckConstraint(
            "channel IN ('email', 'whatsapp')",
            name="ck_notification_channel",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'sent', 'delivered', 'unknown', 'failed')",
            name="ck_notification_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    requested_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    resource_ref = Column(String(128), nullable=False)
    recipient = Column(String(320), nullable=False)
    recipient_hash = Column(String(64), nullable=False)
    channel = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="queued", index=True)
    provider_message_id = Column(String(255), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    # Recorded before an external email request. It bounds safe Resend retries.
    provider_attempted_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_digest", name="uq_notification_event_digest"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id = Column(
        String,
        ForeignKey("notification_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(16), nullable=False)
    event_digest = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class NotificationProviderReceipt(Base):
    """Minimal provider-event inbox; raw webhook payloads and recipients are never stored."""

    __tablename__ = "notification_provider_receipts"
    __table_args__ = (
        UniqueConstraint("provider", "event_digest", name="uq_notification_receipt_event"),
        CheckConstraint("provider IN ('resend', 'evolution')", name="ck_notification_receipt_provider"),
        CheckConstraint(
            "status IN ('sent', 'delivered', 'failed')",
            name="ck_notification_receipt_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # A receipt can precede the worker persisting the provider message id.
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True, index=True)
    delivery_id = Column(
        String,
        ForeignKey("notification_deliveries.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider = Column(String(16), nullable=False)
    provider_message_hash = Column(String(64), nullable=False)
    event_digest = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
