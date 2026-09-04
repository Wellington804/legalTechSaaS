import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings
from app.core.observability import before_send, init_sentry


class ProductionSafetyTest(unittest.TestCase):
    def test_production_rejects_development_defaults(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(ENVIRONMENT="production", _env_file=None)

    def test_sentry_event_removes_request_secrets_and_pii(self) -> None:
        event = before_send(
            {
                "request": {
                    "headers": {"authorization": "Bearer secret"},
                    "data": {"cpf": "123.456.789-09"},
                    "url": "https://user:synthetic-password@app.example.test/api/v1/users?token=synthetic-token#synthetic-fragment",
                    "api_key": "synthetic-key",
                    "instanceToken": "synthetic-token",
                    "X-API-KEY": "synthetic-key",
                },
                "extra": {"instanceToken": "synthetic-token"},
                "contexts": {"request": {"api_key": "synthetic-key"}},
                "breadcrumbs": [{"message": "synthetic-private-context"}],
                "tags": {"client": "synthetic-private-context"},
                "user": {"id": "internal-uuid", "email": "client@example.test"},
                "message": "contact client@example.test using CPF 123.456.789-09",
                "exception": {
                    "values": [{"stacktrace": {"frames": [{"vars": {"password": "VerySecret123"}}]}}]
                },
            },
            {},
        )
        self.assertNotIn("headers", event["request"])
        self.assertNotIn("data", event["request"])
        self.assertEqual(event["request"]["url"], "https://app.example.test/api/v1/users")
        for key in ("api_key", "instanceToken", "X-API-KEY"):
            self.assertEqual(event["request"][key], "[Filtered]")
        for key in ("extra", "contexts", "breadcrumbs", "tags"):
            self.assertNotIn(key, event)
        self.assertEqual(event["user"], {"id": "internal-uuid"})
        self.assertNotIn("client@example.test", event["message"])
        self.assertNotIn("123.456.789-09", event["message"])
        self.assertNotIn("vars", event["exception"]["values"][0]["stacktrace"]["frames"][0])

    def test_sentry_rejects_malformed_request_url(self) -> None:
        event = before_send({"request": {"url": "https://[invalid?token=synthetic"}}, {})
        self.assertNotIn("url", event["request"])

    def test_sentry_is_error_only_and_initialization_is_idempotent(self) -> None:
        config = SimpleNamespace(
            SENTRY_DSN="https://synthetic@example.test/1", ENVIRONMENT="test", RELEASE="test-release"
        )
        with (
            patch("app.core.observability.settings", config),
            patch("app.core.observability.sentry_sdk.is_initialized", return_value=False),
            patch("app.core.observability.sentry_sdk.init") as initialize,
        ):
            init_sentry()
            self.assertEqual(initialize.call_args.kwargs["traces_sample_rate"], 0.0)
            self.assertFalse(initialize.call_args.kwargs["send_default_pii"])
        with (
            patch("app.core.observability.settings", config),
            patch("app.core.observability.sentry_sdk.is_initialized", return_value=True),
            patch("app.core.observability.sentry_sdk.init") as initialize,
        ):
            init_sentry()
            initialize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
