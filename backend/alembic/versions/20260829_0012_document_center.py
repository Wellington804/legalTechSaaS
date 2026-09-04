"""document center folders, object storage and portal sharing

Revision ID: 20260829_0012
Revises: 20260829_0011
"""
from alembic import op
import sqlalchemy as sa


revision = "20260829_0012"
down_revision = "20260829_0011"
branch_labels = None
depends_on = None


def _tenant_table(table: str) -> None:
    policy = "tenant_id = nullif(current_setting('app.current_tenant', true), '')"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {table}_tenant_isolation ON {table} USING ({policy}) WITH CHECK ({policy})")


def upgrade() -> None:
    op.create_table(
        "workspace_document_folders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_document_folders_tenant_id"),
        sa.ForeignKeyConstraint(["tenant_id", "client_id"], ["workspace_clients.tenant_id", "workspace_clients.id"], name="fk_workspace_document_folders_client_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "case_id"], ["workspace_cases.tenant_id", "workspace_cases.id"], name="fk_workspace_document_folders_case_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "parent_id"], ["workspace_document_folders.tenant_id", "workspace_document_folders.id"], name="fk_workspace_document_folders_parent_tenant", ondelete="RESTRICT"),
    )
    for column in ("tenant_id", "client_id", "case_id", "parent_id", "archived_at"):
        op.create_index(f"ix_workspace_document_folders_{column}", "workspace_document_folders", [column])
    op.execute("CREATE UNIQUE INDEX uq_workspace_document_folder_sibling_active ON workspace_document_folders (tenant_id, client_id, COALESCE(case_id, ''), COALESCE(parent_id, ''), normalized_name) WHERE archived_at IS NULL")

    op.add_column("workspace_documents", sa.Column("folder_id", sa.String(), nullable=True))
    op.add_column("workspace_documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workspace_documents", sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_workspace_documents_folder_id", "workspace_documents", ["folder_id"])
    op.create_index("ix_workspace_documents_deleted_at", "workspace_documents", ["deleted_at"])
    op.create_index("ix_workspace_documents_purge_after", "workspace_documents", ["purge_after"])
    op.create_foreign_key("fk_workspace_documents_folder_tenant", "workspace_documents", "workspace_document_folders", ["tenant_id", "folder_id"], ["tenant_id", "id"], ondelete="RESTRICT")
    op.execute("CREATE INDEX ix_workspace_documents_search ON workspace_documents USING gin (to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(filename, '') || ' ' || coalesce(content_text, '')))")

    op.add_column("workspace_document_versions", sa.Column("object_key", sa.String(512), nullable=True))
    op.add_column("workspace_document_versions", sa.Column("storage_status", sa.String(24), nullable=False, server_default="available"))
    op.add_column("workspace_document_versions", sa.Column("ocr_status", sa.String(24), nullable=False, server_default="not_required"))
    op.add_column("workspace_document_versions", sa.Column("processing_error", sa.String(500), nullable=True))
    op.create_unique_constraint("uq_workspace_document_versions_object_key", "workspace_document_versions", ["object_key"])
    op.create_index("ix_workspace_document_versions_storage_status", "workspace_document_versions", ["storage_status"])
    op.create_check_constraint("ck_workspace_document_versions_storage_status", "workspace_document_versions", "storage_status IN ('processing','available','quarantined','failed','deleted')")
    op.create_check_constraint("ck_workspace_document_versions_ocr_status", "workspace_document_versions", "ocr_status IN ('pending','processing','complete','not_required','failed')")

    op.alter_column("brand_exports", "docx", existing_type=sa.LargeBinary(), nullable=True)
    op.alter_column("brand_exports", "pdf", existing_type=sa.LargeBinary(), nullable=True)
    op.add_column("brand_exports", sa.Column("docx_object_key", sa.String(512), nullable=True))
    op.add_column("brand_exports", sa.Column("pdf_object_key", sa.String(512), nullable=True))
    op.add_column("brand_exports", sa.Column("docx_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("brand_exports", sa.Column("pdf_size", sa.Integer(), nullable=False, server_default="0"))
    op.create_unique_constraint("uq_brand_exports_docx_object_key", "brand_exports", ["docx_object_key"])
    op.create_unique_constraint("uq_brand_exports_pdf_object_key", "brand_exports", ["pdf_object_key"])
    op.execute("UPDATE brand_exports SET docx_size = octet_length(docx), pdf_size = octet_length(pdf)")

    op.create_table(
        "workspace_document_uploads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("expected_version", sa.Integer(), nullable=True),
        sa.Column("folder_id", sa.String(), nullable=True),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("expected_size", sa.Integer(), nullable=False),
        sa.Column("expected_sha256", sa.String(64), nullable=True),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.Column("created_by_portal_grant_id", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_workspace_document_uploads_tenant_id"),
        sa.UniqueConstraint("object_key", name="uq_workspace_document_uploads_object_key"),
        sa.CheckConstraint("status IN ('created','uploaded','processing','completed','failed','expired')", name="ck_workspace_document_uploads_status"),
        sa.CheckConstraint("expected_size > 0 AND expected_size <= 26214400", name="ck_workspace_document_uploads_size"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"], name="fk_workspace_document_uploads_document_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "folder_id"], ["workspace_document_folders.tenant_id", "workspace_document_folders.id"], name="fk_workspace_document_uploads_folder_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"], name="fk_workspace_document_uploads_user_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_portal_grant_id"], ["portal_grants.tenant_id", "portal_grants.id"], name="fk_workspace_document_uploads_portal_tenant"),
    )
    for column in ("tenant_id", "document_id", "folder_id", "client_id", "case_id", "status", "expires_at"):
        op.create_index(f"ix_workspace_document_uploads_{column}", "workspace_document_uploads", [column])

    op.create_table(
        "portal_folder_shares",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("grant_id", sa.String(), nullable=False),
        sa.Column("folder_id", sa.String(), nullable=False),
        sa.Column("can_upload", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_portal_folder_shares_tenant_id"),
        sa.UniqueConstraint("tenant_id", "grant_id", "folder_id", name="uq_portal_folder_share"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "grant_id"], ["portal_grants.tenant_id", "portal_grants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "folder_id"], ["workspace_document_folders.tenant_id", "workspace_document_folders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
    )
    for column in ("tenant_id", "grant_id", "folder_id", "revoked_at"):
        op.create_index(f"ix_portal_folder_shares_{column}", "portal_folder_shares", [column])

    for table in ("workspace_document_folders", "workspace_document_uploads", "portal_folder_shares"):
        _tenant_table(table)
    op.execute("""
        CREATE FUNCTION document_lifecycle_candidates(max_rows integer)
        RETURNS TABLE(tenant_id text, document_id text, object_key text)
        LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
          SELECT d.tenant_id, d.id, v.object_key
          FROM workspace_documents d
          JOIN workspace_document_versions v ON v.tenant_id = d.tenant_id AND v.document_id = d.id
          WHERE d.purge_after <= now() AND v.object_key IS NOT NULL AND v.storage_status <> 'deleted'
          ORDER BY d.purge_after, v.version
          LIMIT LEAST(GREATEST(max_rows, 1), 1000)
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION document_lifecycle_candidates(integer) FROM PUBLIC")
    op.execute("""
        CREATE FUNCTION mark_document_object_deleted(request_tenant text, request_document text, request_key text)
        RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM workspace_documents WHERE tenant_id = request_tenant AND id = request_document AND purge_after <= now()) THEN
            RETURN false;
          END IF;
          UPDATE workspace_document_versions SET object_key = NULL, file_content = NULL, content_text = NULL,
            storage_status = 'deleted', processing_error = NULL
          WHERE tenant_id = request_tenant AND document_id = request_document AND object_key = request_key;
          IF NOT FOUND THEN RETURN false; END IF;
          IF NOT EXISTS (SELECT 1 FROM workspace_document_versions WHERE tenant_id = request_tenant AND document_id = request_document AND storage_status <> 'deleted') THEN
            UPDATE workspace_documents SET file_content = NULL, content_text = NULL, filename = NULL, file_size = NULL, sha256_hash = NULL
            WHERE tenant_id = request_tenant AND id = request_document;
          END IF;
          RETURN true;
        END $$
    """)
    op.execute("REVOKE ALL ON FUNCTION mark_document_object_deleted(text, text, text) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS mark_document_object_deleted(text, text, text)")
    op.execute("DROP FUNCTION IF EXISTS document_lifecycle_candidates(integer)")
    connection = op.get_bind()
    for table in ("workspace_document_uploads", "portal_folder_shares", "workspace_document_folders"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} LIMIT 1)")).scalar():
            raise RuntimeError(f"Refusing to drop populated {table}")
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM workspace_document_versions WHERE object_key IS NOT NULL LIMIT 1)")).scalar():
        raise RuntimeError("Refusing to remove object storage pointers")
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM brand_exports WHERE docx_object_key IS NOT NULL OR pdf_object_key IS NOT NULL LIMIT 1)")).scalar():
        raise RuntimeError("Refusing to remove exported object storage pointers")
    op.drop_table("portal_folder_shares")
    op.drop_table("workspace_document_uploads")
    for constraint in ("ck_workspace_document_versions_ocr_status", "ck_workspace_document_versions_storage_status", "uq_workspace_document_versions_object_key"):
        op.drop_constraint(constraint, "workspace_document_versions", type_="check" if constraint.startswith("ck_") else "unique")
    op.drop_index("ix_workspace_document_versions_storage_status", table_name="workspace_document_versions")
    for column in ("processing_error", "ocr_status", "storage_status", "object_key"):
        op.drop_column("workspace_document_versions", column)
    for constraint in ("uq_brand_exports_docx_object_key", "uq_brand_exports_pdf_object_key"):
        op.drop_constraint(constraint, "brand_exports", type_="unique")
    for column in ("pdf_size", "docx_size", "pdf_object_key", "docx_object_key"):
        op.drop_column("brand_exports", column)
    op.alter_column("brand_exports", "pdf", existing_type=sa.LargeBinary(), nullable=False)
    op.alter_column("brand_exports", "docx", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_constraint("fk_workspace_documents_folder_tenant", "workspace_documents", type_="foreignkey")
    op.drop_index("ix_workspace_documents_search", table_name="workspace_documents")
    for column in ("purge_after", "deleted_at", "folder_id"):
        op.drop_column("workspace_documents", column)
    op.drop_table("workspace_document_folders")
