"""Private manual reminders and idempotent operational checklists/results.

Revision ID: 20260828_0008
Revises: 20260828_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0008"
down_revision = "20260828_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workspace_tasks", sa.Column("location", sa.String(300), nullable=True))
    op.add_column("workspace_tasks", sa.Column("contact", sa.String(200), nullable=True))
    op.add_column("workspace_tasks", sa.Column("notes", sa.Text(), nullable=True))
    op.create_table("routine_actions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", "request_id", name="uq_routine_action_request"),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_routine_action_user"),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_routine_action_case"),
        sa.CheckConstraint("kind IN ('checklist','outcome')", name="ck_routine_action_kind"))
    op.create_index("ix_routine_actions_tenant_id", "routine_actions", ["tenant_id"])
    op.create_table("routine_reminders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("task_revision", sa.Integer(), nullable=False),
        sa.Column("due_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="scheduled"),
        sa.Column("push_requested", sa.String(16), nullable=False, server_default="not_requested"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", "id", name="uq_routine_reminder_owner"),
        sa.ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_routine_reminder_user"),
        sa.ForeignKeyConstraint(["tenant_id", "task_id"], ["workspace_tasks.tenant_id", "workspace_tasks.id"], name="fk_routine_reminder_task"),
        sa.CheckConstraint("status IN ('scheduled','due','cancelled')", name="ck_routine_reminder_status"),
        sa.CheckConstraint("push_requested IN ('not_requested','pending','unavailable')", name="ck_routine_reminder_push_requested"))
    op.create_index("ix_routine_reminders_tenant_id", "routine_reminders", ["tenant_id"])
    op.create_index("uq_routine_reminder_active", "routine_reminders", ["tenant_id", "user_id", "task_id"], unique=True,
        postgresql_where=sa.text("status IN ('scheduled','due')"))
    op.create_index("ix_routine_reminder_due", "routine_reminders", ["remind_at"], postgresql_where=sa.text("status = 'scheduled'"))
    op.add_column("push_deliveries", sa.Column("reminder_id", sa.String(), nullable=True))
    op.create_index("ix_push_deliveries_reminder_id", "push_deliveries", ["reminder_id"])
    op.create_foreign_key("fk_push_delivery_reminder", "push_deliveries", "routine_reminders",
        ["tenant_id", "user_id", "reminder_id"], ["tenant_id", "user_id", "id"])
    op.drop_constraint("ck_push_delivery_kind", "push_deliveries", type_="check")
    op.create_check_constraint("ck_push_delivery_kind", "push_deliveries", "kind IN ('task_assigned','portal_message','portal_document','test','task_reminder')")
    for table in ("routine_actions", "routine_reminders"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING (tenant_id = current_setting('app.current_tenant', true)) WITH CHECK (tenant_id = current_setting('app.current_tenant', true))")
    op.execute("""
        CREATE FUNCTION routine_reminder_candidates(max_rows integer)
        RETURNS TABLE(reminder_id text, tenant_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT reminder.id, reminder.tenant_id FROM public.routine_reminders reminder
        WHERE reminder.status = 'scheduled' AND reminder.remind_at <= statement_timestamp()
        ORDER BY reminder.remind_at, reminder.id LIMIT LEAST(GREATEST($1, 1), 500) $$
    """)
    op.execute("REVOKE ALL ON FUNCTION routine_reminder_candidates(integer) FROM PUBLIC")


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT (SELECT count(*) FROM routine_actions) + (SELECT count(*) FROM routine_reminders)")).scalar()
    task_data = op.get_bind().execute(sa.text("SELECT count(*) FROM workspace_tasks WHERE location IS NOT NULL OR contact IS NOT NULL OR notes IS NOT NULL")).scalar()
    if count or task_data:
        raise RuntimeError("Export routine records before destructive downgrade")
    op.execute("DROP FUNCTION routine_reminder_candidates(integer)")
    op.drop_constraint("fk_push_delivery_reminder", "push_deliveries", type_="foreignkey")
    op.drop_column("push_deliveries", "reminder_id")
    op.drop_constraint("ck_push_delivery_kind", "push_deliveries", type_="check")
    op.create_check_constraint("ck_push_delivery_kind", "push_deliveries", "kind IN ('task_assigned','portal_message','portal_document','test')")
    op.drop_table("routine_reminders")
    op.drop_table("routine_actions")
    for column in ("notes", "contact", "location"):
        op.drop_column("workspace_tasks", column)
