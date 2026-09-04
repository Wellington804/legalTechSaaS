import hashlib
import hmac
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints.operations import download_signed_envelope
from app.core.security import encrypt_mfa_secret
from app.models.operations import PaymentProviderEvent, PaymentReceipt, SignatureEnvelope, SignatureProviderEvent
from app.schemas.operations import FeeRuleCreate, InvoiceCreate, PublicIntakeSubmit
from app.services.clicksign_provider import ClicksignWebhook
from app.services.operations import (
    FixedHostHttpClient,
    apply_clicksign_event,
    document_version_digest,
    finalize_queued_clicksign_event,
    idempotency_digest,
    money,
    provider_reference_digest,
    verify_hmac_webhook,
)


class ScalarDB:
    def __init__(self, values):
        self.values = list(values)

    async def scalar(self, _statement):
        return self.values.pop(0)


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
        envelope_unique_sets = {
            tuple(column.name for column in constraint.columns)
            for constraint in SignatureEnvelope.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        self.assertIn(("tenant_id", "request_hash"), envelope_unique_sets)
        self.assertIn(("tenant_id", "provider", "provider_account_reference", "provider_document_hash"), envelope_unique_sets)

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
            self.assertTrue(verify_hmac_webhook(raw, signature.replace("sha256=", "SHA256="), "encrypted"))
            self.assertFalse(verify_hmac_webhook(raw, "sha256=bad", "encrypted"))
            self.assertFalse(verify_hmac_webhook(raw, signature.replace("sha256=", "sha384="), "encrypted"))
        client = FixedHostHttpClient("https://provider.example/api/")
        self.assertEqual(client.host, "provider.example")
        with self.assertRaises(ValueError):
            FixedHostHttpClient("http://provider.example")


class SignatureLegacyRevalidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_download_rejects_legacy_artifact_without_fresh_integrity_validation(self):
        envelope = SignatureEnvelope(
            id="env-legacy",
            tenant_id="tenant-a",
            document_id="doc-1",
            document_version=1,
            document_hash="a" * 64,
            provider="autentique",
            provider_account_reference="account-a",
            signed_file_hash="b" * 64,
            signed_file_content=b"%PDF-1.7\nlegacy",
            signed_validation_status="unavailable",
        )
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a", role="lawyer")
        with patch(
            "app.api.v1.endpoints.operations.get_signature_envelope",
            AsyncMock(return_value=envelope),
        ):
            with self.assertRaises(HTTPException) as blocked:
                await download_signed_envelope("env-legacy", SimpleNamespace(), user, SimpleNamespace())
        self.assertEqual(blocked.exception.status_code, 409)

    async def test_duplicate_clicksign_webhook_revalidates_legacy_artifact(self):
        pdf = b"%PDF-1.7\nsigned"
        envelope = SignatureEnvelope(
            id="env-1",
            tenant_id="tenant-a",
            document_id="doc-1",
            document_version=1,
            document_hash="a" * 64,
            provider="clicksign-sandbox",
            provider_account_reference="account-a",
            provider_document_hash=provider_reference_digest("clicksign-sandbox", "account-a", "doc-provider"),
            provider_envelope_id_encrypted=encrypt_mfa_secret("envelope-provider"),
            provider_document_id_encrypted=encrypt_mfa_secret("doc-provider"),
            signed_file_hash=hashlib.sha256(pdf).hexdigest(),
            signed_file_content=pdf,
            signed_validation_status="unavailable",
            status="signed",
        )
        identity = SimpleNamespace(
            tenant_id="tenant-a",
            credential=SimpleNamespace(
                provider="clicksign-sandbox",
                account_reference="account-a",
                api_token_encrypted=encrypt_mfa_secret("provider-token"),
            ),
        )
        event = ClicksignWebhook(
            "account-a",
            "event-1",
            "document_closed",
            "envelope.signed",
            "env-1",
            "doc-provider",
        )

        async def validate(_db, target, content):
            self.assertEqual(content, pdf)
            target.signed_validation_status = "valid_integrity"
            return True

        fetch = AsyncMock(return_value=pdf)
        with patch("app.services.operations.fetch_clicksign_signed_pdf", fetch), patch(
            "app.services.operations._store_signed_artifact", side_effect=validate
        ), patch("app.services.operations._set_tenant_context", AsyncMock()):
            result, duplicate = await apply_clicksign_event(
                ScalarDB([envelope, "persisted-event", envelope]), identity, event, b"payload"
            )
        self.assertTrue(duplicate)
        self.assertIs(result, envelope)
        self.assertEqual(envelope.signed_validation_status, "valid_integrity")
        fetch.assert_awaited_once()

    async def test_periodic_clicksign_finalizer_downloads_and_revalidates_without_new_webhook(self):
        pdf = b"%PDF-1.7\nsigned"
        event_row = SignatureProviderEvent(
            id="event-row-1",
            tenant_id="tenant-a",
            envelope_id="env-1",
            provider="clicksign",
            account_reference="account-a",
            event_id="provider-event-1",
            event_digest="c" * 64,
            event_type="envelope.signed",
        )
        envelope = SignatureEnvelope(
            id="env-1",
            tenant_id="tenant-a",
            document_id="doc-1",
            document_version=1,
            document_hash="a" * 64,
            provider="clicksign",
            provider_account_reference="account-a",
            provider_envelope_id_encrypted=encrypt_mfa_secret("provider-envelope"),
            provider_document_id_encrypted=encrypt_mfa_secret("provider-document"),
            signed_file_hash=hashlib.sha256(pdf).hexdigest(),
            signed_validation_status="unavailable",
            status="signed",
            revision=4,
        )
        credential = SimpleNamespace(
            api_token_encrypted=encrypt_mfa_secret("provider-token"),
            account_reference="account-a",
        )

        async def validate(_db, target, content):
            self.assertEqual(content, pdf)
            target.signed_validation_status = "valid_integrity"
            return True

        fetch = AsyncMock(return_value=pdf)
        with patch("app.services.operations.fetch_clicksign_signed_pdf", fetch), patch(
            "app.services.operations._store_signed_artifact", side_effect=validate
        ), patch("app.services.operations._set_tenant_context", AsyncMock()):
            result = await finalize_queued_clicksign_event(
                ScalarDB([event_row, envelope, credential, envelope]),
                tenant_id="tenant-a",
                event_id=event_row.id,
            )

        self.assertEqual(result, "finalized")
        self.assertEqual(envelope.signed_validation_status, "valid_integrity")
        self.assertEqual(envelope.revision, 5)
        fetch.assert_awaited_once_with(
            provider="clicksign",
            access_token="provider-token",
            envelope_id="provider-envelope",
            document_id="provider-document",
        )


if __name__ == "__main__":
    unittest.main()
