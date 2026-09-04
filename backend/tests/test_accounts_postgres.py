"""Opt-in integration check for the migrated account tables.

Set ACCOUNT_TEST_DATABASE_URL only to a disposable, already-migrated PostgreSQL
database. The test creates UUID-addressed rows and removes only those rows.
"""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.account import _create_email_token
from app.models.account import AccountToken, AuthSession, PrivacyRequest
from app.models.tenant import Tenant
from app.models.user import User


ACCOUNT_TEST_DATABASE_URL = os.getenv("ACCOUNT_TEST_DATABASE_URL")


@unittest.skipUnless(ACCOUNT_TEST_DATABASE_URL, "ACCOUNT_TEST_DATABASE_URL is not configured")
class AccountPostgresTests(unittest.TestCase):
    def test_persisted_session_is_isolated_by_tenant_rls(self):
        asyncio.run(self._run())

    def test_public_token_lookup_sets_the_only_tenant_context_needed_for_consumption(self):
        asyncio.run(self._run_public_token_lookup())

    async def _run(self):
        engine = create_async_engine(ACCOUNT_TEST_DATABASE_URL, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        privacy_id = str(uuid.uuid4())
        try:
            async with session_factory() as db:
                db.add_all(
                    [
                        Tenant(id=tenant_a, name="Account RLS A", slug=f"account-a-{tenant_a}"),
                        Tenant(id=tenant_b, name="Account RLS B", slug=f"account-b-{tenant_b}"),
                    ]
                )
                db.add(
                    User(
                        id=user_id,
                        tenant_id=tenant_a,
                        full_name="Account RLS",
                        email=f"account-{user_id}@example.test",
                        hashed_password="not-used-by-this-test",
                        role="admin",
                    )
                )
                await db.commit()
                await db.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": tenant_a},
                )
                db.add(
                    AuthSession(
                        id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_a,
                        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                    )
                )
                db.add(PrivacyRequest(id=privacy_id, tenant_id=tenant_a, requested_by_user_id=user_id, request_type="export", scope="self", status="received"))
                await db.commit()

                await db.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": tenant_b},
                )
                isolated = await db.scalar(select(AuthSession).where(AuthSession.id == session_id))
                self.assertIsNone(isolated)
                self.assertIsNone(await db.scalar(select(PrivacyRequest).where(PrivacyRequest.id == privacy_id)))
        finally:
            async with session_factory() as db:
                await db.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": tenant_a},
                )
                await db.execute(text("DELETE FROM auth_sessions WHERE id = :id"), {"id": session_id})
                await db.execute(text("DELETE FROM privacy_requests WHERE id = :id"), {"id": privacy_id})
                await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
                await db.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b})
                await db.commit()
            await engine.dispose()

    async def _run_public_token_lookup(self):
        engine = create_async_engine(ACCOUNT_TEST_DATABASE_URL, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        token_id = str(uuid.uuid4())
        try:
            async with session_factory() as db:
                db.add(Tenant(id=tenant_id, name="Public lookup", slug=f"lookup-{tenant_id}"))
                user = User(
                    id=user_id,
                    tenant_id=tenant_id,
                    full_name="Public lookup",
                    email=f"lookup-{user_id}@example.test",
                    hashed_password="not-used-by-this-test",
                    role="admin",
                )
                db.add(user)
                await db.commit()
                token, _ = await _create_email_token(
                    db,
                    user=user,
                    token_type="password_reset",
                    expires_in=timedelta(minutes=5),
                )
                token_id = token.id
                token_hash = token.token_hash
                await db.commit()

                looked_up_tenant = await db.scalar(
                    text(
                        "SELECT public.account_token_tenant_for_hash(:token_hash, :token_type)"
                    ),
                    {"token_hash": token_hash, "token_type": "password_reset"},
                )
                self.assertEqual(looked_up_tenant, tenant_id)
                await db.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": looked_up_tenant},
                )
                token = await db.scalar(
                    select(AccountToken)
                    .where(AccountToken.id == token_id, AccountToken.tenant_id == tenant_id)
                    .with_for_update()
                )
                self.assertIsNotNone(token)
        finally:
            async with session_factory() as db:
                await db.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": tenant_id},
                )
                await db.execute(text("DELETE FROM account_tokens WHERE id = :id"), {"id": token_id})
                await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
                await db.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
                await db.commit()
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
