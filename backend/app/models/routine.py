"""Private reminders and idempotency records for real workspace actions."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, UniqueConstraint, text

from app.core.database import Base


class RoutineAction(Base):
    __tablename__ = "routine_actions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "request_id", name="uq_routine_action_request"),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_routine_action_user"),
        ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_routine_action_case"),
        CheckConstraint("kind IN ('checklist','outcome')", name="ck_routine_action_kind"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False)
    case_id = Column(String, nullable=False)
    request_id = Column(String(36), nullable=False)
    kind = Column(String(16), nullable=False)
    request_hash = Column(String(64), nullable=False)
    result = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RoutineReminder(Base):
    __tablename__ = "routine_reminders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "id", name="uq_routine_reminder_owner"),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_routine_reminder_user"),
        ForeignKeyConstraint(["tenant_id", "task_id"], ["workspace_tasks.tenant_id", "workspace_tasks.id"], name="fk_routine_reminder_task"),
        CheckConstraint("status IN ('scheduled','due','cancelled')", name="ck_routine_reminder_status"),
        CheckConstraint("push_requested IN ('not_requested','pending','unavailable')", name="ck_routine_reminder_push_requested"),
        Index("uq_routine_reminder_active", "tenant_id", "user_id", "task_id", unique=True, postgresql_where=text("status IN ('scheduled','due')")),
        Index("ix_routine_reminder_due", "remind_at", postgresql_where=text("status = 'scheduled'")),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False)
    task_id = Column(String, nullable=False)
    task_revision = Column(Integer, nullable=False)
    due_at_snapshot = Column(DateTime(timezone=True), nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, default="scheduled")
    push_requested = Column(String(16), nullable=False, default="not_requested")
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
