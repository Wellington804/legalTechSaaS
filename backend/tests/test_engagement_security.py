import asyncio
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
from fastapi import Response
from pydantic import ValidationError
from app.api.v1.endpoints import engagement
from app.api.v1.endpoints.engagement import MessageInput, portal_token
from app.core.config import Settings, settings
from app.api.v1.endpoints.research import TRIBUNALS
from app.models.engagement import CaseMessage, TenantChannel
from app.models.workspace import WorkspaceDocumentVersion
from app.core.security import verify_totp_code


class EngagementSecurityTests(unittest.TestCase):
    def test_whatsapp_connect_restores_rls_context_after_provider_call(self):
        row = SimpleNamespace(
            tenant_id="tenant",
            evolution_instance_id_encrypted="encrypted-id",
            evolution_instance_id_hash="hashed-id",
            evolution_api_key_encrypted="encrypted-token",
            evolution_token_encrypted="encrypted-token",
            whatsapp_enabled=False,
            whatsapp_connection_state="disconnected",
            whatsapp_number=None,
            whatsapp_last_checked_at=None,
        )

        class FakeDB:
            context = True
            commits = 0

            async def scalar(self, _query):
                return object()

            async def get(self, _model, _key):
                return row

            async def commit(self):
                self.commits += 1
                if self.commits == 2 and not self.context:
                    raise AssertionError("tenant context was not restored after commit")
                self.context = False

        async def restore_context(db, _tenant_id):
            db.context = True

        db = FakeDB()
        user = SimpleNamespace(id="user", tenant_id="tenant", role="admin")
        with (
            patch.object(engagement, "ensure_tenant_write_access", new=AsyncMock()),
            patch.object(engagement, "audit", new=AsyncMock()),
            patch.object(engagement, "_set_tenant_context", side_effect=restore_context),
            patch.object(engagement, "_instance_id", return_value="instance"),
            patch.object(engagement, "_instance_token", return_value="token"),
            patch.object(engagement.evolution_manager, "configured", return_value=True),
            patch.object(engagement.evolution_manager, "ensure_instance", new=AsyncMock()),
            patch.object(engagement.evolution_manager, "connect", new=AsyncMock(return_value="data:image/png;base64,qr")),
        ):
            result = asyncio.run(engagement.connect_whatsapp(Response(), user, db))

        self.assertEqual(result["qr_code"], "data:image/png;base64,qr")
        self.assertEqual(db.commits, 2)

    def test_totp_non_ascii_digits_are_rejected_without_server_error(self):
        self.assertFalse(verify_totp_code("JBSWY3DPEHPK3PXP", "١٢٣٤٥٦", now=1700000000))

    def test_browser_cannot_submit_channel_secrets_and_message_identity_is_uuid(self):
        from app.api.v1.endpoints import engagement
        self.assertFalse(hasattr(engagement, "ChannelInput"))
        paths = {route.path for route in engagement.router.routes}
        self.assertNotIn("/whatsapp/connection-request", paths)
        self.assertIn("/whatsapp/connect", paths)
        self.assertIn("/whatsapp/connection", paths)
        with self.assertRaises(ValidationError):
            MessageInput(request_id="reused-string", body="Mensagem")
        with self.assertRaises(ValidationError):
            MessageInput(request_id="aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", body="   ")

    def test_whatsapp_instance_identifier_is_never_stored_in_plain_text(self):
        columns = TenantChannel.__table__.columns
        self.assertNotIn("evolution_instance_id", columns)
        self.assertIn("evolution_instance_id_encrypted", columns)
        self.assertIn("evolution_instance_id_hash", columns)

    def test_portal_tokens_have_distinct_audience_and_random_nonce(self):
        grant = SimpleNamespace(id="grant", tenant_id="tenant")
        token = portal_token(grant, "invite", timedelta(minutes=5))
        self.assertNotEqual(token, portal_token(grant, "invite", timedelta(minutes=5)))
        with self.assertRaises(jwt.InvalidAudienceError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], audience="legaltech-portal")
        self.assertEqual(claims["kind"], "invite")

    def test_fixed_datajud_destinations_and_blank_env_safety(self):
        self.assertIn("tjsp", TRIBUNALS)
        self.assertIn("tre-sp", TRIBUNALS)
        self.assertNotIn("stf", TRIBUNALS)
        self.assertNotIn("../../metadata", TRIBUNALS)
        self.assertTrue(Settings.model_config["env_ignore_empty"])
        with self.assertRaises(ValidationError):
            Settings(ENVIRONMENT="production", _env_file=None)

    def test_portal_and_delivery_references_include_tenant(self):
        for model, column, table in (
            (CaseMessage, "delivery_id", "notification_deliveries"),
            (WorkspaceDocumentVersion, "created_by_portal_grant_id", "portal_grants"),
        ):
            constraints = [fk for fk in model.__table__.foreign_key_constraints if column in fk.column_keys]
            self.assertEqual(len(constraints), 1)
            self.assertEqual(constraints[0].column_keys, ["tenant_id", column])
            self.assertEqual([e.target_fullname for e in constraints[0].elements], [f"{table}.tenant_id", f"{table}.id"])


if __name__ == "__main__":
    unittest.main()
