import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.security import decrypt_mfa_secret
from app.models.operations import SignatureEnvelope
from app.services.operations import _store_signed_artifact
from app.services.pades_validation import PadesSignature, PadesValidationResult, validate_pades_pdf


def _run_with_output(output: str, returncode: int = 0):
    def run(*_args, **kwargs):
        kwargs["stdout"].write(output.encode())
        kwargs["stdout"].flush()
        return SimpleNamespace(returncode=returncode)

    return run


class NoReadDB:
    async def scalar(self, _statement):
        raise AssertionError("invalid signed PDF must not be stored")


class DocumentDB:
    async def scalar(self, _statement):
        return SimpleNamespace(title="Petição inicial")


class PadesValidationTests(unittest.IsolatedAsyncioTestCase):
    def test_valid_signature_requires_valid_cms_and_full_file_coverage(self):
        output = """Digital Signature Info of: signed.pdf
Signature #1:
  - Signer Certificate Common Name: Maria da Silva
  - Signer full Distinguished Name: CN=Maria da Silva,serialNumber=CPF:12345678901
  - Signing Time: Sep 04 2026 12:00:00
  - Signature Type: ETSI.CAdES.detached
  - Total document signed
  - Signature Validation: Signature is Valid.
  - Certificate Validation: Certificate issuer isn't Trusted.
"""
        with patch("app.services.pades_validation.subprocess.run", side_effect=_run_with_output(output)):
            result = validate_pades_pdf(b"%PDF-1.7\nbody")
        self.assertEqual(result.status, "valid_integrity")
        self.assertEqual(result.certificate_trust, "unverified")
        self.assertEqual(result.signatures[0].signer_common_name, "Maria da Silva")
        self.assertTrue(result.signatures[0].covers_entire_file)

    def test_unsigned_increment_and_unsigned_pdf_fail_closed(self):
        partial = """Signature #1:
  - Not total document signed
  - Signature Validation: Signature is Valid.
  - Certificate Validation: Certificate is Trusted.
"""
        with patch("app.services.pades_validation.subprocess.run", side_effect=_run_with_output(partial)):
            result = validate_pades_pdf(b"%PDF-1.7\nbody")
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.reason, "unsigned_increment")

        with patch("app.services.pades_validation.subprocess.run", side_effect=_run_with_output("File has no signatures")):
            unsigned = validate_pades_pdf(b"%PDF-1.7\nbody")
        self.assertEqual(unsigned.status, "invalid")
        self.assertEqual(unsigned.reason, "no_signature")

    async def test_invalid_validation_is_persisted_but_artifact_is_not_promoted(self):
        envelope = SignatureEnvelope(
            id="env-1",
            tenant_id="tenant-a",
            document_id="doc-1",
            document_version=1,
            document_hash="a" * 64,
            provider="autentique",
            provider_account_reference="123",
            signature_authentication="icp_brasil",
        )
        result = PadesValidationResult("invalid", "invalid", (), "no_signature")
        with patch("app.services.operations.validate_pades_pdf", return_value=result):
            stored = await _store_signed_artifact(NoReadDB(), envelope, b"%PDF-1.7\nunsigned")
        self.assertFalse(stored)
        self.assertIsNone(envelope.signed_file_hash)
        self.assertEqual(envelope.signed_validation_status, "invalid")
        report = json.loads(decrypt_mfa_secret(envelope.signed_validation_report_encrypted))
        self.assertEqual(report["reason"], "no_signature")

    async def test_only_integrity_valid_pdf_is_promoted_with_immutable_hash(self):
        envelope = SignatureEnvelope(
            id="env-2",
            tenant_id="tenant-a",
            document_id="doc-1",
            document_version=1,
            document_hash="a" * 64,
            provider="autentique",
            provider_account_reference="123",
            signature_authentication="icp_brasil",
        )
        signature = PadesSignature(1, "Maria da Silva", "CN=Maria", None, "ETSI.CAdES.detached", "Signature is Valid.", "Certificate issuer isn't Trusted.", True)
        result = PadesValidationResult("valid_integrity", "unverified", (signature,), "integrity_valid_trust_unverified")
        pdf = b"%PDF-1.7\nsigned"
        with patch("app.services.operations.validate_pades_pdf", return_value=result), patch(
            "app.services.operations.scan_document_content"
        ), patch("app.services.operations.document_storage_enabled", return_value=False):
            stored = await _store_signed_artifact(DocumentDB(), envelope, pdf)
        self.assertTrue(stored)
        self.assertEqual(envelope.signed_file_content, pdf)
        self.assertEqual(envelope.signed_signature_count, 1)
        self.assertEqual(envelope.signed_certificate_trust, "unverified")
        self.assertEqual(len(envelope.signed_file_hash), 64)


if __name__ == "__main__":
    unittest.main()
