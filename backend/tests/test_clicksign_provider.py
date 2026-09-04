import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.schemas.operations import SignatureEnvelopeCreate
from app.services.clicksign_provider import (
    ClicksignClient,
    ClicksignDispatchError,
    ClicksignSigner,
    _allowed_download_host,
    _signed_file_url,
    parse_clicksign_webhook,
    submit_clicksign_envelope,
)


class FakeClicksignClient:
    def __init__(self, fail_at: int | None = None):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.fail_at = fail_at

    async def request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        self.calls.append((method, path, payload))
        if self.fail_at == len(self.calls):
            raise ClicksignDispatchError("provider failed", ambiguous=True)
        if path == "/envelopes":
            return {"data": {"id": "env-1"}}
        if path.endswith("/documents"):
            return {"data": {"id": "doc-1"}}
        if path.endswith("/signers"):
            return {"data": {"id": "signer-1"}}
        return {"data": {"id": f"result-{len(self.calls)}"}}


class ClicksignProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_authorization_header_preserves_official_raw_token_and_explicit_scheme(self):
        self.assertEqual(ClicksignClient("clicksign-sandbox", " raw-token ").headers["Authorization"], "raw-token")
        self.assertEqual(ClicksignClient("clicksign", " Bearer explicit-token ").headers["Authorization"], "Bearer explicit-token")

    async def test_submits_official_v3_sequence_with_icp_brasil(self):
        client = FakeClicksignClient()
        pdf = b"%PDF-1.7\nimmutable"
        submission = await submit_clicksign_envelope(
            provider="clicksign-sandbox",
            access_token="secret-token",
            local_envelope_id="local-1",
            filename="peca.pdf",
            pdf=pdf,
            pdf_sha256=hashlib.sha256(pdf).hexdigest(),
            signer=ClicksignSigner(name="Maria Silva", email="maria@example.com", cpf="12345678901", authentication="icp_brasil"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            client=client,
        )
        self.assertEqual((submission.envelope_id, submission.document_id), ("env-1", "doc-1"))
        self.assertEqual(
            [(method, path) for method, path, _ in client.calls],
            [
                ("POST", "/envelopes"),
                ("POST", "/envelopes/env-1/documents"),
                ("POST", "/envelopes/env-1/signers"),
                ("POST", "/envelopes/env-1/requirements"),
                ("POST", "/envelopes/env-1/requirements"),
                ("PATCH", "/envelopes/env-1"),
                ("POST", "/envelopes/env-1/notifications"),
            ],
        )
        document_attributes = client.calls[1][2]["data"]["attributes"]
        self.assertEqual(document_attributes["metadata"]["lexflow_envelope_id"], "local-1")
        auth_attributes = client.calls[4][2]["data"]["attributes"]
        self.assertEqual(auth_attributes, {"action": "provide_evidence", "auth": "icp_brasil"})
        serialized = json.dumps([payload for _, _, payload in client.calls])
        self.assertNotIn("pfx", serialized.casefold())
        self.assertNotIn("pin", serialized.casefold())

    async def test_partial_failure_preserves_provider_ids_and_is_not_retry_safe(self):
        client = FakeClicksignClient(fail_at=4)
        pdf = b"%PDF-1.7\nimmutable"
        with self.assertRaises(ClicksignDispatchError) as raised:
            await submit_clicksign_envelope(
                provider="clicksign-sandbox",
                access_token="secret-token",
                local_envelope_id="local-1",
                filename="peca.pdf",
                pdf=pdf,
                pdf_sha256=hashlib.sha256(pdf).hexdigest(),
                signer=ClicksignSigner(name="Maria Silva", email="maria@example.com", cpf=None, authentication="email"),
                expires_at=None,
                client=client,
            )
        self.assertTrue(raised.exception.ambiguous)
        self.assertEqual(raised.exception.envelope_id, "env-1")
        self.assertEqual(raised.exception.document_id, "doc-1")

    def test_parses_document_closed_identity_and_metadata(self):
        raw = json.dumps(
            {
                "event": {
                    "name": "document_closed",
                    "data": {"account": {"key": "account-1"}},
                    "occurred_at": "2026-09-04T12:00:00-03:00",
                },
                "document": {
                    "key": "doc-1",
                    "metadata": {"lexflow_envelope_id": "local-1"},
                },
            }
        ).encode()
        event = parse_clicksign_webhook(raw, "document_closed")
        self.assertEqual(event.account_reference, "account-1")
        self.assertEqual(event.local_envelope_id, "local-1")
        self.assertEqual(event.provider_document_id, "doc-1")
        self.assertEqual(event.event_type, "envelope.signed")
        self.assertEqual(event.event_id, parse_clicksign_webhook(raw, "document_closed").event_id)
        with self.assertRaises(ValueError):
            parse_clicksign_webhook(raw, "document_canceled")

    def test_signed_download_is_extracted_but_restricted_to_clicksign_hosts(self):
        url = "https://clicksign-sandbox-content.s3.amazonaws.com/file.pdf?signature=1"
        self.assertEqual(_signed_file_url({"data": {"links": {"files": {"signed": url}}}}), url)
        self.assertTrue(_allowed_download_host("clicksign-sandbox-content.s3.amazonaws.com", "clicksign-sandbox"))
        self.assertTrue(_allowed_download_host("tavola-staging.s3.amazonaws.com", "clicksign-sandbox"))
        self.assertFalse(_allowed_download_host("attacker.example", "clicksign-sandbox"))
        self.assertFalse(_allowed_download_host("not-clicksign-content.s3.amazonaws.com", "clicksign-sandbox"))
        self.assertFalse(_allowed_download_host("clicksign-content.attacker.s3.amazonaws.com", "clicksign-sandbox"))

    def test_icp_request_requires_cpf_and_two_part_name(self):
        base = {
            "request_key": "12345678-1234-1234-1234-123456789012",
            "document_id": "document-1",
            "document_version": 1,
            "provider": "clicksign-sandbox",
            "account_reference": "account-1",
            "signer_name": "Maria Silva",
            "signer_email": "maria@example.com",
            "authentication": "icp_brasil",
        }
        with self.assertRaises(ValidationError):
            SignatureEnvelopeCreate(**base)
        request = SignatureEnvelopeCreate(**base, signer_cpf="123.456.789-01")
        self.assertEqual(request.signer_cpf, "12345678901")
        with self.assertRaises(ValidationError):
            SignatureEnvelopeCreate(**{**base, "signer_name": "Maria", "signer_cpf": "12345678901"})


if __name__ == "__main__":
    unittest.main()
