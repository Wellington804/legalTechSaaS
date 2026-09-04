import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_conversations_tenant_id"),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_ai_conversations_user_tenant", ondelete="CASCADE"),
        CheckConstraint("context_kind IN ('global','client','case','document','library','branding')", name="ck_ai_conversations_context_kind"),
        CheckConstraint("retention_days IN (30,90,365)", name="ck_ai_conversations_retention_days"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String(160), nullable=False, default="Nova conversa")
    context_kind = Column(String(16), nullable=False, default="global")
    client_id = Column(String, nullable=True)
    case_id = Column(String, nullable=True)
    document_id = Column(String, nullable=True)
    retention_days = Column(Integer, nullable=False, default=90)
    message_count = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AIConversationMessage(Base):
    __tablename__ = "ai_conversation_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_conversation_messages_tenant_id"),
        UniqueConstraint("tenant_id", "conversation_id", "sequence", name="uq_ai_conversation_message_sequence"),
        ForeignKeyConstraint(["tenant_id", "conversation_id"], ["ai_conversations.tenant_id", "ai_conversations.id"], name="fk_ai_messages_conversation_tenant", ondelete="CASCADE"),
        CheckConstraint("role IN ('user','assistant')", name="ck_ai_conversation_messages_role"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)
    limitations = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
