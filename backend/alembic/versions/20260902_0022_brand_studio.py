"""Structured brand studio, professional fields, variants and R2 assets."""
from alembic import op
import sqlalchemy as sa


revision = "20260902_0022"
down_revision = "20260902_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    empty_json = sa.text("'{}'::json")
    op.add_column("brand_profiles", sa.Column("variants", sa.JSON(), nullable=False, server_default=empty_json))
    op.add_column("brand_profiles", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_brand_profiles_archived_at", "brand_profiles", ["archived_at"])

    op.add_column("brand_versions", sa.Column("variants", sa.JSON(), nullable=False, server_default=empty_json))
    op.add_column("brand_versions", sa.Column("professional_snapshot", sa.JSON(), nullable=False, server_default=empty_json))

    op.alter_column("brand_assets", "content", existing_type=sa.LargeBinary(), nullable=True)
    op.add_column("brand_assets", sa.Column("object_key", sa.String(512), nullable=True))
    op.create_unique_constraint("uq_brand_assets_object_key", "brand_assets", ["object_key"])

    op.add_column("brand_exports", sa.Column("document_type", sa.String(32), nullable=False, server_default="general"))
    op.create_check_constraint(
        "ck_brand_exports_document_type",
        "brand_exports",
        "document_type IN ('general','petition','contract','power_of_attorney','notice','correspondence')",
    )

    op.add_column("workspace_documents", sa.Column("document_type", sa.String(32), nullable=False, server_default="general"))
    op.create_check_constraint(
        "ck_workspace_documents_document_type",
        "workspace_documents",
        "document_type IN ('general','petition','contract','power_of_attorney','notice','correspondence')",
    )
    op.create_index("ix_workspace_documents_document_type", "workspace_documents", ["document_type"])


def downgrade() -> None:
    connection = op.get_bind()
    has_new_data = connection.execute(sa.text("""
        SELECT
          EXISTS (SELECT 1 FROM brand_profiles WHERE variants <> '{}'::json OR archived_at IS NOT NULL)
          OR EXISTS (SELECT 1 FROM brand_versions WHERE variants <> '{}'::json OR professional_snapshot <> '{}'::json)
          OR EXISTS (SELECT 1 FROM brand_assets WHERE object_key IS NOT NULL)
          OR EXISTS (SELECT 1 FROM brand_exports WHERE document_type <> 'general')
          OR EXISTS (SELECT 1 FROM workspace_documents WHERE document_type <> 'general')
    """)).scalar()
    if has_new_data:
        raise RuntimeError("Refusing to discard structured branding data")

    op.drop_index("ix_workspace_documents_document_type", table_name="workspace_documents")
    op.drop_constraint("ck_workspace_documents_document_type", "workspace_documents", type_="check")
    op.drop_column("workspace_documents", "document_type")
    op.drop_constraint("ck_brand_exports_document_type", "brand_exports", type_="check")
    op.drop_column("brand_exports", "document_type")
    op.drop_constraint("uq_brand_assets_object_key", "brand_assets", type_="unique")
    op.drop_column("brand_assets", "object_key")
    op.alter_column("brand_assets", "content", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_column("brand_versions", "professional_snapshot")
    op.drop_column("brand_versions", "variants")
    op.drop_index("ix_brand_profiles_archived_at", table_name="brand_profiles")
    op.drop_column("brand_profiles", "archived_at")
    op.drop_column("brand_profiles", "variants")
