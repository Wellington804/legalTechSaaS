"""Persist reviewed AI evaluations and document intelligence.

Revision ID: 20260904_0026
Revises: 20260904_0025
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0026"
down_revision = "20260904_0025"
branch_labels = None
depends_on = None


def _tenant_policy(table: str) -> None:
    policy = "tenant_id = nullif(current_setting('app.current_tenant', true), '')"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING ({policy}) WITH CHECK ({policy})")


def upgrade() -> None:
    op.create_table(
        "ai_evaluation_cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("legal_area", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_evaluation_cases_tenant_id"),
        sa.UniqueConstraint("tenant_id", "name", "version", name="uq_ai_evaluation_cases_version"),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_ai_eval_cases_creator_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "reviewed_by_user_id"], ["users.tenant_id", "users.id"], name="fk_ai_eval_cases_reviewer_tenant"),
        sa.CheckConstraint("status IN ('draft','approved','rejected','retired')", name="ck_ai_evaluation_cases_status"),
        sa.CheckConstraint("version > 0", name="ck_ai_evaluation_cases_version"),
    )
    op.create_index("ix_ai_evaluation_cases_tenant_id", "ai_evaluation_cases", ["tenant_id"])
    op.create_index("ix_ai_evaluation_cases_status", "ai_evaluation_cases", ["status"])

    op.create_table(
        "ai_evaluation_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("corpus_hash", sa.String(64), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("case_ids", sa.JSON(), nullable=False),
        sa.Column("aggregate_metrics", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("requested_by_user_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_evaluation_runs_tenant_id"),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_ai_evaluation_runs_request"),
        sa.ForeignKeyConstraint(["tenant_id", "requested_by_user_id"], ["users.tenant_id", "users.id"], name="fk_ai_eval_runs_requester_tenant"),
        sa.CheckConstraint("status IN ('queued','running','completed','failed')", name="ck_ai_evaluation_runs_status"),
    )
    op.create_index("ix_ai_evaluation_runs_tenant_id", "ai_evaluation_runs", ["tenant_id"])
    op.create_index("ix_ai_evaluation_runs_status", "ai_evaluation_runs", ["status"])

    op.create_table(
        "ai_evaluation_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("case_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("output_hash", sa.String(64), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_evaluation_results_tenant_id"),
        sa.UniqueConstraint("tenant_id", "run_id", "case_id", name="uq_ai_evaluation_results_case"),
        sa.ForeignKeyConstraint(["tenant_id", "run_id"], ["ai_evaluation_runs.tenant_id", "ai_evaluation_runs.id"], name="fk_ai_eval_results_run_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["ai_evaluation_cases.tenant_id", "ai_evaluation_cases.id"], name="fk_ai_eval_results_case_tenant", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('completed','failed','stale')", name="ck_ai_evaluation_results_status"),
    )
    op.create_index("ix_ai_evaluation_results_tenant_id", "ai_evaluation_results", ["tenant_id"])
    op.create_index("ix_ai_evaluation_results_run_id", "ai_evaluation_results", ["run_id"])
    op.create_index("ix_ai_evaluation_results_case_id", "ai_evaluation_results", ["case_id"])

    op.create_table(
        "document_intelligence_analyses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("evidence_sources", sa.JSON(), nullable=True),
        sa.Column("result_hash", sa.String(64), nullable=True),
        sa.Column("classifications", sa.JSON(), nullable=True),
        sa.Column("timeline", sa.JSON(), nullable=True),
        sa.Column("contradiction_groups", sa.JSON(), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("requested_by_user_id", sa.String(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_document_intelligence_analyses_tenant_id"),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_document_intelligence_request"),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_document_intelligence_case_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "requested_by_user_id"], ["users.tenant_id", "users.id"], name="fk_document_intelligence_requester_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "reviewed_by_user_id"], ["users.tenant_id", "users.id"], name="fk_document_intelligence_reviewer_tenant"),
        sa.CheckConstraint("status IN ('queued','processing','review_required','approved','rejected','failed','stale')", name="ck_document_intelligence_status"),
    )
    op.create_index("ix_document_intelligence_analyses_tenant_id", "document_intelligence_analyses", ["tenant_id"])
    op.create_index("ix_document_intelligence_analyses_case_id", "document_intelligence_analyses", ["case_id"])
    op.create_index("ix_document_intelligence_analyses_status", "document_intelligence_analyses", ["status"])

    op.create_table(
        "document_intelligence_sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("analysis_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_document_intelligence_sources_tenant_id"),
        sa.UniqueConstraint("tenant_id", "analysis_id", "document_id", name="uq_document_intelligence_source_document"),
        sa.ForeignKeyConstraint(["tenant_id", "analysis_id"], ["document_intelligence_analyses.tenant_id", "document_intelligence_analyses.id"], name="fk_document_intelligence_sources_analysis_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"], name="fk_document_intelligence_sources_document_tenant", ondelete="RESTRICT"),
    )
    op.create_index("ix_document_intelligence_sources_tenant_id", "document_intelligence_sources", ["tenant_id"])
    op.create_index("ix_document_intelligence_sources_analysis_id", "document_intelligence_sources", ["analysis_id"])
    op.create_index("ix_document_intelligence_sources_document_id", "document_intelligence_sources", ["document_id"])

    for table in (
        "ai_evaluation_cases",
        "ai_evaluation_runs",
        "ai_evaluation_results",
        "document_intelligence_analyses",
        "document_intelligence_sources",
    ):
        _tenant_policy(table)


def downgrade() -> None:
    for table in (
        "document_intelligence_sources",
        "document_intelligence_analyses",
        "ai_evaluation_results",
        "ai_evaluation_runs",
        "ai_evaluation_cases",
    ):
        op.drop_table(table)
