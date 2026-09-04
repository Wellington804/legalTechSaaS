"""Explicit pilot feedback; never automatic client/route telemetry."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, JSON, String, Text, UniqueConstraint, CheckConstraint
from app.core.database import Base


class PilotFeedback(Base):
    __tablename__ = "pilot_feedback"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "request_id", name="uq_pilot_feedback_request"),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_pilot_feedback_owner"),
        CheckConstraint("kind IN ('problem','weekly')", name="ck_pilot_feedback_kind"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    request_id = Column(String(36), nullable=False)
    kind = Column(String(16), nullable=False)
    area = Column(String(24), nullable=False)
    message = Column(Text, nullable=False)
    release = Column(String(100), nullable=False)
    completed_steps = Column(JSON, nullable=False)
    help_steps = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
