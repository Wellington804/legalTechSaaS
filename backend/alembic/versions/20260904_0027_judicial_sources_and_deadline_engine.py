"""Add official judicial sources and versioned double-reviewed deadline rules.

Revision ID: 20260904_0027
Revises: 20260904_0026
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0027"
down_revision = "20260904_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "controladoria_monitoring_subscriptions",
        sa.Column("provider_cursor", sa.String(length=512), nullable=True),
    )
    op.drop_constraint(
        "ck_controladoria_monitoring_subscriptions_source_kind",
        "controladoria_monitoring_subscriptions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_monitoring_subscriptions_source_kind",
        "controladoria_monitoring_subscriptions",
        "source_kind IN ('datajud', 'escavador', 'djen', 'domicilio', 'tribunal_api')",
    )
    op.drop_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        "source_kind IN ('manual', 'datajud', 'escavador', 'djen', 'domicilio', 'tribunal_api')",
    )

    op.create_table(
        "controladoria_deadline_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("rule_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rite", sa.String(length=100), nullable=False),
        sa.Column("act_type", sa.String(length=100), nullable=False),
        sa.Column("tribunal", sa.String(length=20), nullable=False),
        sa.Column("local_code", sa.String(length=100), nullable=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("counting_method", sa.String(length=20), nullable=False),
        sa.Column("start_mode", sa.String(length=30), nullable=False),
        sa.Column("due_adjustment", sa.String(length=30), nullable=False, server_default="next_business_day"),
        sa.Column("timezone_name", sa.String(length=64), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("due_hour", sa.Integer(), nullable=False, server_default="23"),
        sa.Column("due_minute", sa.Integer(), nullable=False, server_default="59"),
        sa.Column("legal_sources", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("days > 0 AND days <= 3650", name="ck_controladoria_deadline_rules_days"),
        sa.CheckConstraint(
            "counting_method IN ('business_days', 'calendar_days')",
            name="ck_controladoria_deadline_rules_counting_method",
        ),
        sa.CheckConstraint(
            "start_mode IN ('next_business_day', 'same_business_day', 'next_calendar_day')",
            name="ck_controladoria_deadline_rules_start_mode",
        ),
        sa.CheckConstraint(
            "due_adjustment IN ('none', 'next_business_day')",
            name="ck_controladoria_deadline_rules_due_adjustment",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'rejected', 'retired')",
            name="ck_controladoria_deadline_rules_status",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR "
            "(status IN ('active', 'rejected', 'retired') AND reviewed_by_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND reviewed_by_user_id <> created_by_user_id)",
            name="ck_controladoria_deadline_rules_reviewed",
        ),
        sa.CheckConstraint("due_hour BETWEEN 0 AND 23", name="ck_controladoria_deadline_rules_due_hour"),
        sa.CheckConstraint("due_minute BETWEEN 0 AND 59", name="ck_controladoria_deadline_rules_due_minute"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_rules_creator_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reviewed_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_rules_reviewer_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_controladoria_deadline_rules_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "rule_key", "version", name="uq_controladoria_deadline_rules_key_version"
        ),
    )
    op.create_index("ix_controladoria_deadline_rules_tenant_id", "controladoria_deadline_rules", ["tenant_id"])
    op.create_index("ix_controladoria_deadline_rules_rite", "controladoria_deadline_rules", ["rite"])
    op.create_index("ix_controladoria_deadline_rules_act_type", "controladoria_deadline_rules", ["act_type"])
    op.create_index("ix_controladoria_deadline_rules_tribunal", "controladoria_deadline_rules", ["tribunal"])
    op.create_index("ix_controladoria_deadline_rules_status", "controladoria_deadline_rules", ["status"])
    op.create_index(
        "uq_controladoria_deadline_rules_active_key",
        "controladoria_deadline_rules",
        ["tenant_id", "rule_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "controladoria_calendar_exceptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("scope_kind", sa.String(length=16), nullable=False),
        sa.Column("scope_code", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("source_name", sa.String(length=300), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_kind IN ('national', 'tribunal', 'local')",
            name="ck_controladoria_calendar_exceptions_scope_kind",
        ),
        sa.CheckConstraint(
            "kind IN ('holiday', 'suspension')", name="ck_controladoria_calendar_exceptions_kind"
        ),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_controladoria_calendar_exceptions_period"),
        sa.CheckConstraint(
            "(scope_kind = 'national' AND scope_code = 'BR') OR "
            "(scope_kind IN ('tribunal', 'local') AND length(scope_code) >= 2)",
            name="ck_controladoria_calendar_exceptions_scope_code",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_controladoria_calendar_exceptions_creator_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_controladoria_calendar_exceptions_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "scope_kind", "scope_code", "starts_on", "ends_on", "kind",
            name="uq_controladoria_calendar_exceptions_scope_period",
        ),
    )
    for column in ("tenant_id", "scope_kind", "scope_code", "starts_on", "ends_on"):
        op.create_index(
            f"ix_controladoria_calendar_exceptions_{column}",
            "controladoria_calendar_exceptions",
            [column],
        )
    for table in ("controladoria_deadline_rules", "controladoria_calendar_exceptions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')) "
            "WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true), ''))"
        )

    op.add_column("controladoria_deadline_reviews", sa.Column("rule_id", sa.String(), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("rule_version", sa.Integer(), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("calculation", sa.JSON(), nullable=True))
    op.add_column(
        "controladoria_deadline_reviews",
        sa.Column("calculation_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "controladoria_deadline_reviews",
        sa.Column("approval_policy_version", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column("controladoria_deadline_reviews", sa.Column("first_approved_by_user_id", sa.String(), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("first_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("first_approval_note", sa.Text(), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("second_approved_by_user_id", sa.String(), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("second_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("controladoria_deadline_reviews", sa.Column("second_approval_note", sa.Text(), nullable=True))
    op.execute(
        "UPDATE controladoria_deadline_reviews SET approval_policy_version = 1 WHERE status = 'approved'"
    )
    op.create_foreign_key(
        "fk_controladoria_deadline_reviews_rule_tenant",
        "controladoria_deadline_reviews",
        "controladoria_deadline_rules",
        ["tenant_id", "rule_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_controladoria_deadline_reviews_first_approver_tenant",
        "controladoria_deadline_reviews",
        "users",
        ["tenant_id", "first_approved_by_user_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_controladoria_deadline_reviews_second_approver_tenant",
        "controladoria_deadline_reviews",
        "users",
        ["tenant_id", "second_approved_by_user_id"],
        ["tenant_id", "id"],
    )
    op.drop_constraint(
        "ck_controladoria_deadline_reviews_status", "controladoria_deadline_reviews", type_="check"
    )
    op.drop_constraint(
        "ck_controladoria_deadline_reviews_human_approval",
        "controladoria_deadline_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_deadline_reviews_status",
        "controladoria_deadline_reviews",
        "status IN ('suggested', 'first_approved', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        "ck_controladoria_deadline_reviews_human_approval",
        "controladoria_deadline_reviews",
        "(approval_policy_version = 1 AND status = 'approved' AND reviewed_at IS NOT NULL "
        "AND reviewed_by_user_id IS NOT NULL AND task_id IS NOT NULL) OR "
        "(approval_policy_version = 2 AND status = 'suggested' AND task_id IS NULL "
        "AND first_approved_by_user_id IS NULL AND second_approved_by_user_id IS NULL) OR "
        "(approval_policy_version = 2 AND status = 'first_approved' AND task_id IS NULL "
        "AND first_approved_by_user_id IS NOT NULL AND first_approved_at IS NOT NULL "
        "AND first_approval_note IS NOT NULL AND second_approved_by_user_id IS NULL) OR "
        "(approval_policy_version = 2 AND status = 'approved' AND task_id IS NOT NULL "
        "AND first_approved_by_user_id IS NOT NULL AND first_approved_at IS NOT NULL "
        "AND second_approved_by_user_id IS NOT NULL AND second_approved_at IS NOT NULL "
        "AND first_approval_note IS NOT NULL AND second_approval_note IS NOT NULL "
        "AND reviewed_by_user_id = second_approved_by_user_id AND reviewed_at IS NOT NULL "
        "AND first_approved_by_user_id <> second_approved_by_user_id) OR "
        "(approval_policy_version = 2 AND status = 'rejected' AND task_id IS NULL "
        "AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_note IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE controladoria_deadline_reviews SET status = 'suggested' WHERE status = 'first_approved'"
    )
    op.drop_constraint(
        "ck_controladoria_deadline_reviews_human_approval",
        "controladoria_deadline_reviews",
        type_="check",
    )
    op.drop_constraint(
        "ck_controladoria_deadline_reviews_status", "controladoria_deadline_reviews", type_="check"
    )
    op.create_check_constraint(
        "ck_controladoria_deadline_reviews_status",
        "controladoria_deadline_reviews",
        "status IN ('suggested', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        "ck_controladoria_deadline_reviews_human_approval",
        "controladoria_deadline_reviews",
        "(status = 'approved' AND reviewed_at IS NOT NULL AND reviewed_by_user_id IS NOT NULL "
        "AND task_id IS NOT NULL) OR (status IN ('suggested', 'rejected') AND task_id IS NULL)",
    )
    for name in (
        "fk_controladoria_deadline_reviews_second_approver_tenant",
        "fk_controladoria_deadline_reviews_first_approver_tenant",
        "fk_controladoria_deadline_reviews_rule_tenant",
    ):
        op.drop_constraint(name, "controladoria_deadline_reviews", type_="foreignkey")
    for column in (
        "second_approval_note", "second_approved_at", "second_approved_by_user_id",
        "first_approval_note", "first_approved_at", "first_approved_by_user_id",
        "approval_policy_version", "calculation_revision", "calculation", "rule_version", "rule_id",
    ):
        op.drop_column("controladoria_deadline_reviews", column)

    for table in ("controladoria_calendar_exceptions", "controladoria_deadline_rules"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for column in ("ends_on", "starts_on", "scope_code", "scope_kind", "tenant_id"):
        op.drop_index(
            f"ix_controladoria_calendar_exceptions_{column}",
            table_name="controladoria_calendar_exceptions",
        )
    op.drop_table("controladoria_calendar_exceptions")
    op.drop_index(
        "uq_controladoria_deadline_rules_active_key",
        table_name="controladoria_deadline_rules",
    )
    for column in ("status", "tribunal", "act_type", "rite", "tenant_id"):
        op.drop_index(f"ix_controladoria_deadline_rules_{column}", table_name="controladoria_deadline_rules")
    op.drop_table("controladoria_deadline_rules")

    op.drop_constraint(
        "ck_controladoria_judicial_events_source_kind", "controladoria_judicial_events", type_="check"
    )
    op.create_check_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        "source_kind IN ('manual', 'datajud', 'escavador')",
    )
    op.drop_constraint(
        "ck_controladoria_monitoring_subscriptions_source_kind",
        "controladoria_monitoring_subscriptions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_monitoring_subscriptions_source_kind",
        "controladoria_monitoring_subscriptions",
        "source_kind IN ('datajud', 'escavador')",
    )
    op.drop_column("controladoria_monitoring_subscriptions", "provider_cursor")
