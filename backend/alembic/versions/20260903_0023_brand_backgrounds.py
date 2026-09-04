"""Allow immutable sanitized page backgrounds for faithful letterheads."""
from alembic import op


revision = "20260903_0023"
down_revision = "20260902_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_brand_asset_kind", "brand_assets", type_="check")
    op.create_check_constraint(
        "ck_brand_asset_kind",
        "brand_assets",
        "kind IN ('reference','logo','logo_dark','logo_mono','watermark','background')",
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.exec_driver_sql("SELECT 1 FROM brand_assets WHERE kind = 'background' LIMIT 1").first():
        raise RuntimeError("Refusing to discard document background assets")
    op.drop_constraint("ck_brand_asset_kind", "brand_assets", type_="check")
    op.create_check_constraint(
        "ck_brand_asset_kind",
        "brand_assets",
        "kind IN ('reference','logo','logo_dark','logo_mono','watermark')",
    )
