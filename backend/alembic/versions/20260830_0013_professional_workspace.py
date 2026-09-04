"""Professional, office and client data used to prepare documents.

Revision ID: 20260830_0013
Revises: 20260829_0012
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260830_0013"
down_revision = "20260829_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("professional_name", sa.String(120)))
    op.add_column("users", sa.Column("professional_email", sa.String(320)))
    op.add_column("users", sa.Column("professional_phone", sa.String(32)))
    op.add_column("users", sa.Column("professional_address", postgresql.JSONB(astext_type=sa.Text())))

    op.add_column("tenants", sa.Column("legal_name", sa.String(160)))
    op.add_column("tenants", sa.Column("office_email", sa.String(320)))
    op.add_column("tenants", sa.Column("office_phone", sa.String(32)))
    op.add_column("tenants", sa.Column("website", sa.String(2048)))
    op.add_column("tenants", sa.Column("office_address", postgresql.JSONB(astext_type=sa.Text())))
    op.add_column("tenants", sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Sao_Paulo"))
    op.add_column("tenants", sa.Column("signature_city", sa.String(120)))

    op.add_column("workspace_clients", sa.Column("person_type", sa.String(16), nullable=False, server_default="individual"))
    op.add_column("workspace_clients", sa.Column("qualification", sa.String(500)))
    op.add_column("workspace_clients", sa.Column("occupation", sa.String(160)))
    op.add_column("workspace_clients", sa.Column("representative_name", sa.String(200)))
    op.add_column("workspace_clients", sa.Column("address", postgresql.JSONB(astext_type=sa.Text())))
    op.create_check_constraint("ck_workspace_clients_person_type", "workspace_clients", "person_type IN ('individual', 'company')")
    op.add_column("tenant_channels", sa.Column("whatsapp_number", sa.String(32)))
    op.add_column("tenant_channels", sa.Column("whatsapp_connection_state", sa.String(24), nullable=False, server_default="disconnected"))


def downgrade() -> None:
    op.drop_column("tenant_channels", "whatsapp_connection_state")
    op.drop_column("tenant_channels", "whatsapp_number")
    op.drop_constraint("ck_workspace_clients_person_type", "workspace_clients", type_="check")
    for column in ("address", "representative_name", "occupation", "qualification", "person_type"):
        op.drop_column("workspace_clients", column)
    for column in ("signature_city", "timezone", "office_address", "website", "office_phone", "office_email", "legal_name"):
        op.drop_column("tenants", column)
    for column in ("professional_address", "professional_phone", "professional_email", "professional_name"):
        op.drop_column("users", column)
