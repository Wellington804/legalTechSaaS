"""Persist Escavador monitor ids and resolve authenticated callback targets.

Revision ID: 20260904_0024
Revises: 20260903_0023
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0024"
down_revision = "20260903_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "controladoria_monitoring_subscriptions",
        sa.Column("provider_subscription_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_controladoria_monitoring_subscriptions_webhook_lookup",
        "controladoria_monitoring_subscriptions",
        ["source_kind", "process_number", "status"],
    )
    op.execute(
        """
        CREATE FUNCTION controladoria_escavador_webhook_targets(
            request_process_number text,
            request_provider_subscription_id text
        ) RETURNS TABLE(subscription_id text, tenant_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT subscription.id, subscription.tenant_id
        FROM public.controladoria_monitoring_subscriptions subscription
        WHERE subscription.source_kind = 'escavador'
          AND subscription.status = 'active'
          AND subscription.process_number = request_process_number
          AND (
              subscription.provider_subscription_id IS NULL
              OR subscription.provider_subscription_id = request_provider_subscription_id
          )
        ORDER BY subscription.id
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION controladoria_escavador_webhook_targets(text, text) FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION controladoria_escavador_webhook_targets(text, text)")
    op.drop_index(
        "ix_controladoria_monitoring_subscriptions_webhook_lookup",
        table_name="controladoria_monitoring_subscriptions",
    )
    op.drop_column("controladoria_monitoring_subscriptions", "provider_subscription_id")
