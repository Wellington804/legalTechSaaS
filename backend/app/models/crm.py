import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CRMOpportunity(Base):
    __tablename__ = "crm_opportunities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_crm_opportunities_tenant_id"),
        UniqueConstraint("tenant_id", "request_id", name="uq_crm_opportunities_request"),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_crm_opportunities_client_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_crm_opportunities_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "intake_id"],
            ["public_intakes.tenant_id", "public_intakes.id"],
            name="fk_crm_opportunities_intake_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_crm_opportunities_owner_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_crm_opportunities_creator_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "stage IN ('new','qualified','proposal','won','lost')",
            name="ck_crm_opportunities_stage",
        ),
        CheckConstraint(
            "source IN ('manual','intake','referral','website','whatsapp','email','other')",
            name="ck_crm_opportunities_source",
        ),
        CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0",
            name="ck_crm_opportunities_estimated_value",
        ),
        CheckConstraint(
            "next_action_at IS NULL OR next_action IS NOT NULL",
            name="ck_crm_opportunities_next_action",
        ),
        Index("ix_crm_opportunities_pipeline", "tenant_id", "archived_at", "stage", "next_action_at"),
        Index("ix_crm_opportunities_owner", "tenant_id", "owner_user_id"),
        Index("ix_crm_opportunities_client", "tenant_id", "client_id"),
        Index("ix_crm_opportunities_case", "tenant_id", "case_id"),
        Index("ix_crm_opportunities_intake", "tenant_id", "intake_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    request_id = Column(String(36), nullable=False)
    title = Column(String(200), nullable=False)
    stage = Column(String(16), nullable=False, default="new")
    source = Column(String(16), nullable=False, default="manual")
    estimated_value = Column(Numeric(14, 2), nullable=True)
    next_action = Column(String(500), nullable=True)
    next_action_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    client_id = Column(String, nullable=True)
    case_id = Column(String, nullable=True)
    intake_id = Column(String, nullable=True)
    owner_user_id = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
