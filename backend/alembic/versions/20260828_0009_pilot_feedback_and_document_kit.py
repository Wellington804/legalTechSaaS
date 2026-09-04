"""Explicit pilot feedback and immutable document-kit request receipts."""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0009"
down_revision = "20260828_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pilot_feedback",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("area", sa.String(24), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("release", sa.String(100), nullable=False),
        sa.Column("completed_steps", sa.JSON(), nullable=False),
        sa.Column("help_steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", "request_id", name="uq_pilot_feedback_request"),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_pilot_feedback_owner"),
        sa.CheckConstraint("kind IN ('problem','weekly')", name="ck_pilot_feedback_kind"),
    )
    op.create_index("ix_pilot_feedback_tenant_id", "pilot_feedback", ["tenant_id"])
    op.create_index("ix_pilot_feedback_user_id", "pilot_feedback", ["user_id"])
    op.create_table("document_kit_receipts",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"], ondelete="RESTRICT"),
    )
    for table in ("pilot_feedback", "document_kit_receipts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING (tenant_id=current_setting('app.current_tenant',true)) WITH CHECK (tenant_id=current_setting('app.current_tenant',true))")


def downgrade():
    for table in ("pilot_feedback", "document_kit_receipts"):
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar():
            raise RuntimeError("Refusing to discard pilot feedback/document request history")
    op.drop_table("document_kit_receipts")
    op.drop_table("pilot_feedback")
