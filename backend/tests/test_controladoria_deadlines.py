import asyncio
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.services import controladoria_service as service
from app.services.controladoria_deadline_engine import (
    CalendarExceptionSpec,
    DeadlineRuleSpec,
    calculate_deadline,
)
from app.services.controladoria_provider import JudicialProviderError, ProviderFetchPage
from app.services.controladoria_tasks import _fetch_with_backoff


def rule(**changes):
    values = {
        "id": "rule-a",
        "rule_key": "cpc.contestacao",
        "version": 3,
        "rite": "civel_comum",
        "act_type": "intimacao",
        "tribunal": "tjsp",
        "local_code": "capital",
        "days": 2,
        "counting_method": "business_days",
        "start_mode": "next_business_day",
        "due_adjustment": "next_business_day",
        "timezone_name": "America/Sao_Paulo",
        "due_hour": 23,
        "due_minute": 59,
        "legal_sources": [{
            "title": "Codigo de Processo Civil",
            "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
            "reference": "arts. 219 e 224",
        }],
    }
    values.update(changes)
    return DeadlineRuleSpec(**values)


def closure(day, *, kind="holiday", name="Feriado", scope_kind="national", scope_code="BR"):
    return CalendarExceptionSpec(
        scope_kind=scope_kind,
        scope_code=scope_code,
        kind=kind,
        name=name,
        starts_on=day,
        ends_on=day,
        source_url="https://atos.cnj.jus.br/",
        source_name="Ato oficial",
    )


class DeadlineEngineTests(unittest.TestCase):
    def test_provider_retry_uses_bounded_exponential_backoff(self):
        class Provider:
            def __init__(self):
                self.calls = 0

            async def fetch_page(self, **_kwargs):
                self.calls += 1
                if self.calls < 3:
                    raise JudicialProviderError("temporario")
                return ProviderFetchPage(events=[], next_cursor="cursor-ok")

        async def run():
            provider = Provider()
            with patch("app.services.controladoria_tasks.asyncio.sleep", new=AsyncMock()) as sleep:
                page = await _fetch_with_backoff(
                    provider,
                    tribunal="tjsp",
                    process_number="00000000000000000000",
                    cursor=None,
                )
            return provider, page, sleep

        provider, page, sleep = asyncio.run(run())
        self.assertEqual(provider.calls, 3)
        self.assertEqual(page.next_cursor, "cursor-ok")
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [1, 2])

    def test_business_days_exclude_weekend_holiday_and_suspension_in_rule_timezone(self):
        result = calculate_deadline(
            datetime(2026, 9, 4, 18, tzinfo=timezone.utc),
            rule(),
            [
                closure(date(2026, 9, 7), name="Independencia do Brasil"),
                closure(
                    date(2026, 9, 8),
                    kind="suspension",
                    name="Suspensao TJSP",
                    scope_kind="tribunal",
                    scope_code="tjsp",
                ),
            ],
        )
        self.assertEqual(result.explanation["term_start"], "2026-09-09")
        self.assertEqual(result.explanation["due_date"], "2026-09-10")
        self.assertEqual(result.due_at.isoformat(), "2026-09-11T02:59:00+00:00")
        exclusions = {item["date"] for item in result.explanation["excluded_dates"]}
        self.assertEqual(exclusions, {"2026-09-05", "2026-09-06", "2026-09-07", "2026-09-08"})
        self.assertEqual(len(result.explanation["rule"]["snapshot_sha256"]), 64)

    def test_calendar_day_due_date_moves_to_next_business_day_when_configured(self):
        result = calculate_deadline(
            datetime(2026, 9, 3, 12, tzinfo=timezone.utc),
            rule(days=2, counting_method="calendar_days", start_mode="next_calendar_day"),
            [],
        )
        self.assertEqual(result.explanation["unadjusted_due_date"], "2026-09-05")
        self.assertEqual(result.explanation["due_date"], "2026-09-07")

    def test_rule_lookup_is_tenant_scoped_and_missing_rule_fails_closed(self):
        class Database:
            def __init__(self):
                self.statement = None

            async def scalar(self, statement):
                self.statement = statement
                return None

        async def run():
            db = Database()
            user = SimpleNamespace(id="lawyer-a", tenant_id="tenant-a", role="lawyer")
            with self.assertRaises(HTTPException) as caught:
                await service.get_deadline_rule(db, user, "missing")
            return db.statement, caught.exception

        statement, error = asyncio.run(run())
        self.assertEqual(error.status_code, 404)
        compiled = str(statement)
        self.assertIn("controladoria_deadline_rules.tenant_id", compiled)
        self.assertIn("controladoria_deadline_rules.id", compiled)

    def test_same_user_cannot_supply_both_deadline_approvals(self):
        review = SimpleNamespace(
            id="review-a",
            case_id="case-a",
            title="Protocolar manifestacao",
            suggested_due_at=datetime(2026, 9, 10, 18, tzinfo=timezone.utc),
            suggested_basis="Regra revisada.",
            assigned_user_id=None,
            approval_policy_version=2,
            status="first_approved",
            first_approved_by_user_id="lawyer-a",
        )
        case = SimpleNamespace(id="case-a", responsible_user_id="lawyer-a")
        user = SimpleNamespace(id="lawyer-a", tenant_id="tenant-a", role="lawyer")

        async def run():
            with (
                patch.object(service, "get_deadline_review", AsyncMock(return_value=review)),
                patch.object(service, "get_case", AsyncMock(return_value=case)),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await service.approve_deadline_and_create_task(SimpleNamespace(), user, review.id, note="Revisto")
            return caught.exception

        error = asyncio.run(run())
        self.assertEqual(error.status_code, 409)
        self.assertIn("outro usuario", error.detail)

    def test_rule_author_cannot_self_approve_rule(self):
        record = SimpleNamespace(id="rule-a", status="draft", created_by_user_id="partner-a")
        user = SimpleNamespace(id="partner-a", tenant_id="tenant-a", role="partner")

        async def run():
            with patch.object(service, "get_deadline_rule", AsyncMock(return_value=record)):
                with self.assertRaises(HTTPException) as caught:
                    await service.review_deadline_rule(
                        SimpleNamespace(), user, record.id, decision="approved", note="Conferida"
                    )
            return caught.exception

        self.assertEqual(asyncio.run(run()).status_code, 409)

    def test_older_rule_cannot_replace_a_newer_active_version(self):
        draft = SimpleNamespace(
            id="rule-old",
            tenant_id="tenant-a",
            rule_key="cpc.contestacao",
            version=2,
            status="draft",
            created_by_user_id="partner-a",
            reviewed_by_user_id=None,
            reviewed_at=None,
            review_note=None,
        )
        active = SimpleNamespace(version=3)
        user = SimpleNamespace(id="partner-b", tenant_id="tenant-a", role="partner")

        async def run():
            db = SimpleNamespace(scalar=AsyncMock(return_value=active))
            with patch.object(service, "get_deadline_rule", AsyncMock(return_value=draft)):
                with self.assertRaises(HTTPException) as caught:
                    await service.review_deadline_rule(
                        db, user, draft.id, decision="approved", note="Conferida por outro socio."
                    )
            return caught.exception

        error = asyncio.run(run())
        self.assertEqual(error.status_code, 409)
        self.assertIn("versao superior", error.detail)


if __name__ == "__main__":
    unittest.main()
