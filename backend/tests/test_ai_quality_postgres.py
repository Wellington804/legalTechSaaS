import asyncio
import os
import unittest
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.assistant import AIEvaluationCase
from app.models.tenant import Tenant
from app.models.user import User
from app.services.ai_quality import canonical_hash


AUDIT_TEST_DATABASE_URL = os.environ.get("AUDIT_TEST_DATABASE_URL")
TABLES = {
    "ai_evaluation_cases", "ai_evaluation_runs", "ai_evaluation_results",
    "document_intelligence_analyses", "document_intelligence_sources",
    "document_intelligence_consent_receipts",
}


@unittest.skipUnless(AUDIT_TEST_DATABASE_URL, "set AUDIT_TEST_DATABASE_URL to run PostgreSQL AI-quality RLS tests")
class AIQualityPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_async_engine(AUDIT_TEST_DATABASE_URL, poolclass=NullPool)
        cls.Session = async_sessionmaker(cls.engine, expire_on_commit=False)
        asyncio.run(cls._assert_rls())

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.engine.dispose())

    @classmethod
    async def _assert_rls(cls):
        async with cls.engine.connect() as connection:
            role = (await connection.execute(text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"))).one()
            rows = await connection.execute(text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN "
                "('ai_evaluation_cases','ai_evaluation_runs','ai_evaluation_results',"
                "'document_intelligence_analyses','document_intelligence_sources',"
                "'document_intelligence_consent_receipts')"
            ))
        if role.rolbypassrls or role.rolsuper:
            raise AssertionError("AUDIT_TEST_DATABASE_URL must use a NOBYPASSRLS runtime role")
        actual = {row.relname: (row.relrowsecurity, row.relforcerowsecurity) for row in rows}
        if actual != {table: (True, True) for table in TABLES}:
            raise AssertionError("AI quality tables must FORCE tenant RLS")

    @staticmethod
    async def _set_tenant(db, tenant_id):
        await db.execute(text("SELECT set_config('app.current_tenant', :tenant_id, true)"), {"tenant_id": tenant_id})

    def test_other_tenant_and_missing_context_cannot_read_gold_case(self):
        async def scenario():
            tenant_id, user_id, case_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
            content = {"sources": [], "questions": [], "gold_answers": []}
            async with self.Session() as db, db.begin():
                db.add(Tenant(id=tenant_id, name="AI quality", slug=str(uuid.uuid4())))
                db.add(User(id=user_id, tenant_id=tenant_id, full_name="Reviewer", email=f"{uuid.uuid4()}@example.test", hashed_password="unused", role="lawyer"))
                await db.flush()
                await self._set_tenant(db, tenant_id)
                db.add(AIEvaluationCase(
                    id=case_id, tenant_id=tenant_id, name="Caso gold", legal_area="civil", version=1,
                    status="draft", content=content, content_hash=canonical_hash(content), created_by_user_id=user_id,
                ))
            async with self.Session() as db, db.begin():
                await self._set_tenant(db, str(uuid.uuid4()))
                other = await db.scalar(select(AIEvaluationCase).where(AIEvaluationCase.id == case_id))
            async with self.Session() as db, db.begin():
                missing = await db.scalar(select(AIEvaluationCase).where(AIEvaluationCase.id == case_id))
            return other, missing

        other, missing = asyncio.run(scenario())
        self.assertIsNone(other)
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
