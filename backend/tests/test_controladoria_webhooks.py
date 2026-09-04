import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1.endpoints import controladoria


def request_with_body(payload) -> Request:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/", "headers": []}, receive)


class EscavadorWebhookTests(unittest.TestCase):
    settings = SimpleNamespace(ESCAVADOR_ENABLED=True, ESCAVADOR_CALLBACK_TOKEN="callback-secret")
    payload = {
        "event": "nova_movimentacao",
        "monitoramento": {"id": 1567024, "numero": "0000000-00.0000.0.00.0000"},
        "movimentacao": {
            "id": 23895909833,
            "data": "2026-09-01",
            "tipo": "ANDAMENTO",
            "conteudo": "Juntada de petição",
            "fonte": {"sigla": "TJSP", "grau_formatado": "Primeiro grau"},
        },
        "uuid": "callback-uuid-a",
    }

    def test_missing_or_wrong_bearer_token_is_rejected(self):
        async def run(token):
            with patch.object(controladoria, "settings", self.settings):
                return await controladoria.escavador_webhook(request_with_body(self.payload), token)

        for token in (None, "Bearer wrong", "Basic callback-secret"):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(run(token))
            self.assertEqual(caught.exception.status_code, 401)

    def test_valid_movement_is_validated_and_queued(self):
        queued = []

        async def run():
            with (
                patch.object(controladoria, "settings", self.settings),
                patch.object(controladoria, "enqueue_escavador_callback", queued.append),
            ):
                return await controladoria.escavador_webhook(
                    request_with_body(self.payload), "Bearer callback-secret"
                )

        result = asyncio.run(run())
        self.assertEqual(result, {"received": True, "queued": True})
        self.assertEqual(queued, [self.payload])

    def test_malformed_movement_is_rejected_before_queue(self):
        async def run():
            malformed = {**self.payload, "movimentacao": {"id": 1}}
            with (
                patch.object(controladoria, "settings", self.settings),
                patch.object(controladoria, "enqueue_escavador_callback") as enqueue,
            ):
                with self.assertRaises(HTTPException) as caught:
                    await controladoria.escavador_webhook(
                        request_with_body(malformed), "Bearer callback-secret"
                    )
            return caught.exception, enqueue

        error, enqueue = asyncio.run(run())
        self.assertEqual(error.status_code, 400)
        enqueue.assert_not_called()

    def test_authenticated_non_movement_event_is_acknowledged_without_queue(self):
        async def run():
            payload = {"event": "processo_verificado"}
            with (
                patch.object(controladoria, "settings", self.settings),
                patch.object(controladoria, "enqueue_escavador_callback") as enqueue,
            ):
                result = await controladoria.escavador_webhook(
                    request_with_body(payload), "Bearer callback-secret"
                )
            return result, enqueue

        result, enqueue = asyncio.run(run())
        self.assertEqual(result["queued"], False)
        enqueue.assert_not_called()

    def test_oversized_callback_is_rejected(self):
        async def run():
            with patch.object(controladoria, "settings", self.settings):
                return await controladoria.escavador_webhook(
                    request_with_body(b"{" + b"x" * controladoria.MAX_ESCAVADOR_CALLBACK_BYTES + b"}"),
                    "Bearer callback-secret",
                )

        with self.assertRaises(HTTPException) as caught:
            asyncio.run(run())
        self.assertEqual(caught.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
