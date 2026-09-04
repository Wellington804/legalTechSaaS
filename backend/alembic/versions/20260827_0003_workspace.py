"""Persisted tenant-scoped legal workspace.

Revision ID: 20260827_0003
Revises: 20260827_0002
Create Date: 2026-08-27
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0003"
down_revision: str | None = "20260827_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _tenant_table(table: str) -> None:
    policy = "tenant_id = nullif(current_setting('app.current_tenant', true), '')"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        f"USING ({policy}) WITH CHECK ({policy})"
    )


def upgrade() -> None:
    # Composite tenant/id targets prevent a child record from referencing a different tenant.
    op.create_unique_constraint("uq_users_tenant_id", "users", ["tenant_id", "id"])

    op.create_table(
        "workspace_clients",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("tax_id", sa.String(length=20), nullable=True),
        sa.Column("stage", sa.String(length=16), nullable=False, server_default="lead"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_clients_tenant_id"),
        sa.CheckConstraint("stage IN ('lead', 'prospect', 'client', 'inactive')", name="ck_workspace_clients_stage"),
    )
    op.create_index("ix_workspace_clients_tenant_id", "workspace_clients", ["tenant_id"])
    op.create_index("ix_workspace_clients_stage", "workspace_clients", ["stage"])
    op.create_index("ix_workspace_clients_tenant_tax_id", "workspace_clients", ["tenant_id", "tax_id"])

    op.create_table(
        "workspace_cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=True),
        sa.Column("court", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("responsible_user_id", sa.String(), nullable=False),
        sa.Column("restricted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_cases_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"], name="fk_workspace_cases_client_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "responsible_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_cases_responsible_user_tenant"
        ),
        sa.CheckConstraint("status IN ('open', 'paused', 'closed', 'archived')", name="ck_workspace_cases_status"),
    )
    for name, columns in (
        ("ix_workspace_cases_tenant_id", ["tenant_id"]),
        ("ix_workspace_cases_client_id", ["client_id"]),
        ("ix_workspace_cases_status", ["status"]),
        ("ix_workspace_cases_responsible_user_id", ["responsible_user_id"]),
        ("ix_workspace_cases_tenant_number", ["tenant_id", "number"]),
    ):
        op.create_index(name, "workspace_cases", columns)

    op.create_table(
        "workspace_case_access",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_case_access_tenant_id"),
        sa.UniqueConstraint("tenant_id", "case_id", "user_id", name="uq_workspace_case_access_user"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_case_access_case_tenant", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_case_access_user_tenant"
        ),
    )
    for column in ("tenant_id", "case_id", "user_id"):
        op.create_index(f"ix_workspace_case_access_{column}", "workspace_case_access", [column])

    op.create_table(
        "workspace_case_parties",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tax_id", sa.String(length=20), nullable=True),
        sa.Column("side", sa.String(length=16), nullable=False, server_default="third_party"),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_case_parties_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_case_parties_case_tenant", ondelete="CASCADE"
        ),
        sa.CheckConstraint("side IN ('client', 'opponent', 'third_party')", name="ck_workspace_case_parties_side"),
    )
    for column in ("tenant_id", "case_id"):
        op.create_index(f"ix_workspace_case_parties_{column}", "workspace_case_parties", [column])
    op.create_index("ix_workspace_case_parties_tenant_tax_id", "workspace_case_parties", ["tenant_id", "tax_id"])

    op.create_table(
        "workspace_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="task"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_user_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("manually_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_tasks_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_tasks_case_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assigned_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_tasks_assigned_user_tenant"
        ),
        sa.CheckConstraint("kind IN ('task', 'deadline', 'hearing')", name="ck_workspace_tasks_kind"),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'cancelled')", name="ck_workspace_tasks_status"),
    )
    for column in ("tenant_id", "case_id", "due_at", "assigned_user_id", "status"):
        op.create_index(f"ix_workspace_tasks_{column}", "workspace_tasks", [column])

    op.create_table(
        "workspace_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="document"),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_content", sa.LargeBinary(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_documents_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_documents_case_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"], name="fk_workspace_documents_client_tenant", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("kind IN ('document', 'template', 'note', 'evidence')", name="ck_workspace_documents_kind"),
    )
    for column in ("tenant_id", "case_id", "client_id", "kind"):
        op.create_index(f"ix_workspace_documents_{column}", "workspace_documents", [column])

    op.create_table(
        "workspace_document_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_content", sa.LargeBinary(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_document_versions_tenant_id"),
        sa.UniqueConstraint("tenant_id", "document_id", "version", name="uq_workspace_document_versions_number"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"], name="fk_workspace_document_versions_document_tenant", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_document_versions_creator_tenant"
        ),
    )
    for column in ("tenant_id", "document_id"):
        op.create_index(f"ix_workspace_document_versions_{column}", "workspace_document_versions", [column])

    op.create_table(
        "workspace_library_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_library_entries_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_library_entries_creator_tenant"
        ),
    )
    op.create_index("ix_workspace_library_entries_tenant_id", "workspace_library_entries", ["tenant_id"])

    op.create_table(
        "workspace_publications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("published_at", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_user_id", sa.String(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_publications_tenant_id"),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_workspace_publications_dedupe"),
        sa.CheckConstraint("source_kind IN ('manual', 'datajud')", name="ck_workspace_publications_source_kind"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_publications_case_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_publications_creator_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "acknowledged_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_publications_acknowledger_tenant"
        ),
    )
    for column in ("tenant_id", "case_id", "published_at"):
        op.create_index(f"ix_workspace_publications_{column}", "workspace_publications", [column])

    op.create_table(
        "workspace_ledger_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("entry_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="BRL"),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("manual_payment_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manual_payment_confirmed_by_user_id", sa.String(), nullable=True),
        sa.Column("manual_confirmation_reason", sa.String(length=500), nullable=True),
        sa.Column("reversal_of_id", sa.String(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_ledger_entries_tenant_id"),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_workspace_ledger_entries_request"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_ledger_entries_case_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"], name="fk_workspace_ledger_entries_client_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reversal_of_id"], ["workspace_ledger_entries.tenant_id", "workspace_ledger_entries.id"], name="fk_workspace_ledger_entries_reversal_tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_ledger_entries_creator_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "manual_payment_confirmed_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_ledger_entries_confirmer_tenant"
        ),
        sa.CheckConstraint("entry_type IN ('fee', 'payment', 'expense', 'time')", name="ck_workspace_ledger_entries_type"),
        sa.CheckConstraint("status IN ('draft', 'posted', 'reversed')", name="ck_workspace_ledger_entries_status"),
        sa.CheckConstraint("amount >= 0", name="ck_workspace_ledger_entries_amount"),
    )
    for column in ("tenant_id", "case_id", "client_id", "entry_type", "status", "reversal_of_id"):
        op.create_index(f"ix_workspace_ledger_entries_{column}", "workspace_ledger_entries", [column])

    for table in (
        "workspace_clients",
        "workspace_cases",
        "workspace_case_access",
        "workspace_case_parties",
        "workspace_tasks",
        "workspace_documents",
        "workspace_document_versions",
        "workspace_library_entries",
        "workspace_publications",
        "workspace_ledger_entries",
    ):
        _tenant_table(table)


def downgrade() -> None:
    tables = (
        "workspace_ledger_entries",
        "workspace_publications",
        "workspace_library_entries",
        "workspace_document_versions",
        "workspace_documents",
        "workspace_tasks",
        "workspace_case_parties",
        "workspace_case_access",
        "workspace_cases",
        "workspace_clients",
    )
    for table in tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    for table in tables:
        op.drop_table(table)
    op.drop_constraint("uq_users_tenant_id", "users", type_="unique")
