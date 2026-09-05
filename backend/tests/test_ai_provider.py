import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import ai_provider


class AIProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_openrouter_returns_only_bounded_message_content(self):
        configured = SimpleNamespace(AI_ENABLED=True, AI_PROVIDER="openrouter", OPENROUTER_API_KEY="secret",
                                     OPENROUTER_MODEL="openai/gpt-test", OPENROUTER_APP_NAME="LexFlow",
                                     FRONTEND_URL="https://lexflow.example", GEMINI_API_KEY=None, GEMINI_MODEL="")
        with patch.object(ai_provider, "settings", configured), patch.object(ai_provider, "_bounded_json", AsyncMock(
            return_value={"choices": [{"message": {"content": "Rascunho para revisão"}}]})) as request:
            text = await ai_provider.generate_text(system_prompt="Regras", user_prompt="Pedido")
        self.assertEqual(text, "Rascunho para revisão")
        self.assertEqual(request.await_args.args[0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertNotIn("secret", str(request.await_args.kwargs["payload"]))
        self.assertEqual(request.await_args.kwargs["payload"]["reasoning"], {"effort": "low"})
        self.assertEqual(request.await_args.kwargs["payload"]["provider"], {
            "zdr": True, "data_collection": "deny", "allow_fallbacks": True,
        })

    async def test_deep_and_legal_routes_reuse_main_key_without_changing_model_slug(self):
        configured = SimpleNamespace(
            AI_ENABLED=True, AI_PROVIDER="openrouter", OPENROUTER_API_KEY="secret",
            OPENROUTER_MODEL="openai/gpt-5.6-luna", OPENROUTER_GENERAL_MODEL="openai/gpt-5.6-luna",
            OPENROUTER_DEEP_MODEL="openai/gpt-5.6-luna", OPENROUTER_DEEP_REASONING="max",
            OPENROUTER_LEGAL_MODEL="openai/gpt-5.6-luna-pro", OPENROUTER_APP_NAME="LexFlow",
            FRONTEND_URL="https://lexflow.example", GEMINI_API_KEY=None, GEMINI_MODEL="",
        )
        with patch.object(ai_provider, "_bounded_json", AsyncMock(
            return_value={"choices": [{"message": {"content": "ok"}}]})) as request:
            await ai_provider.generate_text(system_prompt="Regras", user_prompt="Pedido", purpose="deep", config=configured)
            self.assertEqual(request.await_args.kwargs["payload"]["model"], "openai/gpt-5.6-luna")
            self.assertEqual(request.await_args.kwargs["payload"]["reasoning"], {"effort": "max"})
            await ai_provider.generate_text(system_prompt="Regras", user_prompt="Pedido", purpose="legal", config=configured)
            self.assertEqual(request.await_args.kwargs["payload"]["model"], "openai/gpt-5.6-luna-pro")
            self.assertNotIn("reasoning", request.await_args.kwargs["payload"])

    async def test_visual_route_keeps_zdr_without_unsupported_temperature(self):
        configured = SimpleNamespace(
            AI_ENABLED=True, AI_PROVIDER="openrouter", OPENROUTER_API_KEY="main-secret",
            OPENROUTER_MODEL="openai/gpt-5.6-luna", OPENROUTER_VISUAL_API_KEY="visual-secret",
            OPENROUTER_VISUAL_MODEL="google/gemini-3.8-flash", OPENROUTER_APP_NAME="LexFlow",
            FRONTEND_URL="https://lexflow.example", GEMINI_API_KEY=None, GEMINI_MODEL="",
        )
        with patch.object(ai_provider, "_bounded_json", AsyncMock(
            return_value={"choices": [{"message": {"content": "ok"}}]})) as request:
            await ai_provider.generate_text(
                system_prompt="Regras", user_prompt="Pedido", purpose="visual", config=configured,
            )
        payload = request.await_args.kwargs["payload"]
        self.assertEqual(payload["model"], "google/gemini-3.8-flash")
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["provider"]["zdr"], True)

    async def test_provider_must_be_explicitly_configured(self):
        configured = SimpleNamespace(AI_ENABLED=True, AI_PROVIDER="openrouter", OPENROUTER_API_KEY=None,
                                     OPENROUTER_MODEL="", OPENROUTER_APP_NAME="LexFlow", FRONTEND_URL="https://lexflow.example",
                                     GEMINI_API_KEY=None, GEMINI_MODEL="")
        with patch.object(ai_provider, "settings", configured):
            with self.assertRaises(ai_provider.AIProviderError):
                await ai_provider.generate_text(system_prompt="Regras", user_prompt="Pedido")


if __name__ == "__main__":
    unittest.main()
