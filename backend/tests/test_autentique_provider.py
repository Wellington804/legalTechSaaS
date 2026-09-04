import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace

from app.core.security import encrypt_mfa_secret
from app.services.autentique_provider import (
    AutentiqueSigner,
    parse_autentique_webhook,
    submit_autentique_document,
)
from app.services.operations import verify_hmac_webhook
from app.models.operations import SignatureEnvelope
from app.services.operations import queue_autentique_event


class FakeAutentiqueClient:
    def __init__(self):
        self.calls = []

    async def graphql(self, query, variables, *, file=None):
        self.calls.append((query, variables, file))
        return {"createDocument": {"id": "doc-aut-1", "signatures": [{"public_id": "signer-1"}]}}


class Nested:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class FakeQueueDB:
    def __init__(self, rows):
        self.rows = list(rows)
        self.added = []

    async def scalar(self, _query):
        return self.rows.pop(0)

    def begin_nested(self):
        return Nested()

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        return None


class AutentiqueProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_qualified_document_without_certificate_custody(self):
        client = FakeAutentiqueClient()
        pdf = b"%PDF-1.7\nimmutable"
        result = await submit_autentique_document(
            access_token="tenant-token",
            account_reference="123",
            local_envelope_id="local-1",
            filename="peca.pdf",
            pdf=pdf,
            pdf_sha256=hashlib.sha256(pdf).hexdigest(),
            signer=AutentiqueSigner(
                name="Maria Silva", email="maria@example.com", cpf="12345678901", authentication="icp_brasil"
            ),
            expires_at=None,
            client=client,
        )
        self.assertEqual(result.document_id, "doc-aut-1")
        _, variables, uploaded = client.calls[0]
        self.assertEqual(variables["organization_id"], 123)
        self.assertTrue(variables["document"]["qualified"])
        self.assertEqual(uploaded, ("peca.pdf", pdf))
        serialized = json.dumps(variables).casefold()
        self.assertNotIn("pfx", serialized)
        self.assertNotIn("pin", serialized)
        self.assertNotIn("private_key", serialized)

    def test_webhook_identity_mapping_and_official_hmac_header_contract(self):
        raw = json.dumps(
            {
                "event": {
                    "id": "event-1",
                    "type": "document.finished",
                    "organization": 123,
                    "data": {"object": {"id": "doc-aut-1", "files": {"signed": "https://storage.googleapis.com/file"}}},
                }
            }, separators=(",", ":")
        ).encode()
        event = parse_autentique_webhook(raw)
        self.assertEqual(event.account_reference, "123")
        self.assertEqual(event.provider_document_id, "doc-aut-1")
        self.assertEqual(event.event_type, "envelope.signed")
        secret = "0123456789abcdef0123456789abcdef"
        signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        self.assertTrue(verify_hmac_webhook(raw, signature, encrypt_mfa_secret(secret)))
        self.assertFalse(verify_hmac_webhook(raw + b" ", signature, encrypt_mfa_secret(secret)))

    def test_official_flat_signature_rejection_payload_is_supported_strictly(self):
        raw = json.dumps(
            {
                "event": {
                    "id": "event-rejected-1",
                    "type": "signature.rejected",
                    "organization": {"id": 123},
                    "data": {"object": "signature", "id": "signature-1", "document": "doc-aut-1"},
                }
            },
            separators=(",", ":"),
        ).encode()
        event = parse_autentique_webhook(raw)
        self.assertEqual(event.provider_document_id, "doc-aut-1")
        self.assertEqual(event.event_type, "envelope.declined")

        invalid = json.dumps(
            {
                "event": {
                    "id": "event-rejected-2",
                    "type": "signature.rejected",
                    "organization": 123,
                    "data": {"object": {"id": "signature-1", "document": "doc-aut-1"}},
                }
            }
        ).encode()
        with self.assertRaises(ValueError):
            parse_autentique_webhook(invalid)

    async def test_authenticated_event_is_persisted_once_before_async_finalization(self):
        raw = json.dumps({"event": {"id": "event-1", "type": "document.finished", "organization": 123, "data": {"object": {"id": "doc-aut-1"}}}}, separators=(",", ":")).encode()
        event = parse_autentique_webhook(raw)
        identity = SimpleNamespace(tenant_id="tenant-a", credential=SimpleNamespace(provider="autentique", account_reference="123"))
        envelope = SignatureEnvelope(
            id="env-1", tenant_id="tenant-a", document_id="doc-1", document_version=1,
            document_hash="a" * 64, provider="autentique", provider_account_reference="123", status="pending",
        )
        db = FakeQueueDB([envelope, None])
        queued_envelope, event_row, duplicate = await queue_autentique_event(db, identity, event, raw)
        self.assertIs(queued_envelope, envelope)
        self.assertFalse(duplicate)
        self.assertEqual(event_row.event_type, "envelope.signed")
        self.assertEqual(envelope.status, "pending")
        replay_db = FakeQueueDB([envelope, event_row])
        _, replay_event, duplicate = await queue_autentique_event(replay_db, identity, event, raw)
        self.assertTrue(duplicate)
        self.assertIs(replay_event, event_row)


if __name__ == "__main__":
    unittest.main()
