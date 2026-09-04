"""Add durable notification recovery and a minimal provider receipt inbox.

Revision ID: 20260827_0004
Revises: 20260827_0003
Create Date: 2026-08-27
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0004"
down_revision: str | None = "20260827_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_deliveries",
        sa.Column("provider_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_deliveries",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_notification_deliveries_recovery "
        "ON notification_deliveries (status, next_attempt_at, processing_started_at) "
        "WHERE status IN ('queued', 'processing')"
    )

    op.create_table(
        "notification_provider_receipts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column(
            "delivery_id",
            sa.String(),
            sa.ForeignKey("notification_deliveries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("provider_message_hash", sa.String(64), nullable=False),
        sa.Column("event_digest", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("provider", "event_digest", name="uq_notification_receipt_event"),
        sa.CheckConstraint(
            "provider IN ('resend', 'evolution')", name="ck_notification_receipt_provider"
        ),
        sa.CheckConstraint(
            "status IN ('sent', 'delivered', 'failed')",
            name="ck_notification_receipt_status",
        ),
    )
    op.create_index(
        "ix_notification_provider_receipts_tenant_id",
        "notification_provider_receipts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_notification_provider_receipts_delivery_id",
        "notification_provider_receipts",
        ["delivery_id"],
    )
    op.create_index(
        "ix_notification_provider_receipts_lookup",
        "notification_provider_receipts",
        ["provider", "provider_message_hash"],
    )
    tenant_policy = "tenant_id = current_setting('app.current_tenant', true)"
    op.execute("ALTER TABLE notification_provider_receipts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_provider_receipts FORCE ROW LEVEL SECURITY")
    # Unmatched receipts contain hashes/metadata only; the worker attaches a tenant later.
    op.execute(
        "CREATE POLICY notification_provider_receipts_tenant_isolation "
        "ON notification_provider_receipts "
        f"USING (tenant_id IS NULL OR {tenant_policy}) "
        f"WITH CHECK (tenant_id IS NULL OR {tenant_policy})"
    )

    # The worker uses the runtime RLS role. Expose only opaque delivery/tenant ids through
    # a security-definer function so Beat can recover all tenants without broad table access.
    op.execute(
        "CREATE FUNCTION notification_recovery_candidates(max_rows integer, timeout_seconds integer) "
        "RETURNS TABLE(delivery_id text, tenant_id text) "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$ "
        "SELECT delivery.id, delivery.tenant_id "
        "FROM public.notification_deliveries delivery "
        "WHERE (delivery.status = 'queued' "
        "AND (delivery.next_attempt_at IS NULL OR delivery.next_attempt_at <= statement_timestamp())) "
        "OR (delivery.status = 'processing' "
        "AND (delivery.processing_started_at IS NULL "
        "OR delivery.processing_started_at <= statement_timestamp() "
        "- make_interval(secs => GREATEST($2, 1)))) "
        "ORDER BY COALESCE(delivery.next_attempt_at, delivery.processing_started_at, delivery.created_at), delivery.id "
        "LIMIT LEAST(GREATEST($1, 1), 500) $$"
    )
    op.execute("REVOKE ALL ON FUNCTION notification_recovery_candidates(integer, integer) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS notification_recovery_candidates(integer, integer)")
    op.execute("DROP POLICY IF EXISTS notification_provider_receipts_tenant_isolation ON notification_provider_receipts")
    op.drop_index("ix_notification_provider_receipts_lookup", table_name="notification_provider_receipts")
    op.drop_index("ix_notification_provider_receipts_delivery_id", table_name="notification_provider_receipts")
    op.drop_index("ix_notification_provider_receipts_tenant_id", table_name="notification_provider_receipts")
    op.drop_table("notification_provider_receipts")
    op.execute("DROP INDEX IF EXISTS ix_notification_deliveries_recovery")
    op.drop_column("notification_deliveries", "next_attempt_at")
    op.drop_column("notification_deliveries", "provider_attempted_at")
