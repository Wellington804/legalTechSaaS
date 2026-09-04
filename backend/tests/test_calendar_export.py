import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.calendar_export import render_tasks_ics


class CalendarExportTests(unittest.TestCase):
    def test_exports_due_tasks_and_escapes_injection(self):
        task = SimpleNamespace(
            id="1",
            title="Audiência, revisão\nX-FAKE:1",
            notes="Levar; documentos",
            location="Fórum",
            due_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
        )
        result = render_tasks_ics([task])
        self.assertIn("DTSTART:20260901T120000Z", result)
        self.assertNotIn("DTEND:", result)
        self.assertIn("SUMMARY:Audiência\\, revisão\\nX-FAKE:1", result)
        self.assertNotIn("\nX-FAKE:1\n", result)

    def test_folds_long_utf8_content_lines_without_breaking_characters(self):
        task = SimpleNamespace(
            id="2",
            title="Audiência " + "jurídica " * 20,
            notes=None,
            location=None,
            due_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
        )
        result = render_tasks_ics([task])
        physical_lines = result.split("\r\n")
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in physical_lines))
        unfolded = result.replace("\r\n ", "")
        self.assertIn("SUMMARY:Audiência " + "jurídica " * 20, unfolded)


if __name__ == "__main__":
    unittest.main()
