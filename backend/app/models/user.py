import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, String

from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="lawyer")  # admin, partner, lawyer, paralegal
    oab_number = Column(String, nullable=True)
    oab_uf = Column(String, nullable=True)
    professional_name = Column(String(120), nullable=True)
    professional_email = Column(String(320), nullable=True)
    professional_phone = Column(String(32), nullable=True)
    professional_address = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    mfa_secret_encrypted = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_enrolled_at = Column(DateTime(timezone=True), nullable=True)
    mfa_last_counter = Column(BigInteger, nullable=True)
    calendar_feed_token_hash = Column(String(64), nullable=True)
    calendar_feed_created_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
