import hashlib
import hmac
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.schemas.operations import FeeRuleCreate, InvoiceCreate, PublicIntakeSubmit
from app.models.operations import PaymentProviderEvent, PaymentReceipt, SignatureProviderEvent
from app.services.operations import (
    FixedHostHttpClient,
    document_version_digest,
    idempotency_digest,
    money,
    provider_reference_digest,
    verify_hmac_webhook,
)


class OperationsContractsTests(unittest.TestCase):
    def test_money_is_decimal_and_invoice_installments_are_exact(self):
        self.assertEqual(money(Decimal("10.005")), Decimal("10.01"))
        invoice = InvoiceCreate(
            fee_contract_id="contract-a",
            description="Honorários fictícios",
            total_amount="100.00",
            installments=[{"due_on": date(2026, 9, 1), "amount": "40.00"}, {"due_on": date(2026, 10, 1), "amount": "60.00"}],
        )
        self.assertEqual(invoice.total_amount, Decimal("100.00"))
        with self.assertRaises(ValidationError):
            InvoiceCreate(
                fee_contract_id="contract-a",
                description="Honorários fictícios",
                total_amount="100.00",
                installments=[{"due_on": date(2026, 9, 1), "amount": "99.99"}],
            )
        with self.assertRaises(ValidationError):
            FeeRuleCreate(rule_type="hourly", percentage="10", description="Hora")

    def test_public_intake_contract_requires_explicit_current_consent(self):
        preferred = datetime.now(timezone.utc) + timedelta(days=1)
        intake = PublicIntakeSubmit(name="Pessoa interessada", consent=True, consent_version="v3", preferred_contact_at=preferred)
        self.assertEqual(intake.name, "Pessoa interessada")
        self.assertEqual(intake.preferred_contact_at, preferred)
        with self.assertRaises(ValidationError):
            PublicIntakeSubmit(name="Pessoa interessada", consent=False, consent_version="v3")
        with self.assertRaises(ValidationError):
            PublicIntakeSubmit(name="Pessoa interessada", consent=True, consent_version="v3", preferred_contact_at=datetime.now())

    def test_idempotency_and_provider_references_are_scoped(self):
        self.assertEqual(idempotency_digest("form-a", "request-a"), idempotency_digest("form-a", "request-a"))
        self.assertNotEqual(idempotency_digest("form-a", "request-a"), idempotency_digest("form-b", "request-a"))
        self.assertNotEqual(provider_reference_digest("provider-a", "account-a", "receipt"), provider_reference_digest("provider-b", "account-a", "receipt"))
        self.assertNotEqual(provider_reference_digest("provider-a", "account-a", "receipt"), provider_reference_digest("provider-a", "account-b", "receipt"))

    def test_provider_uniqueness_is_scoped_to_the_configured_account(self):
        expected = {
            SignatureProviderEvent: ("tenant_id", "provider", "account_reference", "event_id"),
            PaymentProviderEvent: ("tenant_id", "provider", "account_reference", "event_id"),
            PaymentReceipt: ("tenant_id", "provider", "provider_account_reference", "provider_payment_hash"),
        }
        for model, columns in expected.items():
            unique_sets = {tuple(column.name for column in constraint.columns) for constraint in model.__table__.constraints if constraint.__class__.__name__ == "UniqueConstraint"}
            self.assertIn(columns, unique_sets)

    def test_signature_snapshot_is_version_immutable(self):
        snapshot = SimpleNamespace(sha256_hash=None, file_content=None, content_text="versão 1")
        self.assertEqual(document_version_digest(snapshot), hashlib.sha256("versão 1".encode()).hexdigest())
        explicit = SimpleNamespace(sha256_hash="a" * 64, file_content=b"ignored", content_text="ignored")
        self.assertEqual(document_version_digest(explicit), "a" * 64)

    def test_webhook_hmac_and_fixed_host_boundary(self):
        raw = b'{"event_id":"evt-1"}'
        signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
        with patch("app.services.operations.decrypt_mfa_secret", return_value="secret"):
            self.assertTrue(verify_hmac_webhook(raw, signature, "encrypted"))
            self.assertFalse(verify_hmac_webhook(raw, "sha256=bad", "encrypted"))
        client = FixedHostHttpClient("https://provider.example/api/")
        self.assertEqual(client.host, "provider.example")
        with self.assertRaises(ValueError):
            FixedHostHttpClient("http://provider.example")


if __name__ == "__main__":
    unittest.main()
