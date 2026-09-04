import unittest
from unittest.mock import AsyncMock, patch
from app.cli.verify_restore import validate_targets, verify


class RestoreVerifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_isolated_readonly_target_and_document_evidence_are_required(self):
        source = "postgresql+asyncpg://admin:unused@localhost/source"
        target = "postgresql+asyncpg://admin:unused@localhost/legaltech_restore_test"
        validate_targets(source, target)
        with self.assertRaises(ValueError):
            validate_targets(source, source)
        snapshot = {"workspace_document_versions": {"count": 1, "sha256": "same", "file_bytes": 10}}
        with patch("app.cli.verify_restore.snapshot", AsyncMock(side_effect=[snapshot, snapshot])):
            self.assertEqual((await verify(source, target))["document_rows"], 1)
        with patch("app.cli.verify_restore.snapshot", AsyncMock(side_effect=[snapshot, {"workspace_document_versions": {"count": 1, "sha256": "tampered"}}])):
            with self.assertRaises(ValueError):
                await verify(source, target)
        with patch("app.cli.verify_restore.snapshot", AsyncMock(return_value={"users": {"count": 1, "sha256": "same"}})):
            with self.assertRaises(ValueError):
                await verify(source, target)
        with patch("app.cli.verify_restore.snapshot", AsyncMock(return_value={"workspace_document_versions": {"count": 1, "sha256": "same", "file_bytes": 0}})):
            with self.assertRaises(ValueError):
                await verify(source, target)
