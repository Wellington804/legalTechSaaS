"""Calendar feeds and document review workflow.

Revision ID: 20260902_0019
Revises: 20260902_0018
"""

from alembic import op
import sqlalchemy as sa


revision = "20260902_0019"
down_revision = "20260902_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("calendar_feed_token_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("calendar_feed_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("case_messages", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workspace_documents", sa.Column("review_status", sa.String(16), nullable=False, server_default="draft"))
    op.add_column("workspace_documents", sa.Column("review_version", sa.Integer(), nullable=True))
    op.add_column("workspace_documents", sa.Column("reviewed_by_user_id", sa.String(), nullable=True))
    op.add_column("workspace_documents", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_workspace_documents_review_status", "workspace_documents", ["review_status"])
    op.create_foreign_key(
        "fk_workspace_documents_reviewer_tenant", "workspace_documents", "users",
        ["tenant_id", "reviewed_by_user_id"], ["tenant_id", "id"],
    )
    op.create_check_constraint(
        "ck_workspace_documents_review_status", "workspace_documents",
        "review_status IN ('draft','in_review','approved','final')",
    )
    op.create_table(
        "workspace_document_reviews",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_document_reviews_tenant_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"],
            name="fk_workspace_document_reviews_document_tenant", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_workspace_document_reviews_user_tenant",
        ),
        sa.CheckConstraint(
            "status IN ('comment','in_review','approved','final','reopened')",
            name="ck_workspace_document_reviews_status",
        ),
    )
    op.create_index("ix_workspace_document_reviews_tenant_id", "workspace_document_reviews", ["tenant_id"])
    op.create_index("ix_workspace_document_reviews_document_id", "workspace_document_reviews", ["document_id"])
    op.execute("ALTER TABLE workspace_document_reviews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_document_reviews FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY workspace_document_reviews_tenant_isolation ON workspace_document_reviews USING (tenant_id = current_setting('app.current_tenant', true)) WITH CHECK (tenant_id = current_setting('app.current_tenant', true))")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM workspace_document_reviews) OR EXISTS (SELECT 1 FROM users WHERE calendar_feed_token_hash IS NOT NULL) OR EXISTS (SELECT 1 FROM workspace_documents WHERE review_status <> 'draft')")).scalar():
        raise RuntimeError("Refusing to discard calendar subscriptions or document review history")
    op.drop_table("workspace_document_reviews")
    op.drop_constraint("ck_workspace_documents_review_status", "workspace_documents", type_="check")
    op.drop_constraint("fk_workspace_documents_reviewer_tenant", "workspace_documents", type_="foreignkey")
    op.drop_index("ix_workspace_documents_review_status", table_name="workspace_documents")
    for column in ("reviewed_at", "reviewed_by_user_id", "review_version", "review_status"):
        op.drop_column("workspace_documents", column)
    op.drop_column("case_messages", "read_at")
    op.drop_column("users", "calendar_feed_created_at")
    op.drop_column("users", "calendar_feed_token_hash")
