"""Manual-date boundaries can be checked without a database or a provider."""
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.schemas.routine import OutcomeCreate, ReminderSet
from app.schemas.workspace import TaskCreate, TaskUpdate
from app.services.routine_service import CHECKLISTS


class RoutineInputTests(unittest.TestCase):
    def test_strict_manual_schedule_and_bounded_plain_text(self):
        with self.assertRaises(ValidationError):
            ReminderSet(remind_at="2026-09-01T10:00:00", expected_revision=1)
        with self.assertRaises(ValidationError):
            ReminderSet(remind_at=datetime.now(timezone.utc), expected_revision=1, user_id="other")
        with self.assertRaises(ValidationError):
            TaskCreate(title="Diligência", notes="x" * 5001)
        with self.assertRaises(ValidationError):
            OutcomeCreate(request_id="00000000-0000-0000-0000-000000000001", title="Resultado", content_text="<script>alert(1)</script>")
        self.assertEqual(TaskUpdate(expected_revision=1, location=None).model_dump(exclude_unset=True)["location"], None)
        self.assertEqual(set(CHECKLISTS), {"intake", "documents", "hearing"})
        self.assertTrue(all(len(item["items"]) == 4 for item in CHECKLISTS.values()))


if __name__ == "__main__":
    unittest.main()
