"""Personal, tenant-scoped AI conversation history."""
from alembic import op
import sqlalchemy as sa

revision = "20260902_0021"
down_revision = "20260902_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("context_kind", sa.String(16), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_ai_conversations_user_tenant", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_conversations_tenant_id"),
        sa.CheckConstraint("context_kind IN ('global','client','case','document','library','branding')", name="ck_ai_conversations_context_kind"),
        sa.CheckConstraint("retention_days IN (30,90,365)", name="ck_ai_conversations_retention_days"),
    )
    op.create_index("ix_ai_conversations_tenant_id", "ai_conversations", ["tenant_id"])
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_expires_at", "ai_conversations", ["expires_at"])
    op.create_table(
        "ai_conversation_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=True),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "conversation_id"], ["ai_conversations.tenant_id", "ai_conversations.id"], name="fk_ai_messages_conversation_tenant", ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ai_conversation_messages_tenant_id"),
        sa.UniqueConstraint("tenant_id", "conversation_id", "sequence", name="uq_ai_conversation_message_sequence"),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_ai_conversation_messages_role"),
    )
    op.create_index("ix_ai_conversation_messages_tenant_id", "ai_conversation_messages", ["tenant_id"])
    op.create_index("ix_ai_conversation_messages_conversation_id", "ai_conversation_messages", ["conversation_id"])
    for table in ("ai_conversations", "ai_conversation_messages"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')) WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true), ''))")
    op.execute("""
        CREATE FUNCTION purge_expired_ai_conversations(max_rows integer)
        RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE removed integer;
        BEGIN
          WITH expired AS (
            SELECT id FROM ai_conversations WHERE expires_at <= now() ORDER BY expires_at LIMIT greatest(1, least(max_rows, 1000))
          )
          DELETE FROM ai_conversations WHERE id IN (SELECT id FROM expired);
          GET DIAGNOSTICS removed = ROW_COUNT;
          RETURN removed;
        END $$
    """)
    op.execute("REVOKE ALL ON FUNCTION purge_expired_ai_conversations(integer) FROM PUBLIC")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM ai_conversations)")).scalar():
        raise RuntimeError("Refusing to discard AI conversation history")
    op.execute("DROP FUNCTION IF EXISTS purge_expired_ai_conversations(integer)")
    op.drop_table("ai_conversation_messages")
    op.drop_table("ai_conversations")
