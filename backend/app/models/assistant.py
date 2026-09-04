import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, text

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


class AIEvaluationCase(Base):
    __tablename__ = "ai_evaluation_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_evaluation_cases_tenant_id"),
        UniqueConstraint("tenant_id", "name", "version", name="uq_ai_evaluation_cases_version"),
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_ai_eval_cases_creator_tenant"),
        ForeignKeyConstraint(["tenant_id", "reviewed_by_user_id"], ["users.tenant_id", "users.id"], name="fk_ai_eval_cases_reviewer_tenant"),
        CheckConstraint("status IN ('draft','approved','rejected','retired')", name="ck_ai_evaluation_cases_status"),
        CheckConstraint("version > 0", name="ck_ai_evaluation_cases_version"),
        CheckConstraint(
            "(status = 'draft' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) "
            "OR status = 'retired' OR "
            "(status IN ('approved','rejected') AND reviewed_by_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND reviewed_by_user_id <> created_by_user_id)",
            name="ck_ai_evaluation_cases_independent_review",
        ),
        Index(
            "uq_ai_evaluation_cases_approved_name", "tenant_id", "name", unique=True,
            postgresql_where=text("status = 'approved'"),
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    legal_area = Column(String(100), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="draft", index=True)
    content = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_by_user_id = Column(String, nullable=False)
    reviewed_by_user_id = Column(String, nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AIEvaluationRun(Base):
    __tablename__ = "ai_evaluation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_evaluation_runs_tenant_id"),
        UniqueConstraint("tenant_id", "request_id", name="uq_ai_evaluation_runs_request"),
        ForeignKeyConstraint(["tenant_id", "requested_by_user_id"], ["users.tenant_id", "users.id"], name="fk_ai_eval_runs_requester_tenant"),
        CheckConstraint("status IN ('queued','running','completed','failed')", name="ck_ai_evaluation_runs_status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    request_id = Column(String(36), nullable=False)
    status = Column(String(16), nullable=False, default="queued", index=True)
    provider = Column(String(40), nullable=False)
    model = Column(String(200), nullable=False)
    corpus_hash = Column(String(64), nullable=False)
    case_count = Column(Integer, nullable=False)
    case_ids = Column(JSON, nullable=False)
    aggregate_metrics = Column(JSON, nullable=True)
    error = Column(String(500), nullable=True)
    requested_by_user_id = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AIEvaluationResult(Base):
    __tablename__ = "ai_evaluation_results"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_ai_evaluation_results_tenant_id"),
        UniqueConstraint("tenant_id", "run_id", "case_id", name="uq_ai_evaluation_results_case"),
        ForeignKeyConstraint(["tenant_id", "run_id"], ["ai_evaluation_runs.tenant_id", "ai_evaluation_runs.id"], name="fk_ai_eval_results_run_tenant", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "case_id"], ["ai_evaluation_cases.tenant_id", "ai_evaluation_cases.id"], name="fk_ai_eval_results_case_tenant", ondelete="RESTRICT"),
        CheckConstraint("status IN ('completed','failed','stale')", name="ck_ai_evaluation_results_status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    run_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    case_version = Column(Integer, nullable=False)
    case_hash = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    output = Column(JSON, nullable=True)
    output_hash = Column(String(64), nullable=True)
    metrics = Column(JSON, nullable=True)
    error = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DocumentIntelligenceAnalysis(Base):
    __tablename__ = "document_intelligence_analyses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_document_intelligence_analyses_tenant_id"),
        UniqueConstraint("tenant_id", "request_id", name="uq_document_intelligence_request"),
        ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_document_intelligence_case_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "requested_by_user_id"], ["users.tenant_id", "users.id"], name="fk_document_intelligence_requester_tenant"),
        ForeignKeyConstraint(["tenant_id", "reviewed_by_user_id"], ["users.tenant_id", "users.id"], name="fk_document_intelligence_reviewer_tenant"),
        CheckConstraint("status IN ('queued','processing','review_required','approved','rejected','failed','stale')", name="ck_document_intelligence_status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    request_id = Column(String(36), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="queued", index=True)
    provider = Column(String(40), nullable=False)
    model = Column(String(200), nullable=False)
    evidence_sources = Column(JSON, nullable=True)
    result_hash = Column(String(64), nullable=True)
    classifications = Column(JSON, nullable=True)
    timeline = Column(JSON, nullable=True)
    contradiction_groups = Column(JSON, nullable=True)
    limitations = Column(JSON, nullable=True)
    coverage = Column(JSON, nullable=True)
    error = Column(String(500), nullable=True)
    requested_by_user_id = Column(String, nullable=False)
    reviewed_by_user_id = Column(String, nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class DocumentIntelligenceSource(Base):
    __tablename__ = "document_intelligence_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_document_intelligence_sources_tenant_id"),
        UniqueConstraint("tenant_id", "analysis_id", "document_id", name="uq_document_intelligence_source_document"),
        ForeignKeyConstraint(["tenant_id", "analysis_id"], ["document_intelligence_analyses.tenant_id", "document_intelligence_analyses.id"], name="fk_document_intelligence_sources_analysis_tenant", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"], name="fk_document_intelligence_sources_document_tenant", ondelete="RESTRICT"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    analysis_id = Column(String, nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    document_version = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    binary_sha256 = Column(String(64), nullable=True)
    text_sha256 = Column(String(64), nullable=False)
    extractor = Column(String(80), nullable=False)
    ocr_status = Column(String(24), nullable=False)
    title = Column(String(300), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DocumentIntelligenceConsentReceipt(Base):
    __tablename__ = "document_intelligence_consent_receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_document_intelligence_consent_receipts_tenant_id"),
        UniqueConstraint("tenant_id", "analysis_id", name="uq_document_intelligence_consent_analysis"),
        ForeignKeyConstraint(
            ["tenant_id", "analysis_id"],
            ["document_intelligence_analyses.tenant_id", "document_intelligence_analyses.id"],
            name="fk_document_intelligence_consent_analysis_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"],
            name="fk_document_intelligence_consent_user_tenant", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_document_intelligence_consent_case_tenant", ondelete="RESTRICT",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    analysis_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    provider = Column(String(40), nullable=False)
    purpose = Column(String(80), nullable=False)
    policy_version = Column(String(32), nullable=False)
    document_manifest = Column(JSON, nullable=False)
    receipt_hash = Column(String(64), nullable=False)
    consented_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
