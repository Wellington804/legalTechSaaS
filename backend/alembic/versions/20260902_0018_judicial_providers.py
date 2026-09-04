"""Allow a VPS-selected judicial monitoring provider.

Revision ID: 20260902_0018
Revises: 20260901_0017
"""

from alembic import op
import sqlalchemy as sa


revision = "20260902_0018"
down_revision = "20260901_0017"
branch_labels = None
depends_on = None


def _create_candidates_function(*, include_source: bool) -> None:
    columns = (
        "subscription_id text, tenant_id text, source_kind varchar, tribunal varchar, "
        "process_number varchar, responsible_user_id text"
        if include_source
        else "subscription_id text, tenant_id text, tribunal varchar, process_number varchar, responsible_user_id text"
    )
    selection = (
        "subscription.id, subscription.tenant_id, subscription.source_kind, subscription.tribunal, "
        "subscription.process_number, cases.responsible_user_id"
        if include_source
        else "subscription.id, subscription.tenant_id, subscription.tribunal, subscription.process_number, cases.responsible_user_id"
    )
    op.execute(
        f"""
        CREATE FUNCTION controladoria_monitoring_candidates(max_rows integer)
        RETURNS TABLE({columns})
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT {selection}
        FROM public.controladoria_monitoring_subscriptions subscription
        JOIN public.workspace_cases cases
          ON cases.tenant_id = subscription.tenant_id AND cases.id = subscription.case_id
        WHERE subscription.status = 'active'
          AND (subscription.last_checked_at IS NULL
               OR subscription.last_checked_at < statement_timestamp() - interval '15 minutes')
        ORDER BY subscription.last_checked_at NULLS FIRST, subscription.id
        LIMIT LEAST(GREATEST(max_rows, 1), 200) $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION controladoria_monitoring_candidates(integer) FROM PUBLIC")


def upgrade() -> None:
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
    op.drop_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        "source_kind IN ('manual', 'datajud', 'escavador')",
    )
    op.execute("DROP FUNCTION controladoria_monitoring_candidates(integer)")
    _create_candidates_function(include_source=True)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM controladoria_monitoring_subscriptions WHERE source_kind = 'escavador') "
            "OR EXISTS (SELECT 1 FROM controladoria_judicial_events WHERE source_kind = 'escavador')"
        )
    ).scalar():
        raise RuntimeError("Refusing to discard Escavador monitoring history")
    op.execute("DROP FUNCTION controladoria_monitoring_candidates(integer)")
    _create_candidates_function(include_source=False)
    op.drop_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_judicial_events_source_kind",
        "controladoria_judicial_events",
        "source_kind IN ('manual', 'datajud')",
    )
    op.drop_constraint(
        "ck_controladoria_monitoring_subscriptions_source_kind",
        "controladoria_monitoring_subscriptions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_controladoria_monitoring_subscriptions_source_kind",
        "controladoria_monitoring_subscriptions",
        "source_kind IN ('datajud')",
    )
