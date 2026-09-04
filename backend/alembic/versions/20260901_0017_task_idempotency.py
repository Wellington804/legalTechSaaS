"""Add tenant-scoped idempotency keys to workspace tasks.

Revision ID: 20260901_0017
Revises: 20260830_0016
"""
from alembic import op
import sqlalchemy as sa


revision = "20260901_0017"
down_revision = "20260830_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_tasks", sa.Column("request_id", sa.String(36)))
    op.create_unique_constraint(
        "uq_workspace_tasks_request_id", "workspace_tasks", ["tenant_id", "request_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_workspace_tasks_request_id", "workspace_tasks", type_="unique")
    op.drop_column("workspace_tasks", "request_id")
