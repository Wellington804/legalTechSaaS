"""Case communication and client portal, tenant isolated."""
from alembic import op
import sqlalchemy as sa

revision = "20260827_0005"
down_revision = "20260827_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_notification_delivery_tenant_id", "notification_deliveries", ["tenant_id", "id"])
    op.create_table("tenant_channels",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evolution_instance_id", sa.String(128), unique=True),
        sa.Column("evolution_api_key_encrypted", sa.Text()), sa.Column("evolution_token_encrypted", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("case_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False), sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False), sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("delivery_id", sa.String()),
        sa.Column("created_by_user_id", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "delivery_id"], ["notification_deliveries.tenant_id", "notification_deliveries.id"], name="fk_case_message_delivery_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        sa.UniqueConstraint("delivery_id", name="uq_case_message_delivery"),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_case_message_request"),
        sa.CheckConstraint("channel IN ('portal','email','whatsapp')", name="ck_case_message_channel"),
        sa.CheckConstraint("direction IN ('inbound','outbound')", name="ck_case_message_direction"))
    op.create_table("portal_grants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False), sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("session_hash", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        sa.UniqueConstraint("tenant_id", "id", name="uq_portal_grants_tenant_id"))
    op.create_table("portal_checklist",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("document_id", sa.String()), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"]))
    op.alter_column("workspace_document_versions", "created_by_user_id", existing_type=sa.String(), nullable=True)
    op.add_column("workspace_document_versions", sa.Column("created_by_portal_grant_id", sa.String()))
    op.create_foreign_key("fk_workspace_document_versions_portal_tenant", "workspace_document_versions", "portal_grants", ["tenant_id", "created_by_portal_grant_id"], ["tenant_id", "id"])
    for name in ("tenant_channels", "case_messages", "portal_grants", "portal_checklist"):
        if name != "tenant_channels":
            op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])
            op.create_index(f"ix_{name}_case_id", name, ["case_id"])
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{name}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'''CREATE POLICY tenant_scope ON "{name}" USING
          (tenant_id = nullif(current_setting('app.current_tenant', true), '')) WITH CHECK
          (tenant_id = nullif(current_setting('app.current_tenant', true), ''))'''))
    op.execute("""CREATE FUNCTION public.tenant_channel_webhook_identity(instance text)
      RETURNS TABLE(tenant_id varchar, token_encrypted text) LANGUAGE sql SECURITY DEFINER
      SET search_path = pg_catalog, public AS $$
        SELECT c.tenant_id, c.evolution_token_encrypted FROM public.tenant_channels c
        WHERE c.evolution_instance_id = instance AND c.whatsapp_enabled = true LIMIT 1
      $$""")
    op.execute("REVOKE ALL ON FUNCTION public.tenant_channel_webhook_identity(text) FROM PUBLIC")


def downgrade():
    # Client-uploaded history cannot be losslessly represented by the older schema.
    if op.get_bind().execute(sa.text("SELECT 1 FROM workspace_document_versions WHERE created_by_portal_grant_id IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while client-uploaded document versions exist; restore a compatible backup instead")
    op.drop_column("workspace_document_versions", "created_by_portal_grant_id")
    op.alter_column("workspace_document_versions", "created_by_user_id", existing_type=sa.String(), nullable=False)
    op.execute("DROP FUNCTION public.tenant_channel_webhook_identity(text)")
    for name in ("portal_checklist", "portal_grants", "case_messages", "tenant_channels"):
        op.drop_table(name)
    op.drop_constraint("uq_notification_delivery_tenant_id", "notification_deliveries", type_="unique")
