"""Immutable, tenant-scoped snapshots of descriptive DataJud analyses."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, UniqueConstraint

from app.core.database import Base


class JurimetrySnapshot(Base):
    __tablename__ = "jurimetry_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_jurimetry_snapshots_tenant_id"),
        UniqueConstraint("tenant_id", "request_id", name="uq_jurimetry_snapshots_request"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_jurimetry_snapshots_creator_tenant",
        ),
        CheckConstraint("sample_limit IN (50, 100, 200)", name="ck_jurimetry_snapshots_sample_limit"),
        CheckConstraint(
            "sample_size >= 0 AND sample_size <= sample_limit",
            name="ck_jurimetry_snapshots_sample_size",
        ),
        CheckConstraint(
            "total_matches IS NULL OR total_matches >= sample_size",
            name="ck_jurimetry_snapshots_total_matches",
        ),
        CheckConstraint(
            "total_relation IN ('eq', 'gte', 'unknown')",
            name="ck_jurimetry_snapshots_total_relation",
        ),
        Index("ix_jurimetry_snapshots_tenant_queried", "tenant_id", "queried_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    request_id = Column(String(36), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    tribunal = Column(String(20), nullable=False, index=True)
    filters = Column(JSON, nullable=False)
    sample_limit = Column(Integer, nullable=False)
    sample_size = Column(Integer, nullable=False)
    total_matches = Column(Integer, nullable=True)
    total_relation = Column(String(8), nullable=False)
    source_name = Column(String(80), nullable=False)
    source_url = Column(String(500), nullable=False)
    queried_at = Column(DateTime(timezone=True), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    universe = Column(String(1000), nullable=False)
    metrics = Column(JSON, nullable=False)
    limitations = Column(JSON, nullable=False)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
