import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Float, Text, ForeignKey, UniqueConstraint
from app.core.database import Base

class OABApplication(Base):
    __tablename__ = "oab_applications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    seccional = Column(String, nullable=False) # e.g. OAB/SP, OAB/AL, OAB/RJ
    candidate_name = Column(String, nullable=False)
    cpf = Column(String, nullable=False, index=True)
    rg = Column(String, nullable=False)
    status = Column(String, default="EM_ANDAMENTO") # EM_ANDAMENTO, PENDENTE_DOCUMENTOS, PROTOCOLADO, CARTEIRA_EMITIDA
    fgv_exam_number = Column(String, nullable=True)
    protocol_number = Column(String, nullable=True)
    biometric_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    delivery_ceremony_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class OABChecklist(Base):
    __tablename__ = "oab_checklists"
    __table_args__ = (UniqueConstraint("application_id", "item_code", name="uq_oab_checklist_item"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("oab_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    item_code = Column(String, nullable=False) # CERTIFICADO_FGV, DIPLOMA, RG_CPF, TITULO_ELEITOR, RESERVISTA, RESIDENCIA, CERTIDOES_NEGATIVAS, FOTOS_3X4
    title = Column(String, nullable=False)
    is_completed = Column(Boolean, default=False)
    file_url = Column(String, nullable=True)
    verification_notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class OABFeeStructure(Base):
    __tablename__ = "oab_fee_structures"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seccional = Column(String, nullable=False, index=True)
    req_fee = Column(Float, nullable=False, default=250.00)
    card_fee = Column(Float, nullable=False, default=180.00)
    anuidade_full = Column(Float, nullable=False, default=950.00)
    jovem_advogado_discount_pct = Column(Float, nullable=False, default=50.0) # 50% discount for first 5 years
    sua_discount_pct = Column(Float, nullable=False, default=25.0) # up to 25% discount for SUA registration
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class OABDeclaration(Base):
    __tablename__ = "oab_declarations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String, ForeignKey("oab_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    declaration_type = Column(String, nullable=False) # IDONEIDADE_MORAL, NAO_INCOMPATIBILIDADE
    declarant_name = Column(String, nullable=False)
    cpf = Column(String, nullable=False)
    content_text = Column(Text, nullable=False)
    signed_digitally = Column(Boolean, default=False)
    signature_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
