"""Private device credentials and a durable, content-free push outbox."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("endpoint_hash", name="uq_push_subscription_endpoint"),
        UniqueConstraint("tenant_id", "user_id", "id", name="uq_push_subscription_owner"),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_push_subscription_user"),
        ForeignKeyConstraint(["tenant_id", "user_id", "auth_session_id"], ["auth_sessions.tenant_id", "auth_sessions.user_id", "auth_sessions.id"], name="fk_push_subscription_session"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    auth_session_id = Column(String, nullable=False, index=True)
    endpoint_hash = Column(String(64), nullable=False)
    credentials_encrypted = Column(Text, nullable=False)
    vapid_key_hash = Column(String(64), nullable=False)
    label = Column(String(80), nullable=False)
    consented_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (
        UniqueConstraint("subscription_id", "event_key", name="uq_push_delivery_event"),
        ForeignKeyConstraint(["tenant_id", "user_id", "subscription_id"], ["push_subscriptions.tenant_id", "push_subscriptions.user_id", "push_subscriptions.id"], name="fk_push_delivery_subscription"),
        ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_push_delivery_case"),
        ForeignKeyConstraint(["tenant_id", "task_id"], ["workspace_tasks.tenant_id", "workspace_tasks.id"], name="fk_push_delivery_task"),
        ForeignKeyConstraint(["tenant_id", "user_id", "reminder_id"], ["routine_reminders.tenant_id", "routine_reminders.user_id", "routine_reminders.id"], name="fk_push_delivery_reminder"),
        CheckConstraint("kind IN ('task_assigned','portal_message','portal_document','test','task_reminder','judicial_movement')", name="ck_push_delivery_kind"),
        CheckConstraint("status IN ('queued','processing','accepted','failed','expired','cancelled','unknown')", name="ck_push_delivery_status"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False)
    subscription_id = Column(String, nullable=False, index=True)
    event_key = Column(String(64), nullable=False)
    kind = Column(String(24), nullable=False)
    case_id = Column(String, nullable=True)
    task_id = Column(String, nullable=True)
    reminder_id = Column(String, nullable=True, index=True)
    status = Column(String(16), nullable=False, default="queued", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
