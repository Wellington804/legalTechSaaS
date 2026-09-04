"""privacy lifecycle and tenant notice settings

Revision ID: 20260829_0011
Revises: 840688cc9b0b
"""
from alembic import op
import sqlalchemy as sa

revision = "20260829_0011"
down_revision = "840688cc9b0b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("privacy_notice_url", sa.String(length=2048), nullable=True))
    op.add_column("tenants", sa.Column("privacy_notice_version", sa.String(length=64), nullable=True))
    op.add_column("tenants", sa.Column("privacy_contact", sa.String(length=320), nullable=True))
    op.add_column("tenants", sa.Column("data_retention_days", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_tenants_data_retention_days", "tenants", "data_retention_days IS NULL OR data_retention_days BETWEEN 30 AND 3650")
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("requested_by_user_id", sa.String(), nullable=True),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("request_type IN ('export', 'deletion', 'anonymization')", name="ck_privacy_requests_type"),
        sa.CheckConstraint("scope IN ('self', 'tenant')", name="ck_privacy_requests_scope"),
        sa.CheckConstraint("status IN ('received', 'in_review', 'completed', 'rejected', 'cancelled')", name="ck_privacy_requests_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_privacy_requests_tenant_id"),
    )
    for column in ("tenant_id", "requested_by_user_id", "request_type", "status"):
        op.create_index(f"ix_privacy_requests_{column}", "privacy_requests", [column])
    policy = "tenant_id = nullif(current_setting('app.current_tenant', true), '')"
    op.execute("ALTER TABLE privacy_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE privacy_requests FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY privacy_requests_tenant_isolation ON privacy_requests USING ({policy}) WITH CHECK ({policy})")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM privacy_requests LIMIT 1)")).scalar():
        raise RuntimeError("Refusing to drop privacy requests with retained data")
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM tenants WHERE privacy_notice_url IS NOT NULL OR privacy_notice_version IS NOT NULL OR privacy_contact IS NOT NULL OR data_retention_days IS NOT NULL LIMIT 1)")).scalar():
        raise RuntimeError("Refusing to drop configured privacy settings")
    op.drop_table("privacy_requests")
    op.drop_constraint("ck_tenants_data_retention_days", "tenants", type_="check")
    for column in ("data_retention_days", "privacy_contact", "privacy_notice_version", "privacy_notice_url"):
        op.drop_column("tenants", column)
