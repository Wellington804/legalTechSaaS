"""Replace the simulated OAB module with user-maintained enrollment tracking.

Revision ID: 20260905_0033
Revises: 20260905_0032
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0033"
down_revision = "20260905_0032"
branch_labels = None
depends_on = None


LEGACY_TABLES = ("oab_checklists", "oab_declarations", "oab_fee_structures", "oab_applications")


def _tenant_policy(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY "tenant_isolation_{table}" ON "{table}" '
        "USING (tenant_id = current_setting('app.current_tenant', true)) "
        "WITH CHECK (tenant_id = current_setting('app.current_tenant', true))"
    )


def _require_empty(tables: tuple[str, ...]) -> None:
    connection = op.get_bind()
    existing = set(sa.inspect(connection).get_table_names())
    populated = []
    for table in tables:
        if table not in existing:
            continue
        if table in {"oab_applications", "oab_checklists", "oab_declarations", "oab_enrollments", "oab_enrollment_checklist_items"}:
            connection.execute(sa.text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'))
            connection.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        if connection.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}")')).scalar():
            populated.append(table)
    if populated:
        raise RuntimeError(f"Migracao OAB bloqueada: tabelas contem dados: {', '.join(populated)}")


def upgrade() -> None:
    _require_empty(LEGACY_TABLES)
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for table in LEGACY_TABLES:
        if table in existing:
            op.drop_table(table)

    op.create_table(
        "oab_enrollments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("enrollment_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="planning"),
        sa.Column("protocol", sa.String(120), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("source_version", sa.String(64), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_oab_enrollments_tenant_id"),
        sa.UniqueConstraint("tenant_id", "user_id", "id", name="uq_oab_enrollments_owner_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_oab_enrollments_owner_tenant",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO')",
            name="ck_oab_enrollments_uf",
        ),
        sa.CheckConstraint(
            "enrollment_type IN ('principal','supplementary','transfer','other')",
            name="ck_oab_enrollments_type",
        ),
        sa.CheckConstraint(
            "status IN ('planning','gathering','submitted','awaiting_response','completed','paused')",
            name="ck_oab_enrollments_status",
        ),
    )
    op.create_index("ix_oab_enrollments_owner_updated", "oab_enrollments", ["tenant_id", "user_id", "updated_at"])
    op.create_index("ix_oab_enrollments_uf", "oab_enrollments", ["uf"])
    op.create_index("ix_oab_enrollments_status", "oab_enrollments", ["status"])

    op.create_table(
        "oab_enrollment_checklist_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("enrollment_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id", "enrollment_id"],
            ["oab_enrollments.tenant_id", "oab_enrollments.user_id", "oab_enrollments.id"],
            name="fk_oab_checklist_enrollment_owner",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_oab_checklist_title"),
    )
    op.create_index(
        "ix_oab_checklist_owner_enrollment",
        "oab_enrollment_checklist_items",
        ["tenant_id", "user_id", "enrollment_id", "created_at"],
    )
    _tenant_policy("oab_enrollments")
    _tenant_policy("oab_enrollment_checklist_items")


def downgrade() -> None:
    _require_empty(("oab_enrollment_checklist_items", "oab_enrollments"))
    op.drop_table("oab_enrollment_checklist_items")
    op.drop_table("oab_enrollments")

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

    tenant_policy = "tenant_id = current_setting('app.current_tenant', true)"
    op.execute("ALTER TABLE oab_applications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE oab_applications FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY oab_applications_tenant_isolation ON oab_applications "
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
