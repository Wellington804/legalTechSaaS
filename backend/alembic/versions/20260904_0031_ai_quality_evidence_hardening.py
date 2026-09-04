"""Harden AI evidence, consent receipts and corpus review.

Revision ID: 20260904_0031
Revises: 20260904_0029
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0031"
down_revision = "20260904_0029"
branch_labels = None
depends_on = None


def _tenant_policy(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "tenant_isolation_{table}" ON "{table}" '
        "USING (tenant_id = current_setting('app.current_tenant', true)) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true))"
    )


def upgrade() -> None:
    # FORCE RLS would hide every tenant row from a non-superuser migration
    # session without app.current_tenant. This is transactional and restored
    # before commit.
    for table in (
        "ai_evaluation_cases",
        "document_intelligence_analyses",
        "document_intelligence_sources",
    ):
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    # Previously approved self-reviews cannot remain trusted. Keep them for audit,
    # but retire them before enforcing the independent-review invariant.
    op.execute(
        "UPDATE ai_evaluation_cases SET status = 'retired' "
        "WHERE status IN ('approved','rejected') AND reviewed_by_user_id = created_by_user_id"
    )
    op.execute(
        "UPDATE ai_evaluation_cases SET reviewed_by_user_id = NULL, reviewed_at = NULL, review_note = NULL "
        "WHERE status = 'draft'"
    )
    op.execute(
        "WITH ranked AS ("
        " SELECT id, row_number() OVER (PARTITION BY tenant_id, name ORDER BY version DESC, updated_at DESC, id) AS rn"
        " FROM ai_evaluation_cases WHERE status = 'approved'"
        ") UPDATE ai_evaluation_cases c SET status = 'retired' FROM ranked r "
        "WHERE c.id = r.id AND r.rn > 1"
    )
    op.create_check_constraint(
        "ck_ai_evaluation_cases_independent_review",
        "ai_evaluation_cases",
        "(status = 'draft' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) "
        "OR status = 'retired' OR "
        "(status IN ('approved','rejected') AND reviewed_by_user_id IS NOT NULL "
        "AND reviewed_at IS NOT NULL AND reviewed_by_user_id <> created_by_user_id)",
    )
    op.create_index(
        "uq_ai_evaluation_cases_approved_name", "ai_evaluation_cases",
        ["tenant_id", "name"], unique=True,
        postgresql_where=sa.text("status = 'approved'"),
    )

    op.add_column("document_intelligence_analyses", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.add_column("document_intelligence_analyses", sa.Column("coverage", sa.JSON(), nullable=True))
    op.execute("UPDATE document_intelligence_analyses SET request_fingerprint = snapshot_hash WHERE request_fingerprint IS NULL")
    op.alter_column("document_intelligence_analyses", "request_fingerprint", nullable=False)

    for name, type_ in (
        ("binary_sha256", sa.String(64)),
        ("text_sha256", sa.String(64)),
        ("extractor", sa.String(80)),
        ("ocr_status", sa.String(24)),
    ):
        op.add_column("document_intelligence_sources", sa.Column(name, type_, nullable=True))
    op.execute(
        "UPDATE document_intelligence_sources s SET "
        "text_sha256 = s.sha256, "
        "binary_sha256 = COALESCE(d.sha256_hash, s.sha256), "
        "extractor = 'legacy-unrecorded', ocr_status = 'unknown' "
        "FROM workspace_documents d "
        "WHERE d.tenant_id = s.tenant_id AND d.id = s.document_id"
    )
    for name in ("text_sha256", "extractor", "ocr_status"):
        op.alter_column("document_intelligence_sources", name, nullable=False)

    for table in (
        "ai_evaluation_cases",
        "document_intelligence_analyses",
        "document_intelligence_sources",
    ):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')

    op.create_table(
        "document_intelligence_consent_receipts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("analysis_id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("purpose", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("document_manifest", sa.JSON(), nullable=False),
        sa.Column("receipt_hash", sa.String(64), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_document_intelligence_consent_receipts_tenant_id"),
        sa.UniqueConstraint("tenant_id", "analysis_id", name="uq_document_intelligence_consent_analysis"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "analysis_id"],
            ["document_intelligence_analyses.tenant_id", "document_intelligence_analyses.id"],
            name="fk_document_intelligence_consent_analysis_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"],
            name="fk_document_intelligence_consent_user_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_document_intelligence_consent_case_tenant", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_document_intelligence_consent_receipts_tenant_id", "document_intelligence_consent_receipts", ["tenant_id"])
    op.create_index("ix_document_intelligence_consent_receipts_analysis_id", "document_intelligence_consent_receipts", ["analysis_id"])
    _tenant_policy("document_intelligence_consent_receipts")
    op.execute(
        "CREATE FUNCTION prevent_document_intelligence_consent_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'consent receipts are immutable'; END; $$"
    )
    op.execute(
        "CREATE TRIGGER document_intelligence_consent_immutable "
        "BEFORE UPDATE OR DELETE ON document_intelligence_consent_receipts "
        "FOR EACH ROW EXECUTE FUNCTION prevent_document_intelligence_consent_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS document_intelligence_consent_immutable ON document_intelligence_consent_receipts")
    op.execute("DROP FUNCTION IF EXISTS prevent_document_intelligence_consent_mutation()")
    op.drop_table("document_intelligence_consent_receipts")
    for name in ("ocr_status", "extractor", "text_sha256", "binary_sha256"):
        op.drop_column("document_intelligence_sources", name)
    op.drop_column("document_intelligence_analyses", "coverage")
    op.drop_column("document_intelligence_analyses", "request_fingerprint")
    op.drop_index("uq_ai_evaluation_cases_approved_name", table_name="ai_evaluation_cases")
    op.drop_constraint("ck_ai_evaluation_cases_independent_review", "ai_evaluation_cases", type_="check")
