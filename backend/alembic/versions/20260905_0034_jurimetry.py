"""Persist tenant-scoped descriptive jurimetry snapshots.

Revision ID: 20260905_0034
Revises: 20260905_0033
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0034"
down_revision = "20260905_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jurimetry_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("tribunal", sa.String(20), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("sample_limit", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("total_matches", sa.Integer(), nullable=True),
        sa.Column("total_relation", sa.String(8), nullable=False),
        sa.Column("source_name", sa.String(80), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("queried_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("universe", sa.String(1000), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "id", name="uq_jurimetry_snapshots_tenant_id"),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_jurimetry_snapshots_request"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_jurimetry_snapshots_creator_tenant",
        ),
        sa.CheckConstraint("sample_limit IN (50, 100, 200)", name="ck_jurimetry_snapshots_sample_limit"),
        sa.CheckConstraint(
            "sample_size >= 0 AND sample_size <= sample_limit",
            name="ck_jurimetry_snapshots_sample_size",
        ),
        sa.CheckConstraint(
            "total_matches IS NULL OR total_matches >= sample_size",
            name="ck_jurimetry_snapshots_total_matches",
        ),
        sa.CheckConstraint(
            "total_relation IN ('eq', 'gte', 'unknown')",
            name="ck_jurimetry_snapshots_total_relation",
        ),
    )
    op.create_index("ix_jurimetry_snapshots_tenant_id", "jurimetry_snapshots", ["tenant_id"])
    op.create_index("ix_jurimetry_snapshots_tribunal", "jurimetry_snapshots", ["tribunal"])
    op.create_index(
        "ix_jurimetry_snapshots_tenant_queried",
        "jurimetry_snapshots",
        ["tenant_id", "queried_at"],
    )
    policy = "tenant_id = nullif(current_setting('app.current_tenant', true), '')"
    op.execute("ALTER TABLE jurimetry_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jurimetry_snapshots FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY jurimetry_snapshots_tenant_isolation ON jurimetry_snapshots "
        f"USING ({policy}) WITH CHECK ({policy})"
    )
    op.execute(
        "CREATE FUNCTION prevent_jurimetry_snapshot_mutation() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'jurimetry snapshots are immutable'; END; $$"
    )
    op.execute(
        "CREATE TRIGGER jurimetry_snapshots_immutable "
        "BEFORE UPDATE OR DELETE ON jurimetry_snapshots "
        "FOR EACH ROW EXECUTE FUNCTION prevent_jurimetry_snapshot_mutation()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE jurimetry_snapshots NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jurimetry_snapshots DISABLE ROW LEVEL SECURITY")
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM jurimetry_snapshots)")).scalar():
        raise RuntimeError("Refusing to discard persisted jurimetry snapshots")
    op.execute("DROP TRIGGER IF EXISTS jurimetry_snapshots_immutable ON jurimetry_snapshots")
    op.execute("DROP FUNCTION IF EXISTS prevent_jurimetry_snapshot_mutation()")
    op.drop_table("jurimetry_snapshots")
