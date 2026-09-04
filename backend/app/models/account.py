import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String, Text, UniqueConstraint

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "id", name="uq_auth_sessions_push_owner"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    mfa_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_account_tokens_hash"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    token_type = Column(String(32), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class TeamInvitation(Base):
    __tablename__ = "team_invitations"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_team_invitation_tenant_email"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email = Column(String(320), nullable=False)
    role = Column(String(16), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SubscriptionRequest(Base):
    __tablename__ = "subscription_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    request_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="received", index=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class PrivacyRequest(Base):
    __tablename__ = "privacy_requests"
    __table_args__ = (
        CheckConstraint("request_type IN ('export', 'deletion', 'anonymization')", name="ck_privacy_requests_type"),
        CheckConstraint("scope IN ('self', 'tenant')", name="ck_privacy_requests_scope"),
        CheckConstraint("status IN ('received', 'in_review', 'completed', 'rejected', 'cancelled')", name="ck_privacy_requests_status"),
        UniqueConstraint("tenant_id", "id", name="uq_privacy_requests_tenant_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_type = Column(String(32), nullable=False, index=True)
    scope = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="received", index=True)
    reason = Column(Text, nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
