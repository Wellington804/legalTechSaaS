"""Harden calendar deletion and signed PDF validation evidence.

Revision ID: 20260904_0030
Revises: 20260904_0029
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0030"
down_revision = "20260904_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_calendar_task_links_status", "calendar_task_links", type_="check")
    op.create_check_constraint(
        "ck_calendar_task_links_status",
        "calendar_task_links",
        "status IN ('active', 'tombstoned', 'conflict', 'delete_pending')",
    )
    op.add_column("signature_envelopes", sa.Column("signed_validation_status", sa.String(length=24)))
    op.add_column("signature_envelopes", sa.Column("signature_authentication", sa.String(length=16)))
    op.add_column("signature_envelopes", sa.Column("signed_certificate_trust", sa.String(length=16)))
    op.add_column("signature_envelopes", sa.Column("signed_validation_report_encrypted", sa.Text()))
    op.add_column("signature_envelopes", sa.Column("signed_validated_at", sa.DateTime(timezone=True)))
    op.add_column("signature_envelopes", sa.Column("signed_signature_count", sa.Integer()))
    op.create_check_constraint(
        "ck_signature_envelopes_authentication",
        "signature_envelopes",
        "signature_authentication IS NULL OR signature_authentication IN ('email', 'icp_brasil')",
    )
    op.create_check_constraint(
        "ck_signature_envelopes_validation_status",
        "signature_envelopes",
        "signed_validation_status IS NULL OR signed_validation_status IN ('valid_integrity', 'invalid', 'unavailable')",
    )
    op.create_check_constraint(
        "ck_signature_envelopes_certificate_trust",
        "signature_envelopes",
        "signed_certificate_trust IS NULL OR signed_certificate_trust IN ('trusted', 'unverified', 'invalid', 'unavailable')",
    )
    op.create_check_constraint(
        "ck_signature_envelopes_signature_count",
        "signature_envelopes",
        "signed_signature_count IS NULL OR signed_signature_count >= 0",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION autentique_signature_event_candidates(request_limit integer)
        RETURNS TABLE(tenant_id text, event_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT event.tenant_id, event.id
        FROM public.signature_provider_events event
        JOIN public.signature_envelopes envelope
          ON envelope.tenant_id = event.tenant_id AND envelope.id = event.envelope_id
        WHERE event.provider = 'autentique'
          AND event.event_type = 'envelope.signed'
          AND envelope.signed_file_hash IS NULL
          AND envelope.signed_validation_status IS DISTINCT FROM 'invalid'
        ORDER BY event.received_at, event.id
        LIMIT LEAST(GREATEST(request_limit, 1), 500)
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION autentique_signature_event_candidates(integer) FROM PUBLIC")


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION autentique_signature_event_candidates(request_limit integer)
        RETURNS TABLE(tenant_id text, event_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT event.tenant_id, event.id
        FROM public.signature_provider_events event
        JOIN public.signature_envelopes envelope
          ON envelope.tenant_id = event.tenant_id AND envelope.id = event.envelope_id
        WHERE event.provider = 'autentique'
          AND event.event_type = 'envelope.signed'
          AND envelope.signed_file_hash IS NULL
        ORDER BY event.received_at, event.id
        LIMIT LEAST(GREATEST(request_limit, 1), 500)
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION autentique_signature_event_candidates(integer) FROM PUBLIC")
    op.drop_constraint("ck_signature_envelopes_signature_count", "signature_envelopes", type_="check")
    op.drop_constraint("ck_signature_envelopes_certificate_trust", "signature_envelopes", type_="check")
    op.drop_constraint("ck_signature_envelopes_validation_status", "signature_envelopes", type_="check")
    op.drop_constraint("ck_signature_envelopes_authentication", "signature_envelopes", type_="check")
    op.drop_column("signature_envelopes", "signed_signature_count")
    op.drop_column("signature_envelopes", "signed_validated_at")
    op.drop_column("signature_envelopes", "signed_validation_report_encrypted")
    op.drop_column("signature_envelopes", "signed_certificate_trust")
    op.drop_column("signature_envelopes", "signed_validation_status")
    op.drop_column("signature_envelopes", "signature_authentication")
    op.drop_constraint("ck_calendar_task_links_status", "calendar_task_links", type_="check")
    op.create_check_constraint(
        "ck_calendar_task_links_status",
        "calendar_task_links",
        "status IN ('active', 'tombstoned', 'conflict')",
    )
