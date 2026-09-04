import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkspaceClient(Base):
    __tablename__ = "workspace_clients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_clients_tenant_id"),
        CheckConstraint(
            "stage IN ('lead', 'prospect', 'client', 'inactive')",
            name="ck_workspace_clients_stage",
        ),
        CheckConstraint(
            "person_type IN ('individual', 'company')",
            name="ck_workspace_clients_person_type",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=True)
    phone = Column(String(32), nullable=True)
    tax_id = Column(String(20), nullable=True)
    person_type = Column(String(16), nullable=False, default="individual")
    qualification = Column(String(500), nullable=True)
    occupation = Column(String(160), nullable=True)
    has_legal_representative = Column(Boolean, nullable=False, default=False)
    representative_name = Column(String(200), nullable=True)
    representative_tax_id = Column(String(20), nullable=True)
    representative_qualification = Column(String(500), nullable=True)
    representative_email = Column(String(320), nullable=True)
    representative_phone = Column(String(32), nullable=True)
    representative_address = Column(JSON, nullable=True)
    address = Column(JSON, nullable=True)
    stage = Column(String(16), nullable=False, default="lead", index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspaceCase(Base):
    __tablename__ = "workspace_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_cases_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_workspace_cases_client_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "responsible_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_cases_responsible_user_tenant",
        ),
        CheckConstraint(
            "status IN ('open', 'paused', 'closed', 'archived')",
            name="ck_workspace_cases_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    number = Column(String(64), nullable=True)
    court = Column(String(300), nullable=True)
    status = Column(String(16), nullable=False, default="open", index=True)
    responsible_user_id = Column(String, nullable=False, index=True)
    restricted = Column(Boolean, nullable=False, default=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspaceCaseAccess(Base):
    __tablename__ = "workspace_case_access"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_case_access_tenant_id"),
        UniqueConstraint("tenant_id", "case_id", "user_id", name="uq_workspace_case_access_user"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_case_access_case_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_case_access_user_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkspaceCaseParty(Base):
    __tablename__ = "workspace_case_parties"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_case_parties_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_case_parties_case_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "side IN ('client', 'opponent', 'third_party')",
            name="ck_workspace_case_parties_side",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    tax_id = Column(String(20), nullable=True)
    side = Column(String(16), nullable=False, default="third_party")
    role = Column(String(100), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspaceTask(Base):
    __tablename__ = "workspace_tasks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_tasks_tenant_id"),
        UniqueConstraint("tenant_id", "request_id", name="uq_workspace_tasks_request_id"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_tasks_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_tasks_assigned_user_tenant",
        ),
        CheckConstraint("kind IN ('task', 'deadline', 'hearing')", name="ck_workspace_tasks_kind"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_workspace_tasks_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    request_id = Column(String(36), nullable=True)
    case_id = Column(String, nullable=True, index=True)
    title = Column(String(300), nullable=False)
    kind = Column(String(16), nullable=False, default="task")
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    assigned_user_id = Column(String, nullable=True, index=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    manually_reviewed = Column(Boolean, nullable=False, default=False)
    location = Column(String(300), nullable=True)
    contact = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspaceDocument(Base):
    __tablename__ = "workspace_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_documents_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_documents_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_workspace_documents_client_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folder_id"],
            ["workspace_document_folders.tenant_id", "workspace_document_folders.id"],
            name="fk_workspace_documents_folder_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reviewed_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_documents_reviewer_tenant",
        ),
        CheckConstraint(
            "kind IN ('document', 'template', 'note', 'evidence')",
            name="ck_workspace_documents_kind",
        ),
        CheckConstraint(
            "document_type IN ('general','petition','contract','power_of_attorney','notice','correspondence')",
            name="ck_workspace_documents_document_type",
        ),
        CheckConstraint("content_format IN ('plain','markdown')", name="ck_workspace_documents_content_format"),
        CheckConstraint(
            "review_status IN ('draft','in_review','approved','final')",
            name="ck_workspace_documents_review_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    client_id = Column(String, nullable=True, index=True)
    folder_id = Column(String, nullable=True, index=True)
    kind = Column(String(16), nullable=False, default="document", index=True)
    document_type = Column(String(32), nullable=False, default="general", server_default="general", index=True)
    title = Column(String(300), nullable=False)
    content_text = Column(Text, nullable=True)
    content_format = Column(String(16), nullable=False, default="plain", server_default="plain")
    filename = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)
    file_content = Column(LargeBinary, nullable=True)
    file_size = Column(Integer, nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    current_version = Column(Integer, nullable=False, default=1)
    review_status = Column(String(16), nullable=False, default="draft", server_default="draft", index=True)
    review_version = Column(Integer, nullable=True)
    reviewed_by_user_id = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    purge_after = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspaceDocumentReview(Base):
    __tablename__ = "workspace_document_reviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_document_reviews_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["workspace_documents.tenant_id", "workspace_documents.id"],
            name="fk_workspace_document_reviews_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_document_reviews_user_tenant",
        ),
        CheckConstraint(
            "status IN ('comment','in_review','approved','final','reopened')",
            name="ck_workspace_document_reviews_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False)
    comment = Column(Text, nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkspaceDocumentVersion(Base):
    __tablename__ = "workspace_document_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_document_versions_tenant_id"),
        UniqueConstraint("tenant_id", "document_id", "version", name="uq_workspace_document_versions_number"),
        CheckConstraint("content_format IN ('plain','markdown')", name="ck_workspace_document_versions_content_format"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["workspace_documents.tenant_id", "workspace_documents.id"],
            name="fk_workspace_document_versions_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_document_versions_creator_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_portal_grant_id"],
            ["portal_grants.tenant_id", "portal_grants.id"],
            name="fk_workspace_document_versions_portal_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content_text = Column(Text, nullable=True)
    content_format = Column(String(16), nullable=False, default="plain", server_default="plain")
    filename = Column(String(255), nullable=True)
    content_type = Column(String(100), nullable=True)
    file_content = Column(LargeBinary, nullable=True)
    file_size = Column(Integer, nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    object_key = Column(String(512), nullable=True, unique=True)
    storage_status = Column(String(24), nullable=False, default="available", server_default="available", index=True)
    ocr_status = Column(String(24), nullable=False, default="not_required", server_default="not_required")
    processing_error = Column(String(500), nullable=True)
    created_by_user_id = Column(String, nullable=True)
    created_by_portal_grant_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkspaceDocumentFolder(Base):
    __tablename__ = "workspace_document_folders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_document_folders_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_workspace_document_folders_client_tenant", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_document_folders_case_tenant", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_id"], ["workspace_document_folders.tenant_id", "workspace_document_folders.id"],
            name="fk_workspace_document_folders_parent_tenant", ondelete="RESTRICT",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    parent_id = Column(String, nullable=True, index=True)
    name = Column(String(160), nullable=False)
    normalized_name = Column(String(160), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    archived_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspaceDocumentUpload(Base):
    __tablename__ = "workspace_document_uploads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_document_uploads_tenant_id"),
        CheckConstraint("status IN ('created','uploaded','processing','completed','failed','expired')", name="ck_workspace_document_uploads_status"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"],
            name="fk_workspace_document_uploads_document_tenant", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "folder_id"], ["workspace_document_folders.tenant_id", "workspace_document_folders.id"],
            name="fk_workspace_document_uploads_folder_tenant", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_workspace_document_uploads_user_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_portal_grant_id"], ["portal_grants.tenant_id", "portal_grants.id"],
            name="fk_workspace_document_uploads_portal_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, nullable=True, index=True)
    expected_version = Column(Integer, nullable=True)
    folder_id = Column(String, nullable=True, index=True)
    client_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    expected_size = Column(Integer, nullable=False)
    expected_sha256 = Column(String(64), nullable=True)
    object_key = Column(String(512), nullable=False, unique=True)
    status = Column(String(16), nullable=False, default="created", index=True)
    created_by_user_id = Column(String, nullable=True)
    created_by_portal_grant_id = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkspaceLibraryEntry(Base):
    __tablename__ = "workspace_library_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_library_entries_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_library_entries_creator_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    source_url = Column(String(2048), nullable=False)
    source_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorkspacePublication(Base):
    __tablename__ = "workspace_publications"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_publications_tenant_id"),
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_workspace_publications_dedupe"),
        CheckConstraint("source_kind IN ('manual', 'datajud')", name="ck_workspace_publications_source_kind"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_publications_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_publications_creator_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "acknowledged_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_publications_acknowledger_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    source_url = Column(String(2048), nullable=False)
    published_at = Column(Date, nullable=False, index=True)
    note = Column(Text, nullable=True)
    source_kind = Column(String(16), nullable=False, default="manual")
    dedupe_key = Column(String(64), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id = Column(String, nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class WorkspaceLedgerEntry(Base):
    __tablename__ = "workspace_ledger_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_workspace_ledger_entries_tenant_id"),
        UniqueConstraint("tenant_id", "request_id", name="uq_workspace_ledger_entries_request"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_workspace_ledger_entries_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_workspace_ledger_entries_client_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reversal_of_id"],
            ["workspace_ledger_entries.tenant_id", "workspace_ledger_entries.id"],
            name="fk_workspace_ledger_entries_reversal_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_ledger_entries_creator_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "manual_payment_confirmed_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_ledger_entries_confirmer_tenant",
        ),
        CheckConstraint(
            "entry_type IN ('fee', 'payment', 'expense', 'time')",
            name="ck_workspace_ledger_entries_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'posted', 'reversed')",
            name="ck_workspace_ledger_entries_status",
        ),
        CheckConstraint("amount >= 0", name="ck_workspace_ledger_entries_amount"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    client_id = Column(String, nullable=True, index=True)
    entry_type = Column(String(16), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    duration_minutes = Column(Integer, nullable=True)
    description = Column(String(500), nullable=False)
    status = Column(String(16), nullable=False, default="draft", index=True)
    manual_payment_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    manual_payment_confirmed_by_user_id = Column(String, nullable=True)
    manual_confirmation_reason = Column(String(500), nullable=True)
    reversal_of_id = Column(String, nullable=True, index=True)
    reversal_reason = Column(String(500), nullable=True)
    request_id = Column(String(36), nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
