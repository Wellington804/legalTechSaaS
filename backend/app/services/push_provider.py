"""One privacy-safe Web Push payload; no arbitrary destination or message API."""
import json
import hashlib
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import redis
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from app.core.config import settings
from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret
from app.schemas.push import PushKeys, decode_url_key, validate_endpoint


@dataclass(frozen=True)
class PushResult:
    status: str
    error_code: str | None = None
    retryable: bool = False


class _PushSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def post(self, url, **kwargs):
        validate_endpoint(url)
        kwargs.update(allow_redirects=False, timeout=(5, 10), stream=True)
        response = super().post(url, **kwargs)
        # No provider body is necessary. Do not load/log endpoint-bearing error pages.
        response.close()
        response._content = b""
        return response


def classify_response(status_code: int) -> PushResult:
    if 200 <= status_code < 300:
        return PushResult("accepted")
    if status_code in {404, 410}:
        return PushResult("expired", "subscription_expired")
    if status_code == 429:
        return PushResult("queued", "provider_rate_limited", retryable=True)
    if 500 <= status_code < 600:
        # A provider's 5xx can occur after enqueueing: no documented idempotency key.
        return PushResult("unknown", "provider_outcome_unknown")
    return PushResult("failed", "provider_rejected")


class PushCacheError(Exception):
    pass


def _vapid_headers(private_key: str, subject: str, audience: str) -> dict:
    """Share a four-hour token across workers/restarts; Apple limits JWT renewal frequency."""
    vapid = Vapid()
    vapid.private_key = ec.derive_private_key(int.from_bytes(decode_url_key(private_key, 32), "big"), ec.SECP256R1())
    public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint).hex()
    cache_key = "legaltech:push:vapid:" + hashlib.sha256(f"{public}:{subject}:{audience}".encode()).hexdigest()
    try:
        with redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=3, socket_timeout=3, decode_responses=True) as client:
            cached = client.get(cache_key)
            if cached is None:
                headers = vapid.sign({"sub": subject, "aud": audience, "exp": int(time.time()) + 12 * 3600})
                encrypted = encrypt_mfa_secret(json.dumps(headers))
                if client.set(cache_key, encrypted, nx=True, ex=4 * 3600):
                    return headers
                cached = client.get(cache_key)  # A concurrent worker's winner is authoritative.
            if not cached:
                raise PushCacheError()
            headers = json.loads(decrypt_mfa_secret(cached))
            if not isinstance(headers, dict) or set(headers) != {"Authorization"} or not isinstance(headers["Authorization"], str):
                raise PushCacheError()
            return headers
    except (redis.RedisError, RuntimeError, ValueError) as exc:
        raise PushCacheError() from exc


def send_push(subscription: dict, delivery_id: str, *, ttl: int = 86400) -> PushResult:
    if not settings.WEB_PUSH_ENABLED:
        return PushResult("queued", "provider_disabled", retryable=True)
    try:
        endpoint = validate_endpoint(subscription["endpoint"])
        keys = PushKeys.model_validate(subscription["keys"]).model_dump()
        parsed = urlsplit(endpoint)
        headers = _vapid_headers(settings.WEB_PUSH_VAPID_PRIVATE_KEY or "", settings.WEB_PUSH_VAPID_SUBJECT or "",
                                 f"https://{parsed.netloc}")
        payload = json.dumps({"title": "LegalFlow", "body": "Há uma atualização no seu escritório. Entre no LegalFlow para consultar.", "url": "/dashboard", "tag": delivery_id}, ensure_ascii=False)
        with _PushSession() as session:
            response = webpush(subscription_info={"endpoint": endpoint, "keys": keys}, data=payload,
                               requests_session=session, timeout=10, ttl=max(0, min(ttl, 86400)),
                               headers={**headers, "Urgency": "normal"})
        return classify_response(response.status_code)
    except PushCacheError:
        return PushResult("queued", "vapid_cache_unavailable", retryable=True)
    except WebPushException as exc:
        if exc.response is not None:
            return classify_response(exc.response.status_code)
        return PushResult("failed", "push_encryption_failed")
    except requests.ConnectTimeout:
        return PushResult("queued", "provider_connect_timeout", retryable=True)
    except (requests.Timeout, requests.ConnectionError):
        return PushResult("unknown", "provider_outcome_unknown")
    except (ValueError, KeyError, TypeError):
        return PushResult("failed", "invalid_subscription")
