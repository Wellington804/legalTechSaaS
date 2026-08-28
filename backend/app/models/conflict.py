import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Boolean, JSON
from app.core.database import Base

class ConflictCheck(Base):
    __tablename__ = "conflict_checks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True)
    entity_name = Column(String, nullable=False, index=True)
    cpf_cnpj = Column(String, nullable=True, index=True)
    check_type = Column(String, default="GLOBAL_ETHICAL") # GLOBAL_ETHICAL, PARTY_OPPONENT, RELATIONAL
    has_conflict = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0) # 0.0 to 1.0
    matched_records = Column(JSON, nullable=True)
    checked_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
