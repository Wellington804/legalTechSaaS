"""Persist real Clicksign dispatch references and immutable signed artifacts.

Revision ID: 20260904_0025
Revises: 20260904_0024
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0025"
down_revision = "20260904_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("signature_envelopes", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.add_column("signature_envelopes", sa.Column("provider_document_hash", sa.String(length=64), nullable=True))
    op.add_column("signature_envelopes", sa.Column("provider_envelope_id_encrypted", sa.Text(), nullable=True))
    op.add_column("signature_envelopes", sa.Column("provider_document_id_encrypted", sa.Text(), nullable=True))
    op.add_column("signature_envelopes", sa.Column("signed_filename", sa.String(length=255), nullable=True))
    op.add_column("signature_envelopes", sa.Column("signed_file_content", sa.LargeBinary(), nullable=True))
    op.add_column("signature_envelopes", sa.Column("signed_object_key", sa.String(length=512), nullable=True))
    op.add_column("signature_envelopes", sa.Column("signed_file_size", sa.Integer(), nullable=True))
    op.add_column("signature_envelopes", sa.Column("signed_file_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_signature_envelopes_request", "signature_envelopes", ["tenant_id", "request_hash"])
    op.create_unique_constraint(
        "uq_signature_envelopes_provider_document",
        "signature_envelopes",
        ["tenant_id", "provider", "provider_account_reference", "provider_document_hash"],
    )
    op.create_unique_constraint("uq_signature_envelopes_signed_object_key", "signature_envelopes", ["signed_object_key"])
    op.create_check_constraint(
        "ck_signature_envelopes_signed_file_size",
        "signature_envelopes",
        "signed_file_size IS NULL OR signed_file_size > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_signature_envelopes_signed_file_size", "signature_envelopes", type_="check")
    op.drop_constraint("uq_signature_envelopes_signed_object_key", "signature_envelopes", type_="unique")
    op.drop_constraint("uq_signature_envelopes_provider_document", "signature_envelopes", type_="unique")
    op.drop_constraint("uq_signature_envelopes_request", "signature_envelopes", type_="unique")
    for column in (
        "signed_file_hash",
        "signed_file_size",
        "signed_object_key",
        "signed_file_content",
        "signed_filename",
        "provider_document_id_encrypted",
        "provider_envelope_id_encrypted",
        "provider_document_hash",
        "request_hash",
    ):
        op.drop_column("signature_envelopes", column)
