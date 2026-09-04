import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.external_integrations import ProviderPriceItem, ProviderPriceVersion
from app.schemas.external_integrations import CostScenario
from app.services.provider_costs import cost_report


class ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, version, items):
        self.version = version
        self.items = items

    async def scalar(self, _query):
        return self.version

    async def scalars(self, _query):
        return ScalarRows(self.items)


class ProviderCostTests(unittest.IsolatedAsyncioTestCase):
    async def test_commitment_floor_uses_configured_price_and_provenance(self):
        version = ProviderPriceVersion(
            id="price-1", tenant_id="tenant-a", provider="autentique", version=1, currency="BRL",
            pricing_model="commitment_floor", monthly_base_amount=Decimal("99"),
            effective_on=date(2026, 9, 1), observed_on=date(2026, 9, 4),
            provenance_url="https://docs.autentique.com.br/api/api-pricing.md",
            quote_required=False, created_by_user_id="user-a",
        )
        items = [
            ProviderPriceItem(tenant_id="tenant-a", price_version_id="price-1", metric="document_created", unit_price=Decimal("0.06"), included_units=0),
            ProviderPriceItem(tenant_id="tenant-a", price_version_id="price-1", metric="webhook_received", unit_price=Decimal("0.0002"), included_units=0),
        ]
        report = await cost_report(
            FakeDB(version, items),
            SimpleNamespace(tenant_id="tenant-a"),
            CostScenario(provider="autentique", price_version_id="price-1", volumes={"document_created": 100, "webhook_received": 100}),
        )
        self.assertEqual(report.usage_amount, Decimal("6.020000"))
        self.assertEqual(report.total_amount, Decimal("99.000000"))
        self.assertEqual(report.provenance_url, version.provenance_url)

    async def test_base_plus_usage_adds_only_billable_units(self):
        version = ProviderPriceVersion(
            id="price-2", tenant_id="tenant-a", provider="quoted-provider", version=1, currency="BRL",
            pricing_model="base_plus_usage", monthly_base_amount=Decimal("10"),
            effective_on=date(2026, 9, 1), observed_on=date(2026, 9, 4),
            provenance_url="https://example.com/official-price", quote_required=True, created_by_user_id="user-a",
        )
        item = ProviderPriceItem(
            tenant_id="tenant-a", price_version_id="price-2", metric="document_created",
            unit_price=Decimal("2"), included_units=5,
        )
        report = await cost_report(
            FakeDB(version, [item]), SimpleNamespace(tenant_id="tenant-a"),
            CostScenario(provider="quoted-provider", price_version_id="price-2", volumes={"document_created": 8}),
        )
        self.assertEqual(report.total_amount, Decimal("16.000000"))
        self.assertTrue(report.quote_required)


if __name__ == "__main__":
    unittest.main()
