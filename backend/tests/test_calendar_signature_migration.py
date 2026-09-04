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
        self.validation_evidence = validation_evidence
        self.pending_deletions = pending_deletions
        self.statements = []

    def execute(self, statement):
        sql = " ".join(str(statement).split())
        self.statements.append(sql)
        if "FROM signature_envelopes" in sql:
            return ScalarResult(self.validation_evidence)
        if "FROM calendar_task_links" in sql:
            return ScalarResult(self.pending_deletions)
        return ScalarResult(None)


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
        self.assertIn("CREATE OR REPLACE FUNCTION clicksign_signature_event_candidates", sql)
        self.assertIn("event.provider IN ('clicksign', 'clicksign-sandbox')", sql)
        self.assertIn("REVOKE ALL ON FUNCTION clicksign_signature_event_candidates(integer) FROM PUBLIC", sql)

        grant_script = (
            Path(__file__).resolve().parents[2] / "deploy" / "postgres" / "grant-runtime-role.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'GRANT EXECUTE ON FUNCTION clicksign_signature_event_candidates(integer) TO :"app_user";',
            grant_script,
        )

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
                self.assertEqual(
                    connection.statements[:4],
                    [
                        "ALTER TABLE signature_envelopes NO FORCE ROW LEVEL SECURITY",
                        "ALTER TABLE signature_envelopes DISABLE ROW LEVEL SECURITY",
                        "ALTER TABLE calendar_task_links NO FORCE ROW LEVEL SECURITY",
                        "ALTER TABLE calendar_task_links DISABLE ROW LEVEL SECURITY",
                    ],
                )
                self.assertFalse(any(" ENABLE ROW LEVEL SECURITY" in sql for sql in connection.statements))

    def test_downgrade_reenables_rls_before_any_destructive_ddl(self):
        connection = EvidenceConnection(False, False)
        ddl = []
        with patch.object(MIGRATION.op, "get_bind", return_value=connection), patch.object(
            MIGRATION.op, "execute", side_effect=lambda statement: ddl.append(str(statement))
        ), patch.object(MIGRATION.op, "drop_constraint"), patch.object(
            MIGRATION.op, "drop_column"
        ), patch.object(MIGRATION.op, "create_check_constraint"):
            MIGRATION.downgrade()

        self.assertEqual(
            connection.statements[-4:],
            [
                "ALTER TABLE signature_envelopes ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE signature_envelopes FORCE ROW LEVEL SECURITY",
                "ALTER TABLE calendar_task_links ENABLE ROW LEVEL SECURITY",
                "ALTER TABLE calendar_task_links FORCE ROW LEVEL SECURITY",
            ],
        )
        self.assertTrue(ddl)
        self.assertIn("DROP FUNCTION clicksign_signature_event_candidates(integer)", ddl[0])


if __name__ == "__main__":
    unittest.main()
