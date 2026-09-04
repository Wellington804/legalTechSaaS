"""Private document branding and immutable export history."""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0006"
down_revision = "20260827_0005"
branch_labels = None
depends_on = None


def common_columns():
    return [sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    for table in ("workspace_documents", "workspace_document_versions"):
        op.add_column(table, sa.Column("content_format", sa.String(16), nullable=False, server_default="plain"))
        op.create_check_constraint(f"ck_{table}_content_format", table, "content_format IN ('plain','markdown')")
    op.create_table("brand_profiles", *common_columns(),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("owner_user_id", sa.String()), sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"), sa.Column("published_version", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_brand_profile_tenant"),
        sa.CheckConstraint("(scope = 'office' AND owner_user_id IS NULL) OR (scope = 'personal' AND owner_user_id IS NOT NULL)", name="ck_brand_profile_scope"),
        sa.ForeignKeyConstraint(["tenant_id", "owner_user_id"], ["users.tenant_id", "users.id"]))
    op.create_table("brand_versions", *common_columns(),
        sa.Column("profile_id", sa.String(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False), sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.UniqueConstraint("tenant_id", "profile_id", "version", name="uq_brand_version_number"),
        sa.ForeignKeyConstraint(["tenant_id", "profile_id"], ["brand_profiles.tenant_id", "brand_profiles.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]))
    op.create_foreign_key("fk_brand_published_version", "brand_profiles", "brand_versions", ["tenant_id", "id", "published_version"], ["tenant_id", "profile_id", "version"], deferrable=True, initially="DEFERRED")
    op.create_table("brand_assets", *common_columns(),
        sa.Column("profile_id", sa.String(), nullable=False), sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False), sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("analysis", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.CheckConstraint("kind IN ('reference','logo','logo_dark','logo_mono','watermark')", name="ck_brand_asset_kind"),
        sa.ForeignKeyConstraint(["tenant_id", "profile_id"], ["brand_profiles.tenant_id", "brand_profiles.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]))
    op.create_table("brand_exports", *common_columns(),
        sa.Column("document_id", sa.String(), nullable=False), sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False), sa.Column("brand_version", sa.Integer(), nullable=False),
        sa.Column("brand_snapshot", sa.JSON(), nullable=False), sa.Column("docx", sa.LargeBinary(), nullable=False),
        sa.Column("pdf", sa.LargeBinary(), nullable=False), sa.Column("sha256_docx", sa.String(64), nullable=False),
        sa.Column("sha256_pdf", sa.String(64), nullable=False), sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "document_id", "document_version"], ["workspace_document_versions.tenant_id", "workspace_document_versions.document_id", "workspace_document_versions.version"]),
        sa.ForeignKeyConstraint(["tenant_id", "profile_id", "brand_version"], ["brand_versions.tenant_id", "brand_versions.profile_id", "brand_versions.version"]),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]))
    for table in ("brand_profiles", "brand_versions", "brand_assets", "brand_exports"):
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        if table in {"brand_versions", "brand_assets"}:
            op.create_index(f"ix_{table}_profile_id", table, ["profile_id"])
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY tenant_scope ON "{table}" USING
            (tenant_id = nullif(current_setting('app.current_tenant', true), '')) WITH CHECK
            (tenant_id = nullif(current_setting('app.current_tenant', true), ''))''')
    op.create_index("ix_brand_exports_document_id", "brand_exports", ["document_id"])
    op.execute("""CREATE FUNCTION public.brand_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Published branding assets and exports are immutable'; END; $$""")
    for table in ("brand_versions", "brand_assets", "brand_exports"):
        op.execute(f'CREATE TRIGGER immutable_brand_record BEFORE UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION public.brand_immutable()')


def downgrade():
    # Fail closed if the migration role cannot see all tenant rows under FORCE RLS.
    op.execute("SET LOCAL row_security = off")
    if op.get_bind().execute(sa.text("SELECT 1 FROM brand_profiles UNION ALL SELECT 1 FROM workspace_document_versions WHERE content_format <> 'plain' LIMIT 1")).first():
        raise RuntimeError("Branding data exists; restore a compatible backup instead of discarding history")
    op.drop_constraint("fk_brand_published_version", "brand_profiles", type_="foreignkey")
    for table in ("brand_exports", "brand_assets", "brand_versions", "brand_profiles"):
        op.drop_table(table)
    op.execute("DROP FUNCTION public.brand_immutable()")
    for table in ("workspace_document_versions", "workspace_documents"):
        op.drop_column(table, "content_format")
