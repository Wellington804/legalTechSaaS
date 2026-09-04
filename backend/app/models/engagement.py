"""Case-bound communication and revocable client portal access."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint, CheckConstraint
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TenantChannel(Base):
    __tablename__ = "tenant_channels"
    __table_args__ = (
        CheckConstraint("whatsapp_connection_state IN ('disconnected','pending','connected')", name="ck_tenant_channel_whatsapp_state"),
        UniqueConstraint("evolution_instance_id_hash", name="uq_tenant_channels_evolution_instance_id_hash"),
    )
    tenant_id = Column(String, ForeignKey("tenants.id"), primary_key=True)
    email_enabled = Column(Boolean, nullable=False, default=False)
    whatsapp_enabled = Column(Boolean, nullable=False, default=False)
    ai_enabled = Column(Boolean, nullable=False, default=False)
    evolution_instance_id_encrypted = Column(Text, nullable=True)
    evolution_instance_id_hash = Column(String(64), nullable=True)
    evolution_api_key_encrypted = Column(Text, nullable=True)
    evolution_token_encrypted = Column(Text, nullable=True)
    whatsapp_number = Column(String(32), nullable=True)
    whatsapp_connection_state = Column(String(24), nullable=False, default="disconnected")
    whatsapp_last_checked_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CaseMessage(Base):
    __tablename__ = "case_messages"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"]),
        ForeignKeyConstraint(["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"]),
        ForeignKeyConstraint(["tenant_id", "delivery_id"], ["notification_deliveries.tenant_id", "notification_deliveries.id"], name="fk_case_message_delivery_tenant"),
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        UniqueConstraint("delivery_id", name="uq_case_message_delivery"),
        UniqueConstraint("tenant_id", "request_id", name="uq_case_message_request"),
        CheckConstraint("channel IN ('portal','email','whatsapp')", name="ck_case_message_channel"),
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_case_message_direction"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    client_id = Column(String, nullable=False)
    request_id = Column(String(36), nullable=False)
    channel = Column(String(16), nullable=False)
    direction = Column(String(16), nullable=False)
    body = Column(Text, nullable=False)
    delivery_id = Column(String, nullable=True)
    created_by_user_id = Column(String, nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PortalGrant(Base):
    __tablename__ = "portal_grants"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"]),
                      ForeignKeyConstraint(["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"]),
                      ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
                      UniqueConstraint("tenant_id", "id", name="uq_portal_grants_tenant_id"))
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    client_id = Column(String, nullable=False)
    token_hash = Column(String(64), nullable=False)
    session_hash = Column(String(64), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PortalFolderShare(Base):
    __tablename__ = "portal_folder_shares"
    __table_args__ = (
        UniqueConstraint("tenant_id", "grant_id", "folder_id", name="uq_portal_folder_share"),
        ForeignKeyConstraint(["tenant_id", "grant_id"], ["portal_grants.tenant_id", "portal_grants.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "folder_id"], ["workspace_document_folders.tenant_id", "workspace_document_folders.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    grant_id = Column(String, nullable=False, index=True)
    folder_id = Column(String, nullable=False, index=True)
    can_upload = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(String, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PortalChecklist(Base):
    __tablename__ = "portal_checklist"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"]),
                      ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"]))
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    document_id = Column(String, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
