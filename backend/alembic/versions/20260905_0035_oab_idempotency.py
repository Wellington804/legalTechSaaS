"""Add retry-safe request identifiers to OAB user records.

Revision ID: 20260905_0035
Revises: 20260905_0034
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0035"
down_revision = "20260905_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("oab_enrollments", "oab_enrollment_checklist_items"):
        op.add_column(table, sa.Column("request_id", sa.String(36), nullable=True))
        op.execute(f"UPDATE {table} SET request_id = id WHERE request_id IS NULL")
        op.alter_column(table, "request_id", nullable=False)
    op.create_unique_constraint(
        "uq_oab_enrollments_owner_request", "oab_enrollments", ["tenant_id", "user_id", "request_id"]
    )
    op.create_unique_constraint(
        "uq_oab_checklist_owner_request",
        "oab_enrollment_checklist_items",
        ["tenant_id", "user_id", "enrollment_id", "request_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_oab_checklist_owner_request", "oab_enrollment_checklist_items", type_="unique")
    op.drop_constraint("uq_oab_enrollments_owner_request", "oab_enrollments", type_="unique")
    op.drop_column("oab_enrollment_checklist_items", "request_id")
    op.drop_column("oab_enrollments", "request_id")
