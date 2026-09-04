import unittest
from uuid import uuid4
from pydantic import ValidationError
from app.api.v1.endpoints.pilot import FeedbackInput
from app.core.config import Settings


class PilotInputTests(unittest.TestCase):
    def test_feedback_is_explicit_and_accepts_only_known_steps_and_areas(self):
        body = {"request_id": str(uuid4()), "kind": "weekly", "area": "dashboard", "message": "Consegui cadastrar", "consent": True}
        self.assertEqual(FeedbackInput(**body, completed_steps=["client", "client"]).completed_steps, ["client"])
        for changes in ({"consent": 1}, {"consent": False}, {"area": "/cases/private-id?token=secret"}, {"message": " "}, {"completed_steps": ["invented"]}, {"screenshot": "data:image/whatever"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                FeedbackInput(**(body | changes))

    def test_support_contact_never_accepts_active_schemes_or_private_destinations(self):
        for url in ("javascript:alert(1)", "http://support.test/help", "https://localhost/help", "https://127.0.0.1/help", "https://user:pass@support.test/help", "mailto:user@example.test?body=secret"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                Settings(_env_file=None, SUPPORT_URL=url)
        self.assertEqual(Settings(_env_file=None, SUPPORT_URL="mailto:support@example.test").SUPPORT_URL, "mailto:support@example.test")
