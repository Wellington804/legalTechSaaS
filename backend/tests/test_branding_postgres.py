"""Run against a migrated disposable database with a NOBYPASSRLS role."""
import os
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints import branding as api
from app.core.dependencies import _set_tenant_context
from app.models.branding import BrandAsset, BrandExport, BrandProfile, BrandVersion
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceDocument, WorkspaceDocumentVersion
from app.schemas.branding import BrandCreate, BrandExportInput, BrandRevision, BrandSettings, BrandUpdate
from app.services.workspace_service import ensure_document_storage_capacity


@unittest.skipUnless(os.environ.get("AUDIT_TEST_DATABASE_URL"), "Requires disposable PostgreSQL runtime-role database")
class BrandingPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["AUDIT_TEST_DATABASE_URL"], poolclass=NullPool)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        async with self.engine.connect() as conn:
            role = (await conn.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
            self.assertFalse(role.rolsuper or role.rolbypassrls, "Tests require enforced RLS")
            rows = (await conn.execute(text("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('brand_profiles','brand_versions','brand_assets','brand_exports')"))).all()
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row.relrowsecurity and row.relforcerowsecurity for row in rows))

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_publication_export_immutability_quota_and_cross_tenant_case_acl(self):
        tenant_id, other_tenant = str(uuid.uuid4()), str(uuid.uuid4())
        owner = User(id=str(uuid.uuid4()), tenant_id=tenant_id, full_name="Brand test", email=f"{uuid.uuid4()}@example.test", hashed_password="not-used", role="lawyer")
        stranger = User(id=str(uuid.uuid4()), tenant_id=tenant_id, full_name="Other lawyer", email=f"{uuid.uuid4()}@example.test", hashed_password="not-used", role="lawyer")
        async with self.Session() as db:
            db.add_all([Tenant(id=tenant_id, name="Brand test", slug=str(uuid.uuid4())), Tenant(id=other_tenant, name="Other brand test", slug=str(uuid.uuid4()))])
            await db.flush()
            db.add_all([owner, stranger])
            await db.flush()
            await _set_tenant_context(db, tenant_id)
            client = WorkspaceClient(tenant_id=tenant_id, name="Fictitious client")
            db.add(client)
            await db.flush()
            case = WorkspaceCase(tenant_id=tenant_id, client_id=client.id, title="Fictitious restricted case", responsible_user_id=owner.id, restricted=True)
            db.add(case)
            await db.flush()
            document = WorkspaceDocument(tenant_id=tenant_id, case_id=case.id, client_id=client.id, title="Test document", content_text="Texto original", content_format="plain")
            db.add(document)
            await db.flush()
            db.add(WorkspaceDocumentVersion(tenant_id=tenant_id, document_id=document.id, version=1, content_text=document.content_text, content_format="plain", created_by_user_id=owner.id))
            await db.commit()
            await _set_tenant_context(db, tenant_id)
            created = await api.create_profile(
                BrandCreate(name="Marca do advogado", settings={"header_fields": [], "footer_fields": []}),
                owner,
                db,
                owner,
            )
            profile_id = created["id"]
            await _set_tenant_context(db, tenant_id)
            with self.assertRaises(HTTPException) as unpublished:
                await api.create_export(document.id, BrandExportInput(expected_version=1), owner, db, owner)
            self.assertEqual(unpublished.exception.status_code, 422)
            await db.rollback()
            # rollback expires ORM instances; keep auth principals as detached request values.
        async with self.Session() as db:
            await _set_tenant_context(db, tenant_id)
            owner = await db.scalar(select(User).where(User.tenant_id == tenant_id, User.role == "lawyer").order_by(User.created_at).limit(1))
            case = await db.scalar(select(WorkspaceCase).where(WorkspaceCase.tenant_id == tenant_id))
            owner = await db.get(User, case.responsible_user_id)
            stranger = await db.scalar(select(User).where(User.tenant_id == tenant_id, User.id != owner.id))
            document = await db.scalar(select(WorkspaceDocument).where(WorkspaceDocument.tenant_id == tenant_id))
            document_id = document.id
            published = await api.publish(profile_id, BrandRevision(expected_revision=1), owner, db, owner)
            self.assertEqual(published["published_version"], 1)
            await _set_tenant_context(db, tenant_id)
            with patch.object(api, "render", AsyncMock(return_value=(b"docx-version-one", b"%PDF-version-one"))) as render:
                exported = await api.create_export(document_id, BrandExportInput(expected_version=1), owner, db, owner)
                await _set_tenant_context(db, tenant_id)
                repeated = await api.create_export(document_id, BrandExportInput(expected_version=1), owner, db, owner)
                self.assertEqual(repeated["id"], exported["id"])
                self.assertEqual(render.await_count, 1)
            changed = BrandSettings(primary_color="#112233").model_dump()
            draft = await api.update_profile(profile_id, BrandUpdate(name="Marca revisada", settings=changed, expected_revision=2), owner, db, owner)
            self.assertEqual(draft["published_version"], 1)
            await _set_tenant_context(db, tenant_id)
            v1 = await db.scalar(select(BrandVersion).where(BrandVersion.profile_id == profile_id))
            self.assertEqual(v1.settings["primary_color"], "#17324D")
            old = await api.download_export(exported["id"], owner, "pdf", db)
            self.assertEqual(old.body, b"%PDF-version-one")
            with self.assertRaises(HTTPException) as case_denied:
                await api.download_export(exported["id"], stranger, "pdf", db)
            self.assertEqual(case_denied.exception.status_code, 404)
            with self.assertRaises(HTTPException):
                await api.profile_for_editor(db, stranger, profile_id)
            asset = BrandAsset(tenant_id=tenant_id, profile_id=profile_id, kind="reference", filename="test.png", content_type="image/png", content=b"test", size=4, sha256="0"*64, analysis={}, created_by_user_id=owner.id)
            db.add(asset)
            await db.flush()
            await db.execute(update(Tenant).where(Tenant.id == tenant_id).values(quota_storage_bytes=1))
            with self.assertRaises(HTTPException) as quota:
                await ensure_document_storage_capacity(db, tenant_id, 1)
            self.assertEqual(quota.exception.status_code, 413)
            await db.commit()
        for model in (BrandVersion, BrandAsset, BrandExport):
            async with self.Session() as db:
                await _set_tenant_context(db, tenant_id)
                with self.assertRaises(DBAPIError):
                    await db.execute(update(model).where(model.tenant_id == tenant_id).values(created_by_user_id="changed"))
                await db.rollback()
        for context in (None, other_tenant):
            async with self.Session() as db:
                if context:
                    await _set_tenant_context(db, context)
                for model in (BrandProfile, BrandVersion, BrandAsset, BrandExport):
                    self.assertIsNone(await db.scalar(select(model).where(model.tenant_id == tenant_id)))


if __name__ == "__main__":
    unittest.main()
