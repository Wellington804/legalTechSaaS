import base64
import binascii
import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, ConfigDict, Field, field_validator


PUSH_HOSTS = frozenset({"fcm.googleapis.com", "updates.push.services.mozilla.com", "updates-autopush.push.services.mozilla.com", "web.push.apple.com"})


def decode_url_key(value: str, length: int) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
        raise ValueError("Chave push invalida.")
    try:
        decoded = base64.b64decode(value.rstrip("=") + "=" * (-len(value.rstrip("=")) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Chave push invalida.") from exc
    if len(decoded) != length:
        raise ValueError("Chave push invalida.")
    return decoded


def validate_endpoint(value: str) -> str:
    if not value.isascii() or len(value) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValueError("Endereco push invalido.")
    parsed = urlsplit(value)
    # Google/Mozilla publish URL-safe path tokens. Apple's subscription URL stays opaque.
    noncanonical_token = parsed.hostname != "web.push.apple.com" and (
        parsed.query or "%" in parsed.path or any(part in {"", ".", ".."} for part in parsed.path.split("/")[1:]))
    if (parsed.scheme != "https" or parsed.hostname not in PUSH_HOSTS or parsed.port not in {None, 443}
            or parsed.username or parsed.password or parsed.fragment or not parsed.path or parsed.path == "/"
            or "\\" in parsed.path or noncanonical_token):
        raise ValueError("Provedor push nao permitido.")
    # A default port or capitalized host must not create a second device ownership key.
    return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=86, max_length=90)
    auth: str = Field(min_length=22, max_length=24)

    @field_validator("p256dh")
    @classmethod
    def check_public_key(cls, value):
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decode_url_key(value, 65))
        return value.rstrip("=")

    @field_validator("auth")
    @classmethod
    def check_auth(cls, value):
        decode_url_key(value, 16)
        return value.rstrip("=")


class PushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=20, max_length=2048)
    keys: PushKeys
    label: str = Field(min_length=1, max_length=80)
    consent: Literal[True]

    @field_validator("endpoint")
    @classmethod
    def check_endpoint(cls, value):
        return validate_endpoint(value)

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Consentimento explicito obrigatorio.")
        return value

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Nome de dispositivo invalido.")
        return value


class PushSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    endpoint_hash: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
