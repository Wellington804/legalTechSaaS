"""Automatic tenant WhatsApp lifecycle.

Revision ID: 20260830_0015
Revises: 20260830_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260830_0015"
down_revision = "20260830_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tenant_channels", sa.Column("whatsapp_last_checked_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_tenant_channel_whatsapp_state",
        "tenant_channels",
        "whatsapp_connection_state IN ('disconnected','pending','connected')",
    )


def downgrade():
    op.drop_constraint("ck_tenant_channel_whatsapp_state", "tenant_channels", type_="check")
    op.drop_column("tenant_channels", "whatsapp_last_checked_at")
