"""Persist authenticated inbound email and WhatsApp messages.

Revision ID: 20260904_0029
Revises: 20260904_0028
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0029"
down_revision = "20260904_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_channels",
        sa.Column("email_inbound_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("tenant_channels", sa.Column("email_inbound_token_encrypted", sa.Text()))
    op.add_column("tenant_channels", sa.Column("email_inbound_token_hash", sa.String(length=64)))
    op.create_unique_constraint(
        "uq_tenant_channels_email_inbound_token_hash",
        "tenant_channels",
        ["email_inbound_token_hash"],
    )
    op.create_unique_constraint(
        "uq_case_messages_tenant_id", "case_messages", ["tenant_id", "id"]
    )

    op.create_table(
        "communication_inbox_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("event_digest", sa.String(length=64), nullable=False),
        sa.Column("provider_message_hash", sa.String(length=64), nullable=False),
        sa.Column("sender_address", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="unmatched"),
        sa.Column("matched_client_id", sa.String()),
        sa.Column("linked_case_id", sa.String()),
        sa.Column("linked_message_id", sa.String()),
        sa.Column("reviewed_by_user_id", sa.String()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_communication_inbox_tenant_id"),
        sa.UniqueConstraint("provider", "event_digest", name="uq_communication_inbox_provider_event"),
        sa.CheckConstraint("channel IN ('email','whatsapp')", name="ck_communication_inbox_channel"),
        sa.CheckConstraint(
            "status IN ('unmatched','ambiguous','linked','dismissed')",
            name="ck_communication_inbox_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "matched_client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_communication_inbox_client_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "linked_case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_communication_inbox_case_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "linked_message_id"],
            ["case_messages.tenant_id", "case_messages.id"],
            name="fk_communication_inbox_message_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reviewed_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_communication_inbox_reviewer_tenant",
        ),
    )
    op.create_index(
        "ix_communication_inbox_tenant_status_received",
        "communication_inbox_items",
        ["tenant_id", "status", "received_at"],
    )
    for column in ("tenant_id", "channel", "status", "matched_client_id", "linked_case_id", "received_at"):
        op.create_index(f"ix_communication_inbox_items_{column}", "communication_inbox_items", [column])
    op.execute("ALTER TABLE communication_inbox_items ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY communication_inbox_items_tenant_isolation ON communication_inbox_items "
        "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')) "
        "WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true), ''))"
    )
    op.execute(
        """
        CREATE FUNCTION public.tenant_channel_email_inbound_identity(token_hash text)
        RETURNS TABLE(tenant_id varchar) LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
          SELECT channel.tenant_id
          FROM public.tenant_channels channel
          WHERE channel.email_inbound_token_hash = token_hash
            AND channel.email_inbound_enabled = true
          LIMIT 1
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.tenant_channel_email_inbound_identity(text) FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION public.tenant_channel_email_inbound_identity(text)")
    op.drop_table("communication_inbox_items")
    op.drop_constraint("uq_case_messages_tenant_id", "case_messages", type_="unique")
    op.drop_constraint(
        "uq_tenant_channels_email_inbound_token_hash", "tenant_channels", type_="unique"
    )
    op.drop_column("tenant_channels", "email_inbound_token_hash")
    op.drop_column("tenant_channels", "email_inbound_token_encrypted")
    op.drop_column("tenant_channels", "email_inbound_enabled")
