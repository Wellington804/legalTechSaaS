import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk

from app.core.config import settings


_SENSITIVE_KEYS = {
    "authorization", "cookie", "cookies", "password", "passwd", "secret",
    "token", "accesstoken", "refreshtoken", "instancetoken", "apikey", "xapikey",
    "clientsecret", "hashedpassword", "document", "documento", "recipient",
    "content", "body", "cpf", "cnpj", "rg", "oab", "email", "phone", "telefone",
}
_PII_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._~-]+", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}(?!\d)"),
)


def _scrub(value: Any, key: str = "") -> Any:
    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
    if normalized_key in _SENSITIVE_KEYS:
        return "[Filtered]"
    if isinstance(value, dict):
        return {str(k): _scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(item) for item in value]
    if isinstance(value, str):
        for pattern in _PII_PATTERNS:
            value = pattern.sub("[Filtered]", value)
    return value


def before_send(event: dict[str, Any], _: dict[str, Any]) -> dict[str, Any]:
    for key in ("extra", "contexts", "breadcrumbs", "tags"):
        event.pop(key, None)
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("headers", None)
        request.pop("query_string", None)
        raw_url = request.pop("url", None)
        if isinstance(raw_url, str):
            try:
                url = urlsplit(raw_url)
                if url.scheme in {"http", "https"} and url.hostname:
                    request["url"] = urlunsplit(
                        (url.scheme, url.netloc.rsplit("@", 1)[-1], url.path, "", "")
                    )
            except ValueError:
                pass

    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if user.get("id") else {}
    for value in event.get("exception", {}).get("values", []):
        for frame in value.get("stacktrace", {}).get("frames", []):
            frame.pop("vars", None)
    return _scrub(event)


def init_sentry() -> None:
    if not settings.SENTRY_DSN or sentry_sdk.is_initialized():
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.RELEASE,
        send_default_pii=False,
        # ponytail: error-only until transaction/span payloads have a tested privacy policy.
        traces_sample_rate=0.0,
        include_local_variables=False,
        before_send=before_send,
    )
