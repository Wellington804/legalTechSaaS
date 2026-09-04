"""Account lifecycle, team and SaaS controls.

Revision ID: 20260827_0002
Revises: 20260826_0001
Create Date: 2026-08-27
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0002"
down_revision: str | None = "20260826_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("mfa_secret_encrypted", sa.String(), nullable=True))
    op.add_column(
        "users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("users", sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("mfa_last_counter", sa.BigInteger(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.add_column(
        "tenants", sa.Column("subscription_status", sa.String(), nullable=False, server_default="trial")
    )
    op.add_column(
        "tenants", sa.Column("subscription_plan", sa.String(), nullable=False, server_default="trial")
    )
    op.add_column("tenants", sa.Column("trial_starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tenants", sa.Column("quota_users", sa.Integer(), nullable=False, server_default="3")
    )
    op.add_column(
        "tenants",
        sa.Column("quota_storage_bytes", sa.Integer(), nullable=False, server_default="1073741824"),
    )
    op.add_column(
        "tenants", sa.Column("quota_messages", sa.Integer(), nullable=False, server_default="100")
    )
    op.execute(
        "UPDATE tenants SET trial_starts_at = created_at, "
        "trial_ends_at = created_at + INTERVAL '14 days' "
        "WHERE trial_starts_at IS NULL OR trial_ends_at IS NULL"
    )
    op.create_check_constraint(
        "ck_tenants_subscription_status",
        "tenants",
        "subscription_status IN ('trial', 'active', 'past_due', 'suspended', 'cancelled')",
    )
    op.create_check_constraint("ck_tenants_quota_users", "tenants", "quota_users >= 1")
    op.create_check_constraint(
        "ck_tenants_quota_storage_bytes", "tenants", "quota_storage_bytes >= 0"
    )
    op.create_check_constraint("ck_tenants_quota_messages", "tenants", "quota_messages >= 0")

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_tenant_id", "auth_sessions", ["tenant_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])

    op.create_table(
        "account_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_type", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_account_tokens_hash"),
    )
    for name, columns in (
        ("ix_account_tokens_user_id", ["user_id"]),
        ("ix_account_tokens_tenant_id", ["tenant_id"]),
        ("ix_account_tokens_token_type", ["token_type"]),
        ("ix_account_tokens_expires_at", ["expires_at"]),
        ("ix_account_tokens_consumed_at", ["consumed_at"]),
    ):
        op.create_index(name, "account_tokens", columns)

    op.create_table(
        "team_invitations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_team_invitation_tenant_email"),
        sa.UniqueConstraint("token_hash", name="uq_team_invitations_token_hash"),
        sa.CheckConstraint("role IN ('admin', 'partner', 'lawyer', 'paralegal')", name="ck_team_invitations_role"),
    )
    op.create_index("ix_team_invitations_tenant_id", "team_invitations", ["tenant_id"])
    op.create_index("ix_team_invitations_expires_at", "team_invitations", ["expires_at"])

    op.create_table(
        "subscription_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("request_type IN ('subscription', 'cancellation')", name="ck_subscription_requests_type"),
        sa.CheckConstraint("status IN ('received', 'in_progress', 'resolved', 'closed')", name="ck_subscription_requests_status"),
    )
    op.create_index("ix_subscription_requests_tenant_id", "subscription_requests", ["tenant_id"])
    op.create_index("ix_subscription_requests_status", "subscription_requests", ["status"])

    tenant_policy = "tenant_id = nullif(current_setting('app.current_tenant', true), '')"
    for table in ("auth_sessions", "account_tokens", "team_invitations", "subscription_requests"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING ({tenant_policy}) WITH CHECK ({tenant_policy})"
        )

    # Public flows receive only a random credential. These functions disclose the
    # tenant only after its opaque, server-peppered hash has matched a live row.
    op.execute(
        "CREATE FUNCTION account_token_tenant_for_hash(opaque_hash text, expected_type text) "
        "RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$ "
        "SELECT tenant_id FROM public.account_tokens "
        "WHERE token_hash = $1 AND token_type = $2 AND consumed_at IS NULL "
        "AND expires_at > statement_timestamp() LIMIT 1 $$"
    )
    op.execute(
        "CREATE FUNCTION team_invitation_tenant_for_hash(opaque_hash text) "
        "RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$ "
        "SELECT tenant_id FROM public.team_invitations "
        "WHERE token_hash = $1 AND accepted_at IS NULL AND revoked_at IS NULL "
        "AND expires_at > statement_timestamp() LIMIT 1 $$"
    )
    op.execute("REVOKE ALL ON FUNCTION account_token_tenant_for_hash(text, text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION team_invitation_tenant_for_hash(text) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS account_token_tenant_for_hash(text, text)")
    op.execute("DROP FUNCTION IF EXISTS team_invitation_tenant_for_hash(text)")
    for table in ("subscription_requests", "team_invitations", "account_tokens", "auth_sessions"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_table("subscription_requests")
    op.drop_table("team_invitations")
    op.drop_table("account_tokens")
    op.drop_table("auth_sessions")

    op.drop_constraint("ck_tenants_quota_messages", "tenants", type_="check")
    op.drop_constraint("ck_tenants_quota_storage_bytes", "tenants", type_="check")
    op.drop_constraint("ck_tenants_quota_users", "tenants", type_="check")
    op.drop_constraint("ck_tenants_subscription_status", "tenants", type_="check")
    for column in (
        "quota_messages",
        "quota_storage_bytes",
        "quota_users",
        "cancel_at_period_end",
        "subscription_ends_at",
        "trial_ends_at",
        "trial_starts_at",
        "subscription_plan",
        "subscription_status",
    ):
        op.drop_column("tenants", column)
    for column in (
        "updated_at",
        "mfa_enrolled_at",
        "mfa_last_counter",
        "mfa_enabled",
        "mfa_secret_encrypted",
        "email_verified_at",
    ):
        op.drop_column("users", column)
