"""Encrypt tenant WhatsApp instance identifiers.

Revision ID: 20260830_0016
Revises: 20260830_0015
"""
from alembic import op
import sqlalchemy as sa


revision = "20260830_0016"
down_revision = "20260830_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_channels", sa.Column("evolution_instance_id_encrypted", sa.Text()))
    op.add_column("tenant_channels", sa.Column("evolution_instance_id_hash", sa.String(64)))
    op.create_unique_constraint(
        "uq_tenant_channels_evolution_instance_id_hash", "tenant_channels", ["evolution_instance_id_hash"]
    )
    # Manual prototype credentials cannot be safely transformed inside SQL; require a fresh secure pairing.
    op.execute(
        "UPDATE tenant_channels SET whatsapp_enabled=false, whatsapp_connection_state='disconnected', "
        "whatsapp_number=NULL, evolution_api_key_encrypted=NULL, evolution_token_encrypted=NULL "
        "WHERE evolution_instance_id IS NOT NULL"
    )
    op.execute("DROP FUNCTION public.tenant_channel_webhook_identity(text)")
    op.drop_constraint("tenant_channels_evolution_instance_id_key", "tenant_channels", type_="unique")
    op.drop_column("tenant_channels", "evolution_instance_id")
    op.execute("""CREATE FUNCTION public.tenant_channel_webhook_identity(instance_hash text)
      RETURNS TABLE(tenant_id varchar, token_encrypted text) LANGUAGE sql SECURITY DEFINER
      SET search_path = pg_catalog, public AS $$
        SELECT c.tenant_id, c.evolution_token_encrypted FROM public.tenant_channels c
        WHERE c.evolution_instance_id_hash = instance_hash AND c.whatsapp_enabled = true LIMIT 1
      $$""")
    op.execute("REVOKE ALL ON FUNCTION public.tenant_channel_webhook_identity(text) FROM PUBLIC")


def downgrade() -> None:
    populated = op.get_bind().execute(
        sa.text("SELECT 1 FROM tenant_channels WHERE evolution_instance_id_encrypted IS NOT NULL LIMIT 1")
    ).first()
    if populated:
        raise RuntimeError("Disconnect tenant WhatsApp instances before downgrading")
    op.execute("DROP FUNCTION public.tenant_channel_webhook_identity(text)")
    op.drop_constraint("uq_tenant_channels_evolution_instance_id_hash", "tenant_channels", type_="unique")
    op.drop_column("tenant_channels", "evolution_instance_id_hash")
    op.drop_column("tenant_channels", "evolution_instance_id_encrypted")
    op.add_column("tenant_channels", sa.Column("evolution_instance_id", sa.String(128)))
    op.create_unique_constraint(
        "tenant_channels_evolution_instance_id_key", "tenant_channels", ["evolution_instance_id"]
    )
    op.execute("""CREATE FUNCTION public.tenant_channel_webhook_identity(instance text)
      RETURNS TABLE(tenant_id varchar, token_encrypted text) LANGUAGE sql SECURITY DEFINER
      SET search_path = pg_catalog, public AS $$
        SELECT c.tenant_id, c.evolution_token_encrypted FROM public.tenant_channels c
        WHERE c.evolution_instance_id = instance AND c.whatsapp_enabled = true LIMIT 1
      $$""")
    op.execute("REVOKE ALL ON FUNCTION public.tenant_channel_webhook_identity(text) FROM PUBLIC")
