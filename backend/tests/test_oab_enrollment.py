import asyncio
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints.oab import require_oab_role, router
from app.models.oab import OABEnrollment, OABEnrollmentChecklistItem
from app.schemas.oab import OABChecklistItemCreate, OABEnrollmentCreate, OABEnrollmentUpdate
from app.services.oab_service import (
    DIRECTORY_URL,
    PROVISION_URL,
    SOURCE_CHECKED_AT,
    OABNotFoundError,
    OABRevisionConflictError,
    OABService,
    list_sources,
)


class CapturingDatabase:
    def __init__(self):
        self.statement = None
        self.added = []

    async def scalar(self, statement):
        self.statement = statement
        return None

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for index, value in enumerate(self.added, start=1):
            value.id = value.id or f"created-{index}"

    @asynccontextmanager
    async def begin_nested(self):
        yield self


REQUEST_ID = "32765845-3321-4ddd-9d66-68bf815a15b6"


class OABEnrollmentTests(unittest.TestCase):
    def test_sources_cover_every_uf_and_only_generate_official_links(self):
        sources = list_sources()
        self.assertEqual(len(sources), 27)
        self.assertEqual({item["uf"] for item in sources}, {
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
            "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        })
        for item in sources:
            self.assertEqual(item["official_url"], f"https://www.oab.org.br/seccional/{item['uf'].lower()}")
            self.assertEqual(item["directory_url"], DIRECTORY_URL)
            self.assertEqual(item["provision_url"], PROVISION_URL)
            self.assertEqual(item["source_checked_at"], SOURCE_CHECKED_AT)
            self.assertIn("confirme", item["notice"].lower())
        self.assertEqual([item["uf"] for item in list_sources("sao paulo")], ["SP"])

    def test_inputs_reject_unknown_values_sensitive_identity_and_money(self):
        with self.assertRaises(ValidationError):
            OABEnrollmentCreate(request_id=REQUEST_ID, uf="XX", enrollment_type="principal")
        with self.assertRaises(ValidationError):
            OABEnrollmentCreate(request_id=REQUEST_ID, uf="SP", enrollment_type="principal", status="approved")
        for field in ("cpf", "rg", "fee", "amount", "payment_hash"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                OABEnrollmentCreate(request_id=REQUEST_ID, uf="SP", enrollment_type="principal", **{field: "invented"})

        active_columns = set(OABEnrollment.__table__.columns.keys()) | set(OABEnrollmentChecklistItem.__table__.columns.keys())
        self.assertTrue({"uf", "enrollment_type", "status", "protocol", "source_url", "source_checked_at", "revision"} <= active_columns)
        self.assertFalse(active_columns & {"cpf", "rg", "fee", "amount", "payment_hash", "file_url", "signature_hash"})
        unique_sets = {
            tuple(constraint.columns.keys()) for table in (OABEnrollment.__table__, OABEnrollmentChecklistItem.__table__)
            for constraint in table.constraints if constraint.__class__.__name__ == "UniqueConstraint"
        }
        self.assertIn(("tenant_id", "user_id", "request_id"), unique_sets)
        self.assertIn(("tenant_id", "user_id", "enrollment_id", "request_id"), unique_sets)

    def test_enrollment_lookup_is_tenant_and_owner_scoped(self):
        db = CapturingDatabase()
        with self.assertRaises(OABNotFoundError):
            asyncio.run(OABService.get_enrollment(db, "tenant-a", "user-a", "foreign-record"))
        query = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("oab_enrollments.tenant_id = 'tenant-a'", query)
        self.assertIn("oab_enrollments.user_id = 'user-a'", query)
        self.assertIn("oab_enrollments.id = 'foreign-record'", query)

    def test_checklist_lookup_is_tenant_owner_and_parent_scoped(self):
        db = CapturingDatabase()
        with self.assertRaises(OABNotFoundError):
            asyncio.run(OABService.get_checklist_item(db, "tenant-a", "user-a", "enrollment-a", "item-b"))
        query = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("oab_enrollment_checklist_items.tenant_id = 'tenant-a'", query)
        self.assertIn("oab_enrollment_checklist_items.user_id = 'user-a'", query)
        self.assertIn("oab_enrollment_checklist_items.enrollment_id = 'enrollment-a'", query)
        self.assertIn("oab_enrollment_checklist_items.id = 'item-b'", query)

    def test_creation_persists_source_snapshot_without_invented_checklist(self):
        db = CapturingDatabase()
        enrollment, reused = asyncio.run(OABService.create_enrollment(
            db,
            "tenant-a",
            "user-a",
            OABEnrollmentCreate(request_id=REQUEST_ID, uf="sp", enrollment_type="principal"),
        ))
        self.assertFalse(reused)
        self.assertEqual(enrollment.tenant_id, "tenant-a")
        self.assertEqual(enrollment.user_id, "user-a")
        self.assertEqual(enrollment.uf, "SP")
        self.assertEqual(enrollment.source_url, "https://www.oab.org.br/seccional/sp")
        self.assertEqual(enrollment.source_checked_at, SOURCE_CHECKED_AT)
        self.assertEqual(len(db.added), 1)
        self.assertIs(db.added[0], enrollment)

    def test_checklist_content_is_user_supplied(self):
        payload = OABChecklistItemCreate(request_id=REQUEST_ID, title="  Item conferido por mim  ", notes="  Consultei a Seccional  ")
        self.assertEqual(payload.title, "Item conferido por mim")
        self.assertEqual(payload.notes, "Consultei a Seccional")
        with self.assertRaises(ValidationError):
            OABChecklistItemCreate(request_id=REQUEST_ID, title="   ")

    def test_update_requires_the_current_revision(self):
        enrollment = OABEnrollment(
            id="enrollment-a",
            request_id=REQUEST_ID,
            tenant_id="tenant-a",
            user_id="user-a",
            uf="SP",
            enrollment_type="principal",
            status="planning",
            source_url="https://www.oab.org.br/seccional/sp",
            source_version="source-v1",
            source_checked_at=SOURCE_CHECKED_AT,
            revision=2,
        )

        class ExistingDatabase(CapturingDatabase):
            async def scalar(self, statement):
                self.statement = statement
                return enrollment

        with self.assertRaises(OABRevisionConflictError):
            asyncio.run(OABService.update_enrollment(
                ExistingDatabase(),
                "tenant-a",
                "user-a",
                "enrollment-a",
                OABEnrollmentUpdate(expected_revision=1, status="gathering"),
            ))

    def test_simulated_endpoints_are_removed(self):
        paths = {route.path for route in router.routes}
        self.assertIn("/sources", paths)
        self.assertIn("/enrollments", paths)
        self.assertNotIn("/simulate-fees", paths)
        self.assertNotIn("/generate-declaration", paths)

    def test_oab_api_rejects_non_lawyer_roles(self):
        require_oab_role(SimpleNamespace(role="lawyer"))
        with self.assertRaises(HTTPException) as caught:
            require_oab_role(SimpleNamespace(role="paralegal"))
        self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
