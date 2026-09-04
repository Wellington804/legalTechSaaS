import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests
import redis
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import encrypt_mfa_secret
from app.schemas.push import PushSubscriptionCreate, PushSubscriptionResponse, validate_endpoint
from app.services import push_provider as provider
from app.services.push_service import decrypt_subscription, encrypt_subscription


def key_pair():
    key = ec.generate_private_key(ec.SECP256R1())
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return encode(key.private_numbers().private_value.to_bytes(32, "big")), encode(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))


def subscription_data():
    _, public = key_pair()
    return {"endpoint": "https://fcm.googleapis.com/fcm/send/fictitious-test-only", "keys": {"p256dh": public, "auth": base64.urlsafe_b64encode(b"0123456789abcdef").decode().rstrip("=")}, "label": "Celular de teste", "consent": True}


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.last_ttl = None
        self.race_value = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, *, nx, ex):
        if self.race_value:
            self.values[key] = self.race_value
        self.last_ttl = ex
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True


class PushTests(unittest.TestCase):
    def setUp(self):
        self.cache = FakeRedis()
        self.redis_patch = patch.object(provider.redis.Redis, "from_url", return_value=self.cache)
        self.redis_patch.start()
        self.addCleanup(self.redis_patch.stop)

    def test_endpoint_boundaries(self):
        valid = subscription_data()["endpoint"]
        self.assertEqual(validate_endpoint(valid), valid)
        self.assertEqual(validate_endpoint(valid.replace("fcm.googleapis.com", "FCM.GOOGLEAPIS.COM:443")), valid)
        apple = "https://web.push.apple.com/Opaque%2FToken?opaque=1"
        self.assertEqual(validate_endpoint(apple), apple)
        for endpoint in ["http://fcm.googleapis.com/test", "https://localhost/test", "https://127.0.0.1/test", "https://169.254.169.254/latest", "https://fcm.googleapis.com.evil.test/test", "https://evil@fcm.googleapis.com/test", "https://fcm.googleapis.com:444/test", "https://fcm.googleapis.com/test#fragment", "https://fcm.googleapis.com/test?alias=1", "https://fcm.googleapis.com/%74est", "https://fcm.googleapis.com/a/../test", "https://fcm.googleapis.com\n/test", "https://fcm.googleapis.com/"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                validate_endpoint(endpoint)

    def test_explicit_consent_real_curve_keys_and_closed_schema(self):
        valid = subscription_data()
        self.assertEqual(PushSubscriptionCreate(**valid).label, valid["label"])
        for changes in [{"consent": False}, {"consent": 1}, {"consent": "true"}, {"tenant_id": "other"}, {"keys": {"p256dh": "A" * 87, "auth": valid["keys"]["auth"]}}, {"label": "\n"}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PushSubscriptionCreate(**(valid | changes))

    def test_encrypted_credentials_and_public_response(self):
        valid = subscription_data()
        encrypted = encrypt_subscription(valid["endpoint"], valid["keys"])
        self.assertNotIn("fcm.googleapis.com", encrypted)
        self.assertNotIn(valid["keys"]["auth"], encrypted)
        self.assertEqual(decrypt_subscription(encrypted), {"endpoint": valid["endpoint"], "keys": valid["keys"]})
        self.assertEqual(set(PushSubscriptionResponse.model_fields), {"id", "label", "endpoint_hash", "created_at", "last_seen_at", "expires_at"})

    def test_vapid_configuration_pair_validation(self):
        private, public = key_pair()
        valid = {"_env_file": None, "WEB_PUSH_ENABLED": True, "WEB_PUSH_VAPID_PUBLIC_KEY": public, "WEB_PUSH_VAPID_PRIVATE_KEY": private, "WEB_PUSH_VAPID_SUBJECT": "mailto:local-test@example.invalid"}
        self.assertTrue(Settings(**valid).WEB_PUSH_ENABLED)
        with self.assertRaises(ValidationError):
            Settings(**(valid | {"WEB_PUSH_VAPID_PUBLIC_KEY": key_pair()[1]}))
        with self.assertRaises(ValidationError):
            Settings(**(valid | {"WEB_PUSH_VAPID_SUBJECT": "javascript:alert(1)"}))
        with self.assertRaisesRegex(ValidationError, "real public contact"):
            Settings(**(valid | {"ENVIRONMENT": "production"}))

    def test_provider_classification_never_calls_accepted_delivered(self):
        for status, expected in [(201, "accepted"), (204, "accepted"), (302, "failed"), (403, "failed"), (404, "expired"), (410, "expired"), (429, "queued"), (500, "unknown")]:
            self.assertEqual(provider.classify_response(status).status, expected)

    def test_transport_disables_redirects_proxy_and_response_bodies(self):
        response = requests.Response()
        response.status_code = 201
        response._content = b"provider-private-data"
        response._content_consumed = True
        with provider._PushSession() as session, patch.object(requests.Session, "post", return_value=response) as post:
            self.assertFalse(session.trust_env)
            result = session.post(subscription_data()["endpoint"], data=b"ciphertext", allow_redirects=True)
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
            self.assertEqual(post.call_args.kwargs["timeout"], (5, 10))
            self.assertTrue(post.call_args.kwargs["stream"])
            self.assertEqual(result.content, b"")

    def test_real_encryption_with_mock_transport_and_opaque_payload(self):
        private, public = key_pair()
        config = SimpleNamespace(WEB_PUSH_ENABLED=True, WEB_PUSH_VAPID_PRIVATE_KEY=private, WEB_PUSH_VAPID_PUBLIC_KEY=public, WEB_PUSH_VAPID_SUBJECT="mailto:local-test@example.invalid", REDIS_URL="redis://unused-test")
        response = requests.Response()
        response.status_code = 201
        response._content = b""
        valid = subscription_data()
        with patch.object(provider, "settings", config), patch.object(provider._PushSession, "post", return_value=response) as post:
            result = provider.send_push(valid, "opaque-delivery-id")
            self.assertEqual(result.status, "accepted")
            self.assertNotIn(b"LegalFlow", post.call_args.kwargs["data"])
            self.assertIn("Authorization", post.call_args.kwargs["headers"])
        with patch.object(provider, "settings", config), patch.object(provider, "webpush", return_value=response) as push:
            provider.send_push(valid, "opaque-delivery-id")
            payload = json.loads(push.call_args.kwargs["data"])
            self.assertEqual(set(payload), {"title", "body", "url", "tag"})
            self.assertEqual(payload["url"], "/dashboard")
            self.assertNotIn("keys", payload)

    def test_timeout_ambiguity_not_retried_and_disabled_never_sends(self):
        private, _ = key_pair()
        config = SimpleNamespace(WEB_PUSH_ENABLED=True, WEB_PUSH_VAPID_PRIVATE_KEY=private, WEB_PUSH_VAPID_SUBJECT="mailto:local-test@example.invalid", REDIS_URL="redis://unused-test")
        with patch.object(provider, "settings", config), patch.object(provider, "webpush", side_effect=requests.ReadTimeout("secret endpoint must not be persisted")):
            result = provider.send_push(subscription_data(), "opaque")
            self.assertEqual(result.status, "unknown")
            self.assertFalse(result.retryable)
            self.assertNotIn("secret", result.error_code)
        config.WEB_PUSH_ENABLED = False
        with patch.object(provider, "settings", config), patch.object(provider, "webpush") as push:
            self.assertEqual(provider.send_push(subscription_data(), "opaque").status, "queued")
            push.assert_not_called()

    def test_vapid_token_shared_across_calls_and_race_winner_is_authoritative(self):
        private, _ = key_pair()
        first = provider._vapid_headers(private, "mailto:local-test@example.invalid", "https://web.push.apple.com")
        with patch.object(provider.Vapid, "sign") as sign:
            self.assertEqual(first, provider._vapid_headers(private, "mailto:local-test@example.invalid", "https://web.push.apple.com"))
            sign.assert_not_called()
        self.assertEqual(self.cache.last_ttl, 4 * 3600)
        self.assertNotIn(first["Authorization"], next(iter(self.cache.values.values())))
        winner = {"Authorization": "vapid-test-concurrent-winner"}
        self.cache.race_value = encrypt_mfa_secret(json.dumps(winner))
        self.assertEqual(winner, provider._vapid_headers(private, "mailto:local-test@example.invalid", "https://fcm.googleapis.com"))

    def test_cache_outage_fails_before_any_provider_request(self):
        private, _ = key_pair()
        config = SimpleNamespace(WEB_PUSH_ENABLED=True, WEB_PUSH_VAPID_PRIVATE_KEY=private, WEB_PUSH_VAPID_SUBJECT="mailto:local-test@example.invalid", REDIS_URL="redis://unused-test")
        with patch.object(provider, "settings", config), patch.object(provider.redis.Redis, "from_url", side_effect=redis.ConnectionError("private redis URI")), patch.object(provider, "webpush") as push:
            result = provider.send_push(subscription_data(), "opaque")
            self.assertEqual(result.status, "queued")
            self.assertTrue(result.retryable)
            self.assertEqual(result.error_code, "vapid_cache_unavailable")
            push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
