import asyncio
import os
import unittest
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceDocument, WorkspaceDocumentVersion


AUDIT_TEST_DATABASE_URL = os.environ.get("AUDIT_TEST_DATABASE_URL")
WORKSPACE_TABLES = {
    "workspace_clients",
    "workspace_cases",
    "workspace_case_access",
    "workspace_case_parties",
    "workspace_tasks",
    "workspace_documents",
    "workspace_document_versions",
    "workspace_library_entries",
    "workspace_publications",
    "workspace_ledger_entries",
}


@unittest.skipUnless(
    AUDIT_TEST_DATABASE_URL,
    "set AUDIT_TEST_DATABASE_URL to run PostgreSQL RLS workspace tests",
)
class WorkspacePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_async_engine(AUDIT_TEST_DATABASE_URL, poolclass=NullPool)
        cls.Session = async_sessionmaker(cls.engine, expire_on_commit=False)
        asyncio.run(cls._assert_runtime_rls())

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.engine.dispose())

    @classmethod
    async def _assert_runtime_rls(cls):
        async with cls.engine.connect() as connection:
            role = (
                await connection.execute(
                    text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
                )
            ).one_or_none()
            rows = await connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname IN ('workspace_clients', 'workspace_cases', "
                    "'workspace_case_access', 'workspace_case_parties', 'workspace_tasks', "
                    "'workspace_documents', 'workspace_document_versions', "
                    "'workspace_library_entries', 'workspace_publications', "
                    "'workspace_ledger_entries')"
                )
            )
        if not role or role.rolbypassrls or role.rolsuper:
            raise AssertionError("AUDIT_TEST_DATABASE_URL must use a NOBYPASSRLS runtime role")
        rls = {row.relname: (row.relrowsecurity, row.relforcerowsecurity) for row in rows}
        expected = {table: (True, True) for table in WORKSPACE_TABLES}
        if rls != expected:
            raise AssertionError("AUDIT_TEST_DATABASE_URL must enforce RLS on every workspace table")

    @staticmethod
    async def _set_tenant(db, tenant_id):
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )

    @classmethod
    async def _seed_case(cls):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        async with cls.Session() as db:
            async with db.begin():
                db.add(Tenant(id=tenant_id, name="Workspace test", slug=str(uuid.uuid4())))
                db.add(
                    User(
                        id=user_id,
                        tenant_id=tenant_id,
                        full_name="Workspace Test User",
                        email=f"{uuid.uuid4()}@example.test",
                        hashed_password="not-used-by-test",
                        role="admin",
                    )
                )
                await db.flush()
                await cls._set_tenant(db, tenant_id)
                client = WorkspaceClient(tenant_id=tenant_id, name="Cliente de teste", stage="client")
                db.add(client)
                await db.flush()
                case = WorkspaceCase(
                    tenant_id=tenant_id,
                    client_id=client.id,
                    title="Caso de teste",
                    responsible_user_id=user_id,
                )
                db.add(case)
                await db.flush()
                document = WorkspaceDocument(
                    tenant_id=tenant_id,
                    client_id=client.id,
                    case_id=case.id,
                    title="Memoria",
                    content_text="conteudo",
                )
                db.add(document)
                await db.flush()
                db.add(
                    WorkspaceDocumentVersion(
                        tenant_id=tenant_id,
                        document_id=document.id,
                        version=1,
                        content_text="conteudo",
                        created_by_user_id=user_id,
                    )
                )
        return tenant_id, case.id, document.id

    def test_other_tenant_and_missing_guc_cannot_read_case_or_document(self):
        async def scenario():
            owner_tenant, case_id, document_id = await self._seed_case()
            other_tenant = str(uuid.uuid4())
            async with self.Session() as db:
                async with db.begin():
                    db.add(Tenant(id=other_tenant, name="Other", slug=str(uuid.uuid4())))
                    await self._set_tenant(db, other_tenant)
                    other_case = await db.scalar(select(WorkspaceCase).where(WorkspaceCase.id == case_id))
                    other_document = await db.scalar(select(WorkspaceDocument).where(WorkspaceDocument.id == document_id))
            async with self.Session() as db:
                async with db.begin():
                    no_context_case = await db.scalar(select(WorkspaceCase).where(WorkspaceCase.id == case_id))
                    no_context_document = await db.scalar(select(WorkspaceDocument).where(WorkspaceDocument.id == document_id))
            return owner_tenant, other_case, other_document, no_context_case, no_context_document

        owner_tenant, other_case, other_document, no_context_case, no_context_document = asyncio.run(scenario())
        self.assertTrue(owner_tenant)
        self.assertIsNone(other_case)
        self.assertIsNone(other_document)
        self.assertIsNone(no_context_case)
        self.assertIsNone(no_context_document)


if __name__ == "__main__":
    unittest.main()
