"""Persist tenant-scoped CRM opportunities.

Revision ID: 20260905_0032
Revises: 20260904_0031
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0032"
down_revision = "20260904_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_opportunities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("estimated_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("next_action", sa.String(length=500), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("intake_id", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_crm_opportunities_tenant_id"),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_crm_opportunities_request"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_crm_opportunities_client_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_crm_opportunities_case_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "intake_id"], ["public_intakes.tenant_id", "public_intakes.id"],
            name="fk_crm_opportunities_intake_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "owner_user_id"], ["users.tenant_id", "users.id"],
            name="fk_crm_opportunities_owner_tenant", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_crm_opportunities_creator_tenant", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("stage IN ('new','qualified','proposal','won','lost')", name="ck_crm_opportunities_stage"),
        sa.CheckConstraint(
            "source IN ('manual','intake','referral','website','whatsapp','email','other')",
            name="ck_crm_opportunities_source",
        ),
        sa.CheckConstraint("estimated_value IS NULL OR estimated_value >= 0", name="ck_crm_opportunities_estimated_value"),
        sa.CheckConstraint("next_action_at IS NULL OR next_action IS NOT NULL", name="ck_crm_opportunities_next_action"),
    )
    op.create_index(
        "ix_crm_opportunities_pipeline", "crm_opportunities",
        ["tenant_id", "archived_at", "stage", "next_action_at"],
    )
    op.create_index("ix_crm_opportunities_owner", "crm_opportunities", ["tenant_id", "owner_user_id"])
    op.create_index("ix_crm_opportunities_client", "crm_opportunities", ["tenant_id", "client_id"])
    op.create_index("ix_crm_opportunities_case", "crm_opportunities", ["tenant_id", "case_id"])
    op.create_index("ix_crm_opportunities_intake", "crm_opportunities", ["tenant_id", "intake_id"])
    op.execute("ALTER TABLE crm_opportunities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crm_opportunities FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY crm_opportunities_tenant_isolation ON crm_opportunities "
        "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')) "
        "WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true), ''))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS crm_opportunities_tenant_isolation ON crm_opportunities")
    op.drop_table("crm_opportunities")
