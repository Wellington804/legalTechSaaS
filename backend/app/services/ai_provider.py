"""Bounded text generation for reviewed, non-autonomous legal assistance."""
import json
import re
from typing import Literal

import httpx

from app.core.config import settings


MAX_RESPONSE_BYTES = 100_000
GEMINI_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
OPENROUTER_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9_.:/-]{1,200}$")


class AIProviderError(RuntimeError):
    pass


Purpose = Literal["general", "deep", "legal", "visual"]


def provider_name(config=None) -> str:
    active = config if config is not None else settings
    return getattr(active, "AI_PROVIDER", "gemini")


def _openrouter_route(active, purpose: Purpose) -> tuple[str | None, str, str | None]:
    fallback = getattr(active, "OPENROUTER_GENERAL_MODEL", "") or getattr(active, "OPENROUTER_MODEL", "")
    key = getattr(active, "OPENROUTER_API_KEY", None)
    if purpose == "visual":
        return getattr(active, "OPENROUTER_VISUAL_API_KEY", None), getattr(active, "OPENROUTER_VISUAL_MODEL", ""), None
    if purpose == "deep":
        return key, getattr(active, "OPENROUTER_DEEP_MODEL", "") or fallback, getattr(active, "OPENROUTER_DEEP_REASONING", "max")
    if purpose == "legal":
        return key, getattr(active, "OPENROUTER_LEGAL_MODEL", "") or fallback, None
    return key, fallback, getattr(active, "OPENROUTER_GENERAL_REASONING", "low")


def model_name(config=None, purpose: Purpose = "general") -> str:
    active = config if config is not None else settings
    return _openrouter_route(active, purpose)[1] if provider_name(active) == "openrouter" else getattr(active, "GEMINI_MODEL", "")


def ai_available(config=None, purpose: Purpose = "general") -> bool:
    active = config if config is not None else settings
    if not getattr(active, "AI_ENABLED", False):
        return False
    if provider_name(active) == "openrouter":
        key, model, _reasoning = _openrouter_route(active, purpose)
        return bool(key and OPENROUTER_MODEL_PATTERN.fullmatch(model))
    key, model = getattr(active, "GEMINI_API_KEY", None), getattr(active, "GEMINI_MODEL", "")
    return bool(key and GEMINI_MODEL_PATTERN.fullmatch(model))


async def _bounded_json(url: str, *, headers: dict[str, str], payload: dict,
                        max_response_bytes: int = MAX_RESPONSE_BYTES, timeout_seconds: int = 45) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if not response.is_success or int(response.headers.get("content-length", "0")) > max_response_bytes:
                    raise AIProviderError("provider unavailable")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > max_response_bytes:
                        raise AIProviderError("provider response too large")
                    body.extend(chunk)
        decoded = json.loads(body)
        if not isinstance(decoded, dict):
            raise AIProviderError("invalid provider response")
        return decoded
    except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as exc:
        if isinstance(exc, AIProviderError):
            raise
        raise AIProviderError("provider request failed") from exc


def _validate_multimodal(parts: list[dict]) -> None:
    if not 1 <= len(parts) <= 12:
        raise AIProviderError("multimodal prompt outside limits")
    encoded = json.dumps(parts, ensure_ascii=True)
    if len(encoded) > 15_000_000:
        raise AIProviderError("multimodal prompt outside limits")
    for part in parts:
        if not isinstance(part, dict) or part.get("type") not in {"text", "image_url", "file"}:
            raise AIProviderError("invalid multimodal prompt")
        if part["type"] == "text" and not isinstance(part.get("text"), str):
            raise AIProviderError("invalid multimodal prompt")
        if part["type"] == "image_url" and not isinstance(part.get("image_url", {}).get("url"), str):
            raise AIProviderError("invalid multimodal prompt")
        if part["type"] == "file" and not isinstance(part.get("file", {}).get("file_data"), str):
            raise AIProviderError("invalid multimodal prompt")


async def generate_text(*, system_prompt: str, user_prompt: str | None = None,
                        user_content: list[dict] | None = None, purpose: Purpose = "general",
                        max_output_tokens: int = 2048, temperature: float = 0.2,
                        response_schema: dict | None = None, config=None) -> str:
    active = config if config is not None else settings
    if not ai_available(active, purpose):
        raise AIProviderError("provider not configured")
    if not 1 <= len(system_prompt) <= 12_000 or (user_prompt is None) == (user_content is None):
        raise AIProviderError("prompt outside limits")
    if user_prompt is not None and not 1 <= len(user_prompt) <= 60_000:
        raise AIProviderError("prompt outside limits")
    if user_content is not None:
        if purpose != "visual":
            raise AIProviderError("multimodal prompt requires visual route")
        _validate_multimodal(user_content)
    if provider_name(active) == "openrouter":
        key, model, reasoning = _openrouter_route(active, purpose)
        payload: dict = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_content if user_content is not None else user_prompt}],
            "max_tokens": max_output_tokens,
            "provider": {"zdr": True, "data_collection": "deny", "allow_fallbacks": True},
        }
        if reasoning:
            payload["reasoning"] = {"effort": reasoning}
        elif purpose != "visual":
            payload["temperature"] = temperature
        if response_schema:
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "lexflow_response", "strict": True, "schema": response_schema,
            }}
        result = await _bounded_json("https://openrouter.ai/api/v1/chat/completions", headers={
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": active.FRONTEND_URL,
            "X-Title": active.OPENROUTER_APP_NAME,
            "Content-Type": "application/json",
        }, payload=payload)
        try:
            text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("invalid provider response") from exc
    else:
        if user_content is not None:
            raise AIProviderError("multimodal prompt unsupported by configured provider")
        generation = {"maxOutputTokens": max_output_tokens, "temperature": temperature, "candidateCount": 1}
        if response_schema:
            generation.update({"responseMimeType": "application/json", "responseJsonSchema": response_schema})
        result = await _bounded_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{active.GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": active.GEMINI_API_KEY or "", "Content-Type": "application/json"},
            payload={"systemInstruction": {"parts": [{"text": system_prompt}]},
                     "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                     "generationConfig": generation},
        )
        try:
            parts = result["candidates"][0]["content"]["parts"]
            text = "\n".join(part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str))
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("invalid provider response") from exc
    if not isinstance(text, str) or not text.strip() or len(text) > 32_000:
        raise AIProviderError("invalid generated text")
    return text.strip()
