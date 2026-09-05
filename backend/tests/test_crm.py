import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.models.crm import CRMOpportunity
from app.schemas.crm import OpportunityArchive, OpportunityCreate, OpportunityUpdate
from app.api.v1.endpoints.crm import commit_crm_mutation
from app.services.crm import (
    archive_opportunity,
    create_opportunity,
    get_opportunity,
    opportunity_statement,
    opportunity_values_match,
    update_opportunity,
    validate_opportunity_links,
)
from app.services.workspace_service import require_role


class CRMContractsTests(unittest.TestCase):
    user = SimpleNamespace(id="user-a", tenant_id="tenant-a", role="lawyer")

    def test_create_validates_closed_sets_money_timezone_and_next_action(self):
        opportunity = OpportunityCreate(
            request_id="66bc64d5-a827-487f-9d0a-d4d816fa51c1",
            title="  Consultoria contratual  ",
            source="referral",
            estimated_value="1250.50",
            next_action="Enviar proposta",
            next_action_at="2026-09-08T09:00:00-03:00",
        )
        self.assertEqual(opportunity.title, "Consultoria contratual")
        self.assertEqual(opportunity.estimated_value, Decimal("1250.50"))
        self.assertEqual(str(opportunity.next_action_at.tzinfo), "UTC")
        for values in (
            {"stage": "invented"},
            {"source": "social-network"},
            {"estimated_value": "-0.01"},
            {"estimated_value": "1.001"},
            {"next_action_at": "2026-09-08T09:00:00"},
            {"next_action_at": "2026-09-08T09:00:00-03:00"},
            {"invented": True},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                OpportunityCreate(
                    request_id="66bc64d5-a827-487f-9d0a-d4d816fa51c1",
                    title="Oportunidade",
                    **values,
                )

    def test_updates_and_archive_require_revision(self):
        with self.assertRaises(ValidationError):
            OpportunityUpdate(stage="proposal")
        with self.assertRaises(ValidationError):
            OpportunityUpdate(title=None, expected_revision=1)
        self.assertEqual(OpportunityUpdate(stage="proposal", expected_revision=2).expected_revision, 2)
        with self.assertRaises(ValidationError):
            OpportunityArchive(expected_revision=0)

    def test_model_has_tenant_idempotency_and_composite_links(self):
        unique_sets = {
            tuple(constraint.columns.keys())
            for constraint in CRMOpportunity.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        self.assertIn(("tenant_id", "request_id"), unique_sets)
        targets = {
            tuple(element.target_fullname for element in constraint.elements)
            for constraint in CRMOpportunity.__table__.foreign_key_constraints
        }
        self.assertIn(("workspace_clients.tenant_id", "workspace_clients.id"), targets)
        self.assertIn(("workspace_cases.tenant_id", "workspace_cases.id"), targets)
        self.assertIn(("public_intakes.tenant_id", "public_intakes.id"), targets)
        self.assertIn(("users.tenant_id", "users.id"), targets)

    def test_queries_are_tenant_scoped_and_reads_have_explicit_roles(self):
        sql = str(opportunity_statement(self.user).compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("crm_opportunities.tenant_id = 'tenant-a'", sql)
        self.assertIn("crm_opportunities.archived_at IS NULL", sql)
        self.assertIn("workspace_case_access.user_id = 'user-a'", sql)
        require_role(SimpleNamespace(role="paralegal"), {"admin", "partner", "lawyer", "paralegal"})
        with self.assertRaises(HTTPException) as caught:
            require_role(SimpleNamespace(role="paralegal"), {"admin", "partner", "lawyer"})
        self.assertEqual(caught.exception.status_code, 403)

    def test_update_lock_targets_only_the_opportunity_table(self):
        opportunity = SimpleNamespace(id="opportunity-a")
        db = SimpleNamespace(scalar=AsyncMock(return_value=opportunity))
        self.assertIs(asyncio.run(get_opportunity(db, self.user, opportunity.id, for_update=True)), opportunity)
        sql = str(db.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE OF crm_opportunities", sql)

    def test_links_reuse_case_client_and_reject_non_lawyer_owner(self):
        db = SimpleNamespace(scalar=AsyncMock(return_value=None))
        intake = SimpleNamespace(converted_client_id=None, converted_case_id=None)
        case = SimpleNamespace(client_id="client-a")
        with (
            patch("app.services.crm.get_case", AsyncMock(return_value=case)),
            patch("app.services.crm.get_client", AsyncMock()),
            patch("app.services.crm.active_tenant_user", AsyncMock(return_value=SimpleNamespace(role="lawyer"))),
        ):
            links = asyncio.run(validate_opportunity_links(
                db, self.user, client_id=None, case_id="case-a", intake_id=None, owner_user_id="owner-a"
            ))
        self.assertEqual(links["client_id"], "client-a")
        db.scalar.return_value = intake
        with patch("app.services.crm.active_tenant_user", AsyncMock(return_value=SimpleNamespace(role="paralegal"))):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(validate_opportunity_links(
                    db, self.user, client_id=None, case_id=None, intake_id="intake-a", owner_user_id="owner-a"
                ))
        self.assertEqual(caught.exception.status_code, 422)

    def test_optimistic_update_is_idempotent_and_rejects_stale_changes(self):
        opportunity = SimpleNamespace(
            id="opportunity-a", tenant_id="tenant-a", title="Consulta", stage="qualified", source="manual",
            estimated_value=None, next_action=None, next_action_at=None, notes=None, client_id=None,
            case_id=None, intake_id=None, owner_user_id=None, revision=2, archived_at=None,
        )
        db = SimpleNamespace(flush=AsyncMock())
        links = {"client_id": None, "case_id": None, "intake_id": None, "owner_user_id": None}
        with (
            patch("app.services.crm.get_opportunity", AsyncMock(return_value=opportunity)),
            patch("app.services.crm.validate_opportunity_links", AsyncMock(return_value=links)),
        ):
            same, changed = asyncio.run(update_opportunity(
                db, self.user, opportunity.id, OpportunityUpdate(stage="qualified", expected_revision=1)
            ))
            self.assertIs(same, opportunity)
            self.assertFalse(changed)
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(update_opportunity(
                    db, self.user, opportunity.id, OpportunityUpdate(stage="proposal", expected_revision=1)
                ))
        self.assertEqual(caught.exception.status_code, 409)

    def test_create_reuses_only_the_same_idempotent_request(self):
        payload = OpportunityCreate(
            request_id="66bc64d5-a827-487f-9d0a-d4d816fa51c1",
            title="Consulta",
        )
        existing = SimpleNamespace(
            title="Consulta", stage="new", source="manual", estimated_value=None, next_action=None,
            next_action_at=None, notes=None, client_id=None, case_id=None, intake_id=None, owner_user_id=None,
        )
        db = SimpleNamespace(scalar=AsyncMock(return_value=existing))
        result, reused = asyncio.run(create_opportunity(db, self.user, payload))
        self.assertIs(result, existing)
        self.assertTrue(reused)
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(create_opportunity(db, self.user, payload.model_copy(update={"title": "Outro assunto"})))
        self.assertEqual(caught.exception.status_code, 409)

    def test_archive_is_soft_delete_and_idempotent(self):
        opportunity = SimpleNamespace(id="opportunity-a", revision=1, archived_at=None)
        db = SimpleNamespace(flush=AsyncMock())
        with patch("app.services.crm.get_opportunity", AsyncMock(return_value=opportunity)):
            archived, changed = asyncio.run(archive_opportunity(db, self.user, opportunity.id, 1))
            self.assertTrue(changed)
            self.assertIsNotNone(archived.archived_at)
            self.assertEqual(archived.revision, 2)
            _, changed_again = asyncio.run(archive_opportunity(db, self.user, opportunity.id, 1))
            self.assertFalse(changed_again)

    def test_value_comparison_is_used_for_idempotent_retries(self):
        opportunity = SimpleNamespace(stage="new", estimated_value=Decimal("10.00"))
        self.assertTrue(opportunity_values_match(opportunity, {"stage": "new", "estimated_value": Decimal("10.00")}))
        self.assertFalse(opportunity_values_match(opportunity, {"stage": "lost"}))

    def test_mutation_writes_audit_before_commit(self):
        db = SimpleNamespace(commit=AsyncMock())
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"user-agent": "crm-test"})
        with patch("app.api.v1.endpoints.crm.AuditService.log_action", AsyncMock()) as log_action:
            asyncio.run(commit_crm_mutation(db, request, self.user, "CRM_OPPORTUNITY_UPDATED", "opportunity-a"))
        log_action.assert_awaited_once()
        db.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
