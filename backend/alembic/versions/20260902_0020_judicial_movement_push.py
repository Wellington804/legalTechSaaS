"""Allow privacy-safe push delivery for new judicial movements.

Revision ID: 20260902_0020
Revises: 20260902_0019
"""

from alembic import op
import sqlalchemy as sa


revision = "20260902_0020"
down_revision = "20260902_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_push_delivery_kind", "push_deliveries", type_="check")
    op.create_check_constraint(
        "ck_push_delivery_kind",
        "push_deliveries",
        "kind IN ('task_assigned','portal_message','portal_document','test','task_reminder','judicial_movement')",
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM push_deliveries WHERE kind = 'judicial_movement')"
    )).scalar():
        raise RuntimeError("Refusing to discard judicial movement push history")
    op.drop_constraint("ck_push_delivery_kind", "push_deliveries", type_="check")
    op.create_check_constraint(
        "ck_push_delivery_kind",
        "push_deliveries",
        "kind IN ('task_assigned','portal_message','portal_document','test','task_reminder')",
    )
