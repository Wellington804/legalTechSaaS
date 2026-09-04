"""Server-side Evolution Go lifecycle; provider credentials never reach the browser."""
import base64
import re
from urllib.parse import quote

import httpx

from app.core.config import settings


MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024


class EvolutionProviderError(RuntimeError):
    pass


def configured() -> bool:
    return bool(
        settings.EVOLUTION_ENABLED
        and settings.EVOLUTION_GO_URL
        and settings.EVOLUTION_API_KEY
        and not settings.NOTIFICATIONS_DRY_RUN
    )


def _payload_data(payload):
    return payload.get("data", payload) if isinstance(payload, dict) else {}


async def _request(method: str, path: str, api_key: str, *, body=None, qr_pending_ok=False, already_exists_ok=False):
    url = f"{settings.EVOLUTION_GO_URL.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, headers={"apikey": api_key}, json=body)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise EvolutionProviderError("provider_unavailable") from exc
    if qr_pending_ok and response.status_code == 400:
        return None
    if already_exists_ok and response.status_code == 500 and len(response.content) <= MAX_PROVIDER_RESPONSE_BYTES:
        try:
            if response.json().get("error") == "instance already exists":
                return {}
        except (AttributeError, ValueError):
            pass
    if response.status_code == 429 or response.status_code >= 500:
        raise EvolutionProviderError("provider_unavailable")
    if response.status_code >= 400:
        raise EvolutionProviderError("provider_rejected")
    if len(response.content) > MAX_PROVIDER_RESPONSE_BYTES:
        raise EvolutionProviderError("provider_response_too_large")
    try:
        payload = response.json()
    except ValueError as exc:
        raise EvolutionProviderError("provider_response_invalid") from exc
    if not isinstance(payload, dict):
        raise EvolutionProviderError("provider_response_invalid")
    return payload


async def ensure_instance(instance_id: str, token: str) -> None:
    await _request(
        "POST",
        "/instance/create",
        settings.EVOLUTION_API_KEY or "",
        body={
            "instanceId": instance_id,
            "name": f"lexflow-{instance_id.replace('-', '')[:16]}",
            "token": token,
            "advancedSettings": {
                "alwaysOnline": False,
                "rejectCall": False,
                "readMessages": False,
                "ignoreGroups": True,
                "ignoreStatus": True,
            },
        },
        already_exists_ok=True,
    )


async def connect(token: str) -> str | None:
    await _request(
        "POST",
        "/instance/connect",
        token,
        body={
            "webhookUrl": f"{settings.FRONTEND_URL.rstrip('/')}{settings.API_V1_STR}/notifications/webhooks/evolution",
            "subscribe": ["READ_RECEIPT", "CONNECTION", "QRCODE"],
            "rabbitmqEnable": "disabled",
            "websocketEnable": "disabled",
            "natsEnable": "disabled",
        },
    )
    return await qr_code(token)


async def qr_code(token: str) -> str | None:
    payload = await _request("GET", "/instance/qr", token, qr_pending_ok=True)
    if payload is None:
        return None
    value = _payload_data(payload).get("qrcode")
    if not isinstance(value, str) or not value.startswith("data:image/png;base64,"):
        raise EvolutionProviderError("provider_qr_invalid")
    encoded = value.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise EvolutionProviderError("provider_qr_invalid") from exc
    if len(raw) > 1024 * 1024 or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise EvolutionProviderError("provider_qr_invalid")
    return value


async def status(token: str) -> dict:
    payload = await _request("GET", "/instance/status", token)
    data = _payload_data(payload)
    return {
        "connected": bool(data.get("Connected", data.get("connected", False))),
        "logged_in": bool(data.get("LoggedIn", data.get("loggedIn", data.get("logged_in", False)))),
    }


async def phone_number(instance_id: str) -> str | None:
    payload = await _request(
        "GET", f"/instance/info/{quote(instance_id, safe='')}", settings.EVOLUTION_API_KEY or ""
    )
    return phone_from_jid(_payload_data(payload).get("jid"))


def phone_from_jid(jid) -> str | None:
    if not isinstance(jid, str):
        return None
    digits = re.sub(r"\D", "", jid.split("@", 1)[0].split(":", 1)[0])
    return f"+{digits}" if 10 <= len(digits) <= 15 else None


async def reconnect(token: str) -> None:
    await _request("POST", "/instance/reconnect", token, body={})


async def delete_instance(instance_id: str) -> None:
    await _request(
        "DELETE", f"/instance/delete/{quote(instance_id, safe='')}", settings.EVOLUTION_API_KEY or ""
    )
