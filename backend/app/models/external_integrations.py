"""Tenant-scoped calendar OAuth, synchronization and provider cost records."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CalendarOAuthState(Base):
    __tablename__ = "calendar_oauth_states"
    __table_args__ = (
        UniqueConstraint("state_digest", name="uq_calendar_oauth_state_digest"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_calendar_oauth_state_user_tenant"
        ),
        CheckConstraint("provider IN ('google', 'microsoft')", name="ck_calendar_oauth_state_provider"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String(16), nullable=False)
    state_digest = Column(String(64), nullable=False)
    pkce_verifier_encrypted = Column(Text, nullable=False)
    redirect_path = Column(String(300), nullable=False, default="/dashboard/tasks")
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_calendar_connections_tenant_id"),
        UniqueConstraint("tenant_id", "user_id", "provider", name="uq_calendar_connection_user_provider"),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_calendar_connection_user_tenant"
        ),
        CheckConstraint("provider IN ('google', 'microsoft')", name="ck_calendar_connections_provider"),
        CheckConstraint(
            "status IN ('active', 'reauthorization_required', 'revoked')", name="ck_calendar_connections_status"
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String(16), nullable=False)
    provider_account_id_hash = Column(String(64), nullable=False)
    provider_account_label = Column(String(320), nullable=True)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)
    granted_scopes = Column(Text, nullable=False)
    selected_calendar_id_encrypted = Column(Text, nullable=True)
    selected_calendar_label = Column(String(300), nullable=True)
    sync_cursor_encrypted = Column(Text, nullable=True)
    sync_window_start = Column(DateTime(timezone=True), nullable=True)
    sync_window_end = Column(DateTime(timezone=True), nullable=True)
    watch_reference_hash = Column(String(64), nullable=True, unique=True)
    watch_reference_encrypted = Column(Text, nullable=True)
    watch_resource_hash = Column(String(64), nullable=True)
    watch_resource_encrypted = Column(Text, nullable=True)
    watch_token_hash = Column(String(64), nullable=True)
    watch_token_encrypted = Column(Text, nullable=True)
    watch_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(500), nullable=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CalendarTaskLink(Base):
    __tablename__ = "calendar_task_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_calendar_task_links_tenant_id"),
        UniqueConstraint("connection_id", "task_id", name="uq_calendar_task_link_connection_task"),
        UniqueConstraint("connection_id", "provider_event_hash", name="uq_calendar_task_link_provider_event"),
        ForeignKeyConstraint(
            ["tenant_id", "connection_id"],
            ["calendar_connections.tenant_id", "calendar_connections.id"],
            name="fk_calendar_task_link_connection_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["workspace_tasks.tenant_id", "workspace_tasks.id"],
            name="fk_calendar_task_link_task_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('active', 'tombstoned', 'conflict')", name="ck_calendar_task_links_status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    connection_id = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=False, index=True)
    provider_event_hash = Column(String(64), nullable=True)
    provider_event_id_encrypted = Column(Text, nullable=True)
    provider_etag = Column(String(512), nullable=True)
    last_local_hash = Column(String(64), nullable=True)
    last_remote_hash = Column(String(64), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CalendarSyncConflict(Base):
    __tablename__ = "calendar_sync_conflicts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_calendar_sync_conflicts_tenant_id"),
        UniqueConstraint("connection_id", "task_id", "remote_hash", name="uq_calendar_sync_conflict_remote"),
        ForeignKeyConstraint(
            ["tenant_id", "connection_id"],
            ["calendar_connections.tenant_id", "calendar_connections.id"],
            name="fk_calendar_sync_conflict_connection_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["workspace_tasks.tenant_id", "workspace_tasks.id"],
            name="fk_calendar_sync_conflict_task_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "resolved_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_calendar_sync_conflict_resolver_tenant",
        ),
        CheckConstraint("reason IN ('both_changed', 'remote_deleted')", name="ck_calendar_sync_conflicts_reason"),
        CheckConstraint("status IN ('pending', 'accepted_remote', 'kept_local')", name="ck_calendar_sync_conflicts_status"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    connection_id = Column(String, nullable=False, index=True)
    task_id = Column(String, nullable=False, index=True)
    reason = Column(String(32), nullable=False)
    remote_hash = Column(String(64), nullable=False)
    remote_etag = Column(String(512), nullable=True)
    remote_payload_encrypted = Column(Text, nullable=False)
    local_revision = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False, default="pending", index=True)
    resolved_by_user_id = Column(String, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class CalendarWebhookEvent(Base):
    __tablename__ = "calendar_webhook_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "delivery_id", name="uq_calendar_webhook_delivery"),
        UniqueConstraint("tenant_id", "provider", "payload_digest", name="uq_calendar_webhook_payload"),
        ForeignKeyConstraint(
            ["tenant_id", "connection_id"],
            ["calendar_connections.tenant_id", "calendar_connections.id"],
            name="fk_calendar_webhook_connection_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("provider IN ('google', 'microsoft')", name="ck_calendar_webhook_events_provider"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    connection_id = Column(String, nullable=False, index=True)
    provider = Column(String(16), nullable=False)
    delivery_id = Column(String(200), nullable=False)
    payload_digest = Column(String(64), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProviderPriceVersion(Base):
    __tablename__ = "provider_price_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_provider_price_versions_tenant_id"),
        UniqueConstraint("tenant_id", "provider", "effective_on", "version", name="uq_provider_price_version"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_provider_price_version_user_tenant",
        ),
        CheckConstraint("pricing_model IN ('commitment_floor', 'base_plus_usage')", name="ck_provider_price_model"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_provider_price_currency"),
        CheckConstraint("monthly_base_amount >= 0", name="ck_provider_price_base_amount"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    pricing_model = Column(String(24), nullable=False)
    monthly_base_amount = Column(Numeric(18, 6), nullable=False, default=0)
    effective_on = Column(Date, nullable=False)
    observed_on = Column(Date, nullable=False)
    provenance_url = Column(String(1000), nullable=False)
    quote_required = Column(Boolean, nullable=False, default=False)
    notes = Column(String(1000), nullable=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProviderPriceItem(Base):
    __tablename__ = "provider_price_items"
    __table_args__ = (
        UniqueConstraint("price_version_id", "metric", name="uq_provider_price_item_metric"),
        ForeignKeyConstraint(
            ["tenant_id", "price_version_id"],
            ["provider_price_versions.tenant_id", "provider_price_versions.id"],
            name="fk_provider_price_item_version_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("unit_price >= 0 AND included_units >= 0", name="ck_provider_price_item_values"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    price_version_id = Column(String, nullable=False, index=True)
    metric = Column(String(64), nullable=False)
    unit_price = Column(Numeric(18, 6), nullable=False)
    included_units = Column(Integer, nullable=False, default=0)


class ProviderUsageEvent(Base):
    __tablename__ = "provider_usage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_hash", name="uq_provider_usage_event_idempotency"),
        ForeignKeyConstraint(
            ["tenant_id", "envelope_id"],
            ["signature_envelopes.tenant_id", "signature_envelopes.id"],
            name="fk_provider_usage_envelope_tenant",
        ),
        CheckConstraint("units > 0", name="ck_provider_usage_event_units"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    envelope_id = Column(String, nullable=True, index=True)
    metric = Column(String(64), nullable=False)
    units = Column(Integer, nullable=False, default=1)
    idempotency_hash = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
