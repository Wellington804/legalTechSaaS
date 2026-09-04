"""Initial production schema.

Revision ID: 20260826_0001
Revises:
Create Date: 2026-08-26
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "20260826_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("cnpj", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="lawyer"),
        sa.Column("oab_number", sa.String(), nullable=True),
        sa.Column("oab_uf", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.execute("CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))")

    op.create_table(
        "oab_applications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("seccional", sa.String(), nullable=False),
        sa.Column("candidate_name", sa.String(), nullable=False),
        sa.Column("cpf", sa.String(), nullable=False),
        sa.Column("rg", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="EM_ANDAMENTO"),
        sa.Column("fgv_exam_number", sa.String(), nullable=True),
        sa.Column("protocol_number", sa.String(), nullable=True),
        sa.Column("biometric_scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_ceremony_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_oab_applications_tenant_id", "oab_applications", ["tenant_id"])
    op.create_index("ix_oab_applications_user_id", "oab_applications", ["user_id"])
    op.create_index("ix_oab_applications_cpf", "oab_applications", ["cpf"])
    op.execute("CREATE INDEX idx_oab_apps_tenant_created ON oab_applications (tenant_id, created_at DESC)")
    op.create_index("idx_oab_apps_tenant_status", "oab_applications", ["tenant_id", "status"])

    op.create_table(
        "oab_checklists",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("application_id", sa.String(), sa.ForeignKey("oab_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_code", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("file_url", sa.String(), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("application_id", "item_code", name="uq_oab_checklist_item"),
    )
    op.create_index("ix_oab_checklists_application_id", "oab_checklists", ["application_id"])

    op.create_table(
        "oab_fee_structures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("seccional", sa.String(), nullable=False),
        sa.Column("req_fee", sa.Float(), nullable=False, server_default="250"),
        sa.Column("card_fee", sa.Float(), nullable=False, server_default="180"),
        sa.Column("anuidade_full", sa.Float(), nullable=False, server_default="950"),
        sa.Column("jovem_advogado_discount_pct", sa.Float(), nullable=False, server_default="50"),
        sa.Column("sua_discount_pct", sa.Float(), nullable=False, server_default="25"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_oab_fee_structures_seccional", "oab_fee_structures", ["seccional"])

    op.create_table(
        "oab_declarations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("application_id", sa.String(), sa.ForeignKey("oab_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("declaration_type", sa.String(), nullable=False),
        sa.Column("declarant_name", sa.String(), nullable=False),
        sa.Column("cpf", sa.String(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("signed_digitally", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signature_hash", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_oab_declarations_application_id", "oab_declarations", ["application_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("sha256_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.execute("CREATE INDEX idx_audit_tenant_created ON audit_logs (tenant_id, created_at DESC)")

    op.create_table(
        "conflict_checks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entity_name", sa.String(), nullable=False),
        sa.Column("cpf_cnpj", sa.String(), nullable=True),
        sa.Column("check_type", sa.String(), nullable=True),
        sa.Column("has_conflict", sa.Boolean(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("matched_records", sa.JSON(), nullable=True),
        sa.Column("checked_by_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for column in ("tenant_id", "entity_name", "cpf_cnpj"):
        op.create_index(f"ix_conflict_checks_{column}", "conflict_checks", [column])

    op.create_table(
        "dashboard_metrics",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("processos", sa.String(), nullable=False),
        sa.Column("processos_change", sa.String(), nullable=False),
        sa.Column("conflitos", sa.String(), nullable=False),
        sa.Column("conflitos_change", sa.String(), nullable=False),
        sa.Column("contratos", sa.String(), nullable=False),
        sa.Column("contratos_change", sa.String(), nullable=False),
        sa.Column("faturamento", sa.Float(), nullable=False),
        sa.Column("faturamento_change", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_dashboard_metrics_tenant_id", "dashboard_metrics", ["tenant_id"])
    op.create_index("ix_dashboard_metrics_period", "dashboard_metrics", ["period"])

    op.create_table(
        "critical_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("dept", sa.String(), nullable=False),
        sa.Column("deadline", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_critical_tasks_tenant_id", "critical_tasks", ["tenant_id"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_ref", sa.String(128), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("recipient_hash", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "resource_ref", "recipient_hash", "channel", name="uq_notification_delivery_identity"),
        sa.UniqueConstraint("channel", "provider_message_id", name="uq_notification_provider_message"),
        sa.CheckConstraint("channel IN ('email', 'whatsapp')", name="ck_notification_channel"),
        sa.CheckConstraint("status IN ('queued', 'processing', 'sent', 'delivered', 'unknown', 'failed')", name="ck_notification_status"),
    )
    op.create_index("ix_notification_deliveries_tenant_id", "notification_deliveries", ["tenant_id"])
    op.create_index("ix_notification_deliveries_status", "notification_deliveries", ["status"])

    op.create_table(
        "notification_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("delivery_id", sa.String(), sa.ForeignKey("notification_deliveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("event_digest", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "event_digest", name="uq_notification_event_digest"),
    )
    op.create_index("ix_notification_events_delivery_id", "notification_events", ["delivery_id"])

    op.create_table(
        "petition_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.execute(
        "CREATE INDEX idx_petition_hnsw ON petition_templates "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    tenant_policy = "tenant_id = current_setting('app.current_tenant', true)"
    for table in ("oab_applications", "audit_logs"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING ({tenant_policy}) WITH CHECK ({tenant_policy})"
        )
    for table in ("oab_checklists", "oab_declarations"):
        policy = (
            "EXISTS (SELECT 1 FROM oab_applications app "
            f"WHERE app.id = {table}.application_id "
            "AND app.tenant_id = current_setting('app.current_tenant', true))"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING ({policy}) WITH CHECK ({policy})"
        )

    op.execute(
        "CREATE FUNCTION notification_tenant_for_provider(provider_channel text, message_id text) "
        "RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$ "
        "SELECT tenant_id FROM public.notification_deliveries "
        "WHERE channel = $1 AND provider_message_id = $2 LIMIT 1 $$"
    )
    op.execute("REVOKE ALL ON FUNCTION notification_tenant_for_provider(text, text) FROM PUBLIC")
    op.execute("ALTER TABLE notification_deliveries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_deliveries FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY notification_deliveries_tenant_isolation ON notification_deliveries "
        f"USING ({tenant_policy}) WITH CHECK ({tenant_policy})"
    )
    event_policy = (
        "EXISTS (SELECT 1 FROM notification_deliveries delivery "
        "WHERE delivery.id = notification_events.delivery_id "
        "AND delivery.tenant_id = current_setting('app.current_tenant', true))"
    )
    op.execute("ALTER TABLE notification_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY notification_events_tenant_isolation ON notification_events "
        f"USING ({event_policy}) WITH CHECK ({event_policy})"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS notification_tenant_for_provider(text, text)")
    op.execute("DROP POLICY IF EXISTS notification_events_tenant_isolation ON notification_events")
    op.execute("DROP POLICY IF EXISTS notification_deliveries_tenant_isolation ON notification_deliveries")
    for table in (
        "oab_declarations",
        "oab_checklists",
        "audit_logs",
        "oab_applications",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    for table in (
        "petition_templates",
        "notification_events",
        "notification_deliveries",
        "critical_tasks",
        "dashboard_metrics",
        "conflict_checks",
        "audit_logs",
        "oab_declarations",
        "oab_fee_structures",
        "oab_checklists",
        "oab_applications",
        "users",
        "tenants",
    ):
        op.drop_table(table)
