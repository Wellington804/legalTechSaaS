import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260904_0030_calendar_autentique_hardening.py"
)
SPEC = importlib.util.spec_from_file_location("calendar_signature_migration_0030", MIGRATION_PATH)
MIGRATION = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MIGRATION)


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class EvidenceConnection:
    def __init__(self, validation_evidence: bool, pending_deletions: bool):
        self.values = [validation_evidence, pending_deletions]

    def execute(self, _statement):
        return ScalarResult(self.values.pop(0))


class CalendarSignatureMigrationTests(unittest.TestCase):
    def test_upgrade_marks_legacy_artifacts_unavailable_and_requeues_revalidation(self):
        statements = []

        def capture(statement):
            statements.append(str(statement))

        with patch.object(MIGRATION.op, "drop_constraint"), patch.object(
            MIGRATION.op, "create_check_constraint"
        ), patch.object(MIGRATION.op, "add_column"), patch.object(MIGRATION.op, "execute", side_effect=capture):
            MIGRATION.upgrade()
        sql = "\n".join(statements)
        self.assertIn("SET signed_validation_status = 'unavailable'", sql)
        self.assertIn("signed_file_hash IS NOT NULL", sql)
        self.assertIn("signed_validation_status IS DISTINCT FROM 'valid_integrity'", sql)

    def test_downgrade_stops_before_ddl_when_evidence_or_deletion_is_pending(self):
        for validation_evidence, pending_deletions in ((True, False), (False, True)):
            with self.subTest(validation_evidence=validation_evidence, pending_deletions=pending_deletions):
                connection = EvidenceConnection(validation_evidence, pending_deletions)
                with patch.object(MIGRATION.op, "get_bind", return_value=connection), patch.object(
                    MIGRATION.op, "execute"
                ) as execute, patch.object(MIGRATION.op, "drop_constraint") as drop_constraint, patch.object(
                    MIGRATION.op, "drop_column"
                ) as drop_column:
                    with self.assertRaises(RuntimeError):
                        MIGRATION.downgrade()
                execute.assert_not_called()
                drop_constraint.assert_not_called()
                drop_column.assert_not_called()


if __name__ == "__main__":
    unittest.main()
