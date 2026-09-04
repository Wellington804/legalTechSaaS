from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import settings


GENERIC_SUBJECT = "Nova solicitação no LegalTech"
GENERIC_MESSAGE = "Você possui uma nova solicitação no LegalTech. Acesse a plataforma com sua conta para consultar."


@dataclass(frozen=True)
class ProviderResult:
    status: Literal["sent", "queued", "unknown", "failed"]
    message_id: str | None = None
    error_code: str | None = None
    retryable: bool = False


def provider_is_configured(channel: str) -> bool:
    if getattr(settings, "NOTIFICATIONS_DRY_RUN", False):
        return False
    if channel == "email":
        return bool(
            getattr(settings, "RESEND_ENABLED", False)
            and getattr(settings, "RESEND_API_KEY", None)
            and getattr(settings, "RESEND_FROM_EMAIL", None)
        )
    # Case-bound delivery supplies the tenant's encrypted instance credentials later.
    return bool(
        getattr(settings, "EVOLUTION_ENABLED", False)
        and getattr(settings, "EVOLUTION_GO_URL", None)
        and getattr(settings, "EVOLUTION_API_KEY", None)
    )


async def send_resend(
    delivery_id: str,
    recipient: str,
    *,
    text: str | None = None,
    subject: str | None = None,
) -> ProviderResult:
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Idempotency-Key": delivery_id,
    }
    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [recipient],
        "subject": GENERIC_SUBJECT if subject is None else subject,
        "text": GENERIC_MESSAGE if text is None else text,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post("https://api.resend.com/emails", headers=headers, json=payload)
    except (httpx.TimeoutException, httpx.NetworkError):
        return ProviderResult("queued", error_code="provider_unavailable", retryable=True)

    if response.status_code == 429 or response.status_code >= 500:
        return ProviderResult("queued", error_code="provider_unavailable", retryable=True)
    if response.status_code >= 400:
        return ProviderResult("failed", error_code="provider_rejected")
    try:
        message_id = response.json().get("id")
    except ValueError:
        message_id = None
    if not isinstance(message_id, str) or not message_id:
        return ProviderResult("unknown", error_code="provider_response_invalid")
    return ProviderResult("sent", message_id=message_id)


async def send_evolution(
    recipient: str,
    *,
    text: str | None = None,
    instance_id: str | None = None,
    api_key: str | None = None,
) -> ProviderResult:
    if not instance_id or not api_key:
        return ProviderResult("failed", error_code="provider_not_configured")
    headers = {
        "apikey": api_key,
        "instanceId": instance_id,
    }
    payload = {
        "number": recipient.removeprefix("+"),
        "text": GENERIC_MESSAGE if text is None else text,
    }
    url = f"{settings.EVOLUTION_GO_URL.rstrip('/')}/send/text"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.ConnectError:
        return ProviderResult("failed", error_code="provider_unavailable")
    except (httpx.TimeoutException, httpx.NetworkError):
        # Evolution Go has no idempotency contract. Retrying an ambiguous request can duplicate it.
        return ProviderResult("unknown", error_code="provider_outcome_unknown")

    if response.status_code >= 500:
        return ProviderResult("unknown", error_code="provider_outcome_unknown")
    if response.status_code >= 400:
        return ProviderResult("failed", error_code="provider_rejected")
    try:
        body = response.json()
        message_id = body.get("messageId") or body.get("data", {}).get("Info", {}).get("ID")
    except (AttributeError, ValueError):
        message_id = None
    if not isinstance(message_id, str) or not message_id:
        return ProviderResult("unknown", error_code="provider_response_invalid")
    return ProviderResult("sent", message_id=message_id)
