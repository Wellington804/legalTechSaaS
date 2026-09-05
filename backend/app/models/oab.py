"""Tenant and user scoped OAB enrollment tracking.

The records are an organizer maintained by the user. They are not an OAB
protocol system and intentionally contain no identity documents or charges.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OABEnrollment(Base):
    __tablename__ = "oab_enrollments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_oab_enrollments_tenant_id"),
        UniqueConstraint("tenant_id", "user_id", "id", name="uq_oab_enrollments_owner_id"),
        UniqueConstraint("tenant_id", "user_id", "request_id", name="uq_oab_enrollments_owner_request"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_oab_enrollments_owner_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO')",
            name="ck_oab_enrollments_uf",
        ),
        CheckConstraint(
            "enrollment_type IN ('principal','supplementary','transfer','other')",
            name="ck_oab_enrollments_type",
        ),
        CheckConstraint(
            "status IN ('planning','gathering','submitted','awaiting_response','completed','paused')",
            name="ck_oab_enrollments_status",
        ),
        Index("ix_oab_enrollments_owner_updated", "tenant_id", "user_id", "updated_at"),
        Index("ix_oab_enrollments_uf", "uf"),
        Index("ix_oab_enrollments_status", "status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(36), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, nullable=False)
    uf = Column(String(2), nullable=False)
    enrollment_type = Column(String(24), nullable=False)
    status = Column(String(24), nullable=False, default="planning")
    protocol = Column(String(120), nullable=True)
    source_url = Column(String(2048), nullable=False)
    source_version = Column(String(64), nullable=False)
    source_checked_at = Column(DateTime(timezone=True), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class OABEnrollmentChecklistItem(Base):
    __tablename__ = "oab_enrollment_checklist_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id", "enrollment_id"],
            ["oab_enrollments.tenant_id", "oab_enrollments.user_id", "oab_enrollments.id"],
            name="fk_oab_checklist_enrollment_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "user_id", "enrollment_id", "request_id", name="uq_oab_checklist_owner_request"),
        CheckConstraint("length(btrim(title)) > 0", name="ck_oab_checklist_title"),
        Index("ix_oab_checklist_owner_enrollment", "tenant_id", "user_id", "enrollment_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(36), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, nullable=False)
    enrollment_id = Column(String, nullable=False)
    title = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
