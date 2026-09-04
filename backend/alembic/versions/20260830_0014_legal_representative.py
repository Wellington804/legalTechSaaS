"""Store complete optional legal representative data for clients.

Revision ID: 20260830_0014
Revises: 20260830_0013
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260830_0014"
down_revision = "20260830_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_clients", sa.Column("has_legal_representative", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("workspace_clients", sa.Column("representative_tax_id", sa.String(20)))
    op.add_column("workspace_clients", sa.Column("representative_qualification", sa.String(500)))
    op.add_column("workspace_clients", sa.Column("representative_email", sa.String(320)))
    op.add_column("workspace_clients", sa.Column("representative_phone", sa.String(32)))
    op.add_column("workspace_clients", sa.Column("representative_address", postgresql.JSONB(astext_type=sa.Text())))
    op.execute(
        "UPDATE workspace_clients SET has_legal_representative = true "
        "WHERE representative_name IS NOT NULL AND btrim(representative_name) <> ''"
    )


def downgrade() -> None:
    for column in ("representative_address", "representative_phone", "representative_email", "representative_qualification", "representative_tax_id", "has_legal_representative"):
        op.drop_column("workspace_clients", column)
