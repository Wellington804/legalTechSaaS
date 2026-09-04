"""Consent-bound encrypted Web Push subscriptions and durable outbox.

Revision ID: 20260828_0007
Revises: 20260828_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0007"
down_revision = "20260828_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_auth_sessions_push_owner", "auth_sessions", ["tenant_id", "user_id", "id"])
    op.create_table("push_subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("auth_session_id", sa.String(), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("vapid_key_hash", sa.String(64), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("endpoint_hash", name="uq_push_subscription_endpoint"),
        sa.UniqueConstraint("tenant_id", "user_id", "id", name="uq_push_subscription_owner"),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_push_subscription_user"),
        sa.ForeignKeyConstraint(["tenant_id", "user_id", "auth_session_id"], ["auth_sessions.tenant_id", "auth_sessions.user_id", "auth_sessions.id"], name="fk_push_subscription_session"),
    )
    for field in ("tenant_id", "user_id", "auth_session_id"):
        op.create_index(f"ix_push_subscriptions_{field}", "push_subscriptions", [field])
    op.create_table("push_deliveries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("subscription_id", "event_key", name="uq_push_delivery_event"),
        sa.ForeignKeyConstraint(["tenant_id", "user_id", "subscription_id"], ["push_subscriptions.tenant_id", "push_subscriptions.user_id", "push_subscriptions.id"], name="fk_push_delivery_subscription"),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_push_delivery_case"),
        sa.ForeignKeyConstraint(["tenant_id", "task_id"], ["workspace_tasks.tenant_id", "workspace_tasks.id"], name="fk_push_delivery_task"),
        sa.CheckConstraint("kind IN ('task_assigned','portal_message','portal_document','test')", name="ck_push_delivery_kind"),
        sa.CheckConstraint("status IN ('queued','processing','accepted','failed','expired','cancelled','unknown')", name="ck_push_delivery_status"),
    )
    for field in ("tenant_id", "subscription_id", "status"):
        op.create_index(f"ix_push_deliveries_{field}", "push_deliveries", [field])
    op.execute("CREATE INDEX ix_push_deliveries_recovery ON push_deliveries (status, next_attempt_at, processing_started_at) WHERE status IN ('queued', 'processing')")
    for table in ("push_subscriptions", "push_deliveries"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING (tenant_id = current_setting('app.current_tenant', true)) WITH CHECK (tenant_id = current_setting('app.current_tenant', true))")
    op.execute("""
        CREATE FUNCTION push_recovery_candidates(max_rows integer, timeout_seconds integer)
        RETURNS TABLE(delivery_id text, tenant_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT delivery.id, delivery.tenant_id FROM public.push_deliveries delivery
        WHERE (delivery.status = 'queued' AND (delivery.next_attempt_at IS NULL OR delivery.next_attempt_at <= statement_timestamp()))
           OR (delivery.status = 'processing' AND (delivery.processing_started_at IS NULL
               OR delivery.processing_started_at <= statement_timestamp() - make_interval(secs => GREATEST($2, 120))))
        ORDER BY COALESCE(delivery.next_attempt_at, delivery.processing_started_at, delivery.created_at), delivery.id
        LIMIT LEAST(GREATEST($1, 1), 500) $$
    """)
    op.execute("REVOKE ALL ON FUNCTION push_recovery_candidates(integer, integer) FROM PUBLIC")


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM push_subscriptions")).scalar()
    if count:
        raise RuntimeError("Export/revoke existing push subscriptions before destructive downgrade")
    op.execute("DROP FUNCTION push_recovery_candidates(integer, integer)")
    op.drop_table("push_deliveries")
    op.drop_table("push_subscriptions")
    op.drop_constraint("uq_auth_sessions_push_owner", "auth_sessions", type_="unique")
