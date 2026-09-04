import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.schemas.workspace import CaseCreate, CaseUpdate, ClientCreate, ClientImport, DocumentFolderCreate, DocumentFolderUpdate, DocumentUpdate, LedgerEntryCreate, ManualPaymentCreate, TaskCreate, TaskUpdate, normalize_phone
from app.services.document_storage import object_key, quarantine_key
from app.services.workspace_service import case_access_clause, document_version_bytes, require_finance_role, validate_upload_bytes
from app.api.v1.endpoints.workspace import daily_priority_items, daily_time_context, priority_actions, summarize_task_dates, task_values_match
from app.models.workspace import WorkspaceTask


class WorkspaceSchemaTests(unittest.TestCase):
    def test_requests_reject_unknown_fields_and_whitespace_names(self):
        with self.assertRaises(ValidationError):
            ClientCreate(name="Cliente", stage="client", invented=True)
        with self.assertRaises(ValidationError):
            ClientCreate(name="   ")

    def test_phone_normalizes_brazilian_input_and_keeps_explicit_international_numbers(self):
        for value in ("11999999999", "(11) 99999-9999", "5511999999999", "+55 (11) 99999-9999", "011999999999"):
            self.assertEqual(normalize_phone(value), "+5511999999999")
        self.assertEqual(ClientCreate(name="Cliente", phone="(11) 99999-9999").phone, "+5511999999999")
        self.assertEqual(normalize_phone("+14155552671"), "+14155552671")
        with self.assertRaises(ValueError):
            normalize_phone("999999999")

    def test_legal_representative_is_optional_but_requires_name_when_enabled(self):
        client = ClientCreate(
            name="Empresa Cliente",
            person_type="company",
            has_legal_representative=True,
            representative_name="Ana Representante",
            representative_tax_id="123.456.789-01",
            representative_qualification="brasileira, empresária",
            representative_email="ana@example.com",
            representative_phone="(11) 99999-9999",
            representative_address={"street": "Rua Dois", "number": "20", "city": "São Paulo", "state": "SP", "postal_code": "01000-001"},
        )
        self.assertEqual(client.representative_tax_id, "12345678901")
        self.assertEqual(client.representative_phone, "+5511999999999")
        self.assertEqual(client.representative_address.city, "São Paulo")
        cleared = ClientCreate(name="Empresa sem representante", representative_name="Ignorar")
        self.assertFalse(cleared.has_legal_representative)
        self.assertIsNone(cleared.representative_name)
        with self.assertRaises(ValidationError):
            ClientCreate(name="Empresa incompleta", has_legal_representative=True)

    def test_document_updates_require_a_concurrency_token(self):
        with self.assertRaises(ValidationError):
            DocumentUpdate(content_text="revisao")
        self.assertEqual(DocumentUpdate(content_text="revisao", expected_version=2).expected_version, 2)
        self.assertEqual(DocumentUpdate(content_text="revisao", expected_revision=2).expected_revision, 2)

    def test_document_center_validates_names_content_and_opaque_keys(self):
        self.assertEqual(DocumentFolderCreate(client_id="c1", name="  Contratos   assinados ").name, "Contratos assinados")
        self.assertEqual(DocumentFolderUpdate(name="Petições", expected_revision=1).name, "Petições")
        with self.assertRaises(ValidationError):
            DocumentFolderCreate(client_id="c1", name="cliente/segredo")
        self.assertEqual(validate_upload_bytes("nota.txt", "ação".encode())[1], "text/plain")
        with self.assertRaises(HTTPException):
            validate_upload_bytes("falso.pdf", b"nao e pdf")
        self.assertEqual(quarantine_key("tenant-a", "upload-a"), "quarantine/tenant-a/upload-a")
        self.assertEqual(object_key("tenant-a", "doc-a", "version-a"), "documents/tenant-a/doc-a/version-a")

    def test_task_and_financial_statuses_are_closed_sets(self):
        self.assertEqual(CaseCreate(client_id="client-a", title="Caso", responsible_user_id="user-a").status, "open")
        with self.assertRaises(ValidationError):
            CaseUpdate(title="Caso alterado")
        self.assertEqual(TaskCreate(title="Revisar prazo").status, "pending")
        self.assertEqual(
            TaskCreate(title="Revisar prazo", request_id="66bc64d5-a827-487f-9d0a-d4d816fa51c1").request_id,
            UUID("66bc64d5-a827-487f-9d0a-d4d816fa51c1"),
        )
        with self.assertRaises(ValidationError):
            TaskUpdate(title="Revisar prazo")
        with self.assertRaises(ValidationError):
            TaskCreate(title="Revisar prazo", status="anything")
        with self.assertRaises(ValidationError):
            TaskCreate(title="Revisar prazo", due_at="2026-08-28T09:00:00")
        with self.assertRaises(ValidationError):
            LedgerEntryCreate(entry_type="payment", amount="10", description="Pagamento")
        with self.assertRaises(ValidationError):
            ManualPaymentCreate(amount="10", description="Pagamento", confirmation_reason="Caixa confirmado")

    def test_paralegal_cannot_access_financial_endpoints(self):
        with self.assertRaises(HTTPException) as caught:
            require_finance_role(SimpleNamespace(role="paralegal"))
        self.assertEqual(caught.exception.status_code, 403)

    def test_case_acl_clause_keeps_restricted_membership_condition(self):
        clause = case_access_clause(SimpleNamespace(id="user-a", tenant_id="tenant-a", role="lawyer"))
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("workspace_cases.restricted IS false", sql)
        self.assertIn("workspace_case_access.user_id = 'user-a'", sql)

    def test_import_is_bounded_and_document_storage_uses_utf8_bytes(self):
        self.assertEqual(document_version_bytes("ação", b"pdf"), len("ação".encode("utf-8")) + 3)
        with self.assertRaises(ValidationError):
            ClientImport(items=[{"name": "Cliente"}] * 201)

    def test_task_summary_uses_sao_paulo_day_at_utc_midnight_edge(self):
        now = datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)  # 22:00 on 27/08 in Sao Paulo
        records = [
            SimpleNamespace(status="pending", kind="task", due_at=datetime(2026, 8, 28, 2, 30, tzinfo=timezone.utc)),  # 23:30 local, today
            SimpleNamespace(status="pending", kind="hearing", due_at=datetime(2026, 8, 28, 3, 30, tzinfo=timezone.utc)),  # 00:30 local, upcoming
            SimpleNamespace(status="pending", kind="deadline", due_at=datetime(2026, 8, 28, 0, 30, tzinfo=timezone.utc)),  # 21:30 local, overdue
        ]
        self.assertEqual(summarize_task_dates(records, now), {"overdue": 1, "due_today": 1, "upcoming": 1, "completed": 0, "hearings_upcoming": 1})

    def test_daily_context_uses_the_office_timezone(self):
        now = datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)
        office_tz, utc_now, tomorrow = daily_time_context("America/Sao_Paulo", now)
        self.assertEqual(office_tz.key, "America/Sao_Paulo")
        self.assertEqual(utc_now, now)
        self.assertEqual(tomorrow, datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc))

    def test_daily_actions_follow_existing_write_permissions(self):
        task = {"source": "task", "assigned_user_id": "user-a"}
        self.assertEqual(priority_actions(task, SimpleNamespace(role="lawyer", id="user-b")), ["complete", "reschedule"])
        self.assertEqual(priority_actions(task, SimpleNamespace(role="paralegal", id="user-b")), [])
        case = {"source": "case_without_action", "responsible_user_id": "user-a"}
        self.assertEqual(priority_actions(case, SimpleNamespace(role="lawyer", id="user-a")), ["create_next_action"])
        self.assertEqual(priority_actions(case, SimpleNamespace(role="lawyer", id="user-b")), [])

    def test_task_retries_only_match_the_same_persisted_values(self):
        task = SimpleNamespace(title="Protocolar", status="completed", due_at=None)
        self.assertTrue(task_values_match(task, {"status": "completed"}))
        self.assertFalse(task_values_match(task, {"title": "Outra tarefa"}))

    def test_daily_queue_is_bounded_and_ordered_in_one_sql_statement(self):
        class EmptyResult:
            def mappings(self):
                return self

            def all(self):
                return []

        class CaptureDb:
            statement = None

            async def execute(self, statement):
                self.statement = statement
                return EmptyResult()

        db = CaptureDb()
        now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        items = asyncio.run(
            daily_priority_items(
                db,
                SimpleNamespace(role="lawyer", id="user-a", tenant_id="tenant-a"),
                now=now,
                tomorrow_start=datetime(2026, 8, 29, 3, 0, tzinfo=timezone.utc),
            )
        )
        sql = str(db.statement.compile(dialect=postgresql.dialect()))
        self.assertEqual(items, [])
        self.assertIn("UNION ALL", sql)
        self.assertIn("ORDER BY daily_priority_queue.priority_rank ASC", sql)
        self.assertIn("LIMIT", sql)

    def test_open_task_filter_keeps_only_actionable_statuses(self):
        sql = str(WorkspaceTask.status.in_(("pending", "in_progress")).compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("'pending'", sql)
        self.assertIn("'in_progress'", sql)
        self.assertNotIn("'completed'", sql)


if __name__ == "__main__":
    unittest.main()
