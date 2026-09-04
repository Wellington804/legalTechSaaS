import asyncio
import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.services import evolution_manager


PNG = b"\x89PNG\r\n\x1a\nfixture"


class FakeClient:
    responses = []
    calls = []

    def __init__(self, *_, **__):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def request(self, method, url, *, headers, json=None):
        self.calls.append((method, url, headers, json))
        return self.responses.pop(0)


class EvolutionManagerTests(unittest.TestCase):
    def setUp(self):
        FakeClient.calls = []
        FakeClient.responses = []
        self.settings = SimpleNamespace(
            EVOLUTION_ENABLED=True,
            EVOLUTION_GO_URL="http://evolution-go:4000",
            EVOLUTION_API_KEY="global-key",
            NOTIFICATIONS_DRY_RUN=False,
            FRONTEND_URL="https://lexflow.example.com",
            API_V1_STR="/api/v1",
        )

    def test_connect_configures_webhook_and_returns_valid_png_qr(self):
        qr = "data:image/png;base64," + base64.b64encode(PNG).decode()
        FakeClient.responses = [httpx.Response(200, json={"data": {}}), httpx.Response(200, json={"data": {"qrcode": qr}})]
        with patch.object(evolution_manager, "settings", self.settings), patch.object(evolution_manager.httpx, "AsyncClient", FakeClient):
            result = asyncio.run(evolution_manager.connect("tenant-token"))
        self.assertEqual(result, qr)
        self.assertEqual(FakeClient.calls[0][2]["apikey"], "tenant-token")
        self.assertEqual(FakeClient.calls[0][3]["webhookUrl"], "https://lexflow.example.com/api/v1/notifications/webhooks/evolution")
        self.assertEqual(FakeClient.calls[0][3]["subscribe"], ["MESSAGE", "READ_RECEIPT", "CONNECTION", "QRCODE"])

    def test_instance_creation_uses_only_global_key_and_generated_instance_token(self):
        FakeClient.responses = [httpx.Response(200, json={"data": {"id": "instance-a"}})]
        with patch.object(evolution_manager, "settings", self.settings), patch.object(evolution_manager.httpx, "AsyncClient", FakeClient):
            asyncio.run(evolution_manager.ensure_instance("instance-a", "tenant-token"))
        self.assertEqual(FakeClient.calls[0][2]["apikey"], "global-key")
        self.assertEqual(FakeClient.calls[0][3]["token"], "tenant-token")

    def test_instance_creation_retry_accepts_only_the_exact_already_exists_response(self):
        FakeClient.responses = [httpx.Response(500, json={"error": "instance already exists"})]
        with patch.object(evolution_manager, "settings", self.settings), patch.object(evolution_manager.httpx, "AsyncClient", FakeClient):
            asyncio.run(evolution_manager.ensure_instance("instance-a", "tenant-token"))
        self.assertEqual(len(FakeClient.calls), 1)

    def test_invalid_provider_qr_is_rejected(self):
        FakeClient.responses = [httpx.Response(200, json={"data": {"qrcode": "data:text/html;base64,WA=="}})]
        with patch.object(evolution_manager, "settings", self.settings), patch.object(evolution_manager.httpx, "AsyncClient", FakeClient):
            with self.assertRaises(evolution_manager.EvolutionProviderError):
                asyncio.run(evolution_manager.qr_code("tenant-token"))

    def test_phone_number_is_extracted_without_device_suffix(self):
        self.assertEqual(evolution_manager.phone_from_jid("5511999999999:23@s.whatsapp.net"), "+5511999999999")

    def test_connection_webhooks_never_override_provider_truth(self):
        logged_in = {"connected": True, "logged_in": True}
        offline = {"connected": False, "logged_in": False}
        self.assertEqual(evolution_manager.verified_webhook_state("Disconnected", logged_in), "connected")
        self.assertEqual(evolution_manager.verified_webhook_state("PairSuccess", offline), "pending")
        self.assertEqual(evolution_manager.verified_webhook_state("LoggedOut", offline), "disconnected")


if __name__ == "__main__":
    unittest.main()
