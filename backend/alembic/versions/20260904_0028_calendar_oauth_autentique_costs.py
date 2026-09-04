"""Calendar OAuth/sync state and provider cost provenance.

Revision ID: 20260904_0028
Revises: 20260904_0027
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0028"
down_revision = "20260904_0027"
branch_labels = None
depends_on = None


TABLES = (
    "calendar_oauth_states",
    "calendar_connections",
    "calendar_task_links",
    "calendar_sync_conflicts",
    "calendar_webhook_events",
    "provider_price_versions",
    "provider_price_items",
    "provider_usage_events",
)


def _tenant_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (tenant_id = nullif(current_setting('app.current_tenant', true), '')) "
        "WITH CHECK (tenant_id = nullif(current_setting('app.current_tenant', true), ''))"
    )


def upgrade() -> None:
    op.create_table(
        "calendar_oauth_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("state_digest", sa.String(length=64), nullable=False),
        sa.Column("pkce_verifier_encrypted", sa.Text(), nullable=False),
        sa.Column("redirect_path", sa.String(length=300), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google', 'microsoft')", name="ck_calendar_oauth_state_provider"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_calendar_oauth_state_user_tenant"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_digest", name="uq_calendar_oauth_state_digest"),
    )
    op.create_index("ix_calendar_oauth_states_tenant_id", "calendar_oauth_states", ["tenant_id"])
    op.create_index("ix_calendar_oauth_states_user_id", "calendar_oauth_states", ["user_id"])
    op.create_index("ix_calendar_oauth_states_expires_at", "calendar_oauth_states", ["expires_at"])

    op.create_table(
        "calendar_connections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_account_id_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_account_label", sa.String(length=320), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_scopes", sa.Text(), nullable=False),
        sa.Column("selected_calendar_id_encrypted", sa.Text(), nullable=True),
        sa.Column("selected_calendar_label", sa.String(length=300), nullable=True),
        sa.Column("sync_cursor_encrypted", sa.Text(), nullable=True),
        sa.Column("sync_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watch_reference_hash", sa.String(length=64), nullable=True),
        sa.Column("watch_reference_encrypted", sa.Text(), nullable=True),
        sa.Column("watch_resource_hash", sa.String(length=64), nullable=True),
        sa.Column("watch_resource_encrypted", sa.Text(), nullable=True),
        sa.Column("watch_token_hash", sa.String(length=64), nullable=True),
        sa.Column("watch_token_encrypted", sa.Text(), nullable=True),
        sa.Column("watch_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google', 'microsoft')", name="ck_calendar_connections_provider"),
        sa.CheckConstraint(
            "status IN ('active', 'reauthorization_required', 'revoked')", name="ck_calendar_connections_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_calendar_connection_user_tenant"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_calendar_connections_tenant_id"),
        sa.UniqueConstraint("tenant_id", "user_id", "provider", name="uq_calendar_connection_user_provider"),
        sa.UniqueConstraint("watch_reference_hash", name="uq_calendar_connections_watch_reference_hash"),
    )
    op.create_index("ix_calendar_connections_tenant_id", "calendar_connections", ["tenant_id"])
    op.create_index("ix_calendar_connections_user_id", "calendar_connections", ["user_id"])
    op.create_index("ix_calendar_connections_status", "calendar_connections", ["status"])

    op.create_table(
        "calendar_task_links",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("connection_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("provider_event_hash", sa.String(length=64), nullable=True),
        sa.Column("provider_event_id_encrypted", sa.Text(), nullable=True),
        sa.Column("provider_etag", sa.String(length=512), nullable=True),
        sa.Column("last_local_hash", sa.String(length=64), nullable=True),
        sa.Column("last_remote_hash", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'tombstoned', 'conflict')", name="ck_calendar_task_links_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "connection_id"], ["calendar_connections.tenant_id", "calendar_connections.id"],
            name="fk_calendar_task_link_connection_tenant", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"], ["workspace_tasks.tenant_id", "workspace_tasks.id"],
            name="fk_calendar_task_link_task_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_calendar_task_links_tenant_id"),
        sa.UniqueConstraint("connection_id", "task_id", name="uq_calendar_task_link_connection_task"),
        sa.UniqueConstraint("connection_id", "provider_event_hash", name="uq_calendar_task_link_provider_event"),
    )
    for column in ("tenant_id", "connection_id", "task_id", "status"):
        op.create_index(f"ix_calendar_task_links_{column}", "calendar_task_links", [column])

    op.create_table(
        "calendar_sync_conflicts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("connection_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("remote_hash", sa.String(length=64), nullable=False),
        sa.Column("remote_etag", sa.String(length=512), nullable=True),
        sa.Column("remote_payload_encrypted", sa.Text(), nullable=False),
        sa.Column("local_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("resolved_by_user_id", sa.String(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reason IN ('both_changed', 'remote_deleted')", name="ck_calendar_sync_conflicts_reason"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted_remote', 'kept_local')", name="ck_calendar_sync_conflicts_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "connection_id"], ["calendar_connections.tenant_id", "calendar_connections.id"],
            name="fk_calendar_sync_conflict_connection_tenant", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"], ["workspace_tasks.tenant_id", "workspace_tasks.id"],
            name="fk_calendar_sync_conflict_task_tenant", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resolved_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_calendar_sync_conflict_resolver_tenant"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_calendar_sync_conflicts_tenant_id"),
        sa.UniqueConstraint("connection_id", "task_id", "remote_hash", name="uq_calendar_sync_conflict_remote"),
    )
    for column in ("tenant_id", "connection_id", "task_id", "status"):
        op.create_index(f"ix_calendar_sync_conflicts_{column}", "calendar_sync_conflicts", [column])

    op.create_table(
        "calendar_webhook_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("connection_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("delivery_id", sa.String(length=200), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google', 'microsoft')", name="ck_calendar_webhook_events_provider"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "connection_id"], ["calendar_connections.tenant_id", "calendar_connections.id"],
            name="fk_calendar_webhook_connection_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider", "delivery_id", name="uq_calendar_webhook_delivery"),
        sa.UniqueConstraint("tenant_id", "provider", "payload_digest", name="uq_calendar_webhook_payload"),
    )
    op.create_index("ix_calendar_webhook_events_tenant_id", "calendar_webhook_events", ["tenant_id"])
    op.create_index("ix_calendar_webhook_events_connection_id", "calendar_webhook_events", ["connection_id"])

    op.create_table(
        "provider_price_versions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("pricing_model", sa.String(length=24), nullable=False),
        sa.Column("monthly_base_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("provenance_url", sa.String(length=1000), nullable=False),
        sa.Column("quote_required", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("pricing_model IN ('commitment_floor', 'base_plus_usage')", name="ck_provider_price_model"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_provider_price_currency"),
        sa.CheckConstraint("monthly_base_amount >= 0", name="ck_provider_price_base_amount"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"],
            name="fk_provider_price_version_user_tenant"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_provider_price_versions_tenant_id"),
        sa.UniqueConstraint("tenant_id", "provider", "effective_on", "version", name="uq_provider_price_version"),
    )
    op.create_index("ix_provider_price_versions_tenant_id", "provider_price_versions", ["tenant_id"])
    op.create_index("ix_provider_price_versions_provider", "provider_price_versions", ["provider"])

    op.create_table(
        "provider_price_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("price_version_id", sa.String(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("included_units", sa.Integer(), nullable=False),
        sa.CheckConstraint("unit_price >= 0 AND included_units >= 0", name="ck_provider_price_item_values"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "price_version_id"], ["provider_price_versions.tenant_id", "provider_price_versions.id"],
            name="fk_provider_price_item_version_tenant", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("price_version_id", "metric", name="uq_provider_price_item_metric"),
    )
    op.create_index("ix_provider_price_items_tenant_id", "provider_price_items", ["tenant_id"])
    op.create_index("ix_provider_price_items_price_version_id", "provider_price_items", ["price_version_id"])

    op.create_table(
        "provider_usage_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("envelope_id", sa.String(), nullable=True),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("idempotency_hash", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("units > 0", name="ck_provider_usage_event_units"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "envelope_id"], ["signature_envelopes.tenant_id", "signature_envelopes.id"],
            name="fk_provider_usage_envelope_tenant"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_hash", name="uq_provider_usage_event_idempotency"),
    )
    for column in ("tenant_id", "provider", "envelope_id", "occurred_at"):
        op.create_index(f"ix_provider_usage_events_{column}", "provider_usage_events", [column])

    for table in TABLES:
        _tenant_policy(table)

    op.execute(
        """
        CREATE FUNCTION calendar_webhook_identity(request_provider text, request_reference_hash text)
        RETURNS TABLE(tenant_id text, connection_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT connection.tenant_id, connection.id
        FROM public.calendar_connections connection
        WHERE connection.provider = request_provider
          AND connection.watch_reference_hash = request_reference_hash
          AND connection.status = 'active'
        LIMIT 1
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION calendar_webhook_identity(text, text) FROM PUBLIC")
    op.execute(
        """
        CREATE FUNCTION calendar_reconciliation_candidates(request_limit integer)
        RETURNS TABLE(tenant_id text, connection_id text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT connection.tenant_id, connection.id
        FROM public.calendar_connections connection
        WHERE connection.status = 'active'
          AND connection.selected_calendar_id_encrypted IS NOT NULL
        ORDER BY connection.last_sync_at ASC NULLS FIRST, connection.id
        LIMIT LEAST(GREATEST(request_limit, 1), 500)
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION calendar_reconciliation_candidates(integer) FROM PUBLIC")
    op.execute(
        """
        CREATE FUNCTION autentique_signature_event_candidates(request_limit integer)
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


def downgrade() -> None:
    op.execute("DROP FUNCTION autentique_signature_event_candidates(integer)")
    op.execute("DROP FUNCTION calendar_reconciliation_candidates(integer)")
    op.execute("DROP FUNCTION calendar_webhook_identity(text, text)")
    for table in reversed(TABLES):
        op.drop_table(table)
