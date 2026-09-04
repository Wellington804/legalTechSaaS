import tempfile
import unittest
from pathlib import Path
from dotenv import dotenv_values

from app.cli.push_keys import configure
from app.core.config import Settings


class PushKeysTests(unittest.TestCase):
    def test_atomic_generation_preserves_existing_and_refuses_partial_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("# Keep me\nOTHER_SECRET='unchanged'\nWEB_PUSH_ENABLED=false\n", encoding="utf-8")
            self.assertTrue(configure(path, "mailto:local-test@example.invalid", enable=True))
            values = dotenv_values(path)
            self.assertEqual(values["OTHER_SECRET"], "unchanged")
            Settings(_env_file=None, ENVIRONMENT="test", **{k: v for k, v in values.items() if k.startswith("WEB_PUSH_")})
            before = path.read_bytes()
            self.assertFalse(configure(path, "mailto:different@example.invalid", enable=True))
            self.assertEqual(path.read_bytes(), before)
            path.write_text("WEB_PUSH_VAPID_PRIVATE_KEY=existing\n", encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                configure(path, "mailto:local-test@example.invalid", enable=True)
            self.assertEqual(path.read_bytes(), before)
