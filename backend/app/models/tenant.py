import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, Column, DateTime, Integer, String

from app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (CheckConstraint("data_retention_days IS NULL OR data_retention_days BETWEEN 30 AND 3650", name="ck_tenants_data_retention_days"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    cnpj = Column(String, nullable=True)
    legal_name = Column(String(160), nullable=True)
    office_email = Column(String(320), nullable=True)
    office_phone = Column(String(32), nullable=True)
    website = Column(String(2048), nullable=True)
    office_address = Column(JSON, nullable=True)
    timezone = Column(String(64), nullable=False, default="America/Sao_Paulo")
    signature_city = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True)
    subscription_status = Column(String, default="trial", nullable=False)
    subscription_plan = Column(String, default="trial", nullable=False)
    trial_starts_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    subscription_ends_at = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    quota_users = Column(Integer, default=3, nullable=False)
    quota_storage_bytes = Column(Integer, default=1073741824, nullable=False)
    quota_messages = Column(Integer, default=100, nullable=False)
    privacy_notice_url = Column(String(2048), nullable=True)
    privacy_notice_version = Column(String(64), nullable=True)
    privacy_contact = Column(String(320), nullable=True)
    data_retention_days = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
