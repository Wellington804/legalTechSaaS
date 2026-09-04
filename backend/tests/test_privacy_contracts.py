import unittest
from pydantic import ValidationError

from app.api.v1.endpoints.account import PrivacySettingsUpdate
from app.schemas.operations import PublicIntakeConfigUpsert


class PrivacyContractTests(unittest.TestCase):
    def test_active_public_intake_requires_https_notice(self):
        base = {"enabled": True, "form_title": "Atendimento", "notice_version": "2026-01", "consent_version": "2026-01"}
        with self.assertRaises(ValidationError):
            PublicIntakeConfigUpsert(**base)
        with self.assertRaises(ValidationError):
            PublicIntakeConfigUpsert(**base, notice_url="http://example.test/privacy")
        self.assertEqual(PublicIntakeConfigUpsert(**base, notice_url="https://example.test/privacy").notice_url, "https://example.test/privacy")

    def test_tenant_privacy_settings_reject_unsafe_url_and_retention(self):
        with self.assertRaises(ValidationError):
            PrivacySettingsUpdate(privacy_notice_url="https://user:secret@example.test/privacy")
        with self.assertRaises(ValidationError):
            PrivacySettingsUpdate(data_retention_days=10)


if __name__ == "__main__":
    unittest.main()
