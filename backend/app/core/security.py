import base64
import binascii
import hashlib
import hmac
import re
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from cryptography.fernet import Fernet, InvalidToken as FernetInvalidToken
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_policy(password: str) -> None:
    password_bytes = len(password.encode("utf-8"))
    if password_bytes < 12 or password_bytes > 72:
        raise ValueError("a senha deve ter entre 12 e 72 bytes")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("a senha deve conter letras e numeros")


def create_access_token(
    subject: str | Any,
    tenant_id: str,
    expires_delta: Optional[timedelta] = None,
    *,
    session_id: str | None = None,
    mfa_verified: bool = False,
) -> str:
    issued_at = datetime.now(timezone.utc)
    expire = issued_at + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode: dict[str, Any] = {
        "exp": expire,
        "iat": issued_at,
        "sub": str(subject),
        "tenant_id": str(tenant_id),
    }
    if session_id:
        to_encode["sid"] = str(session_id)
    if mfa_verified:
        to_encode["mfa"] = True
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        if not isinstance(payload.get("tenant_id"), str) or not payload["tenant_id"]:
            return None
        return payload
    except InvalidTokenError:
        return None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_account_token(token: str) -> str:
    pepper = getattr(settings, "ACCOUNT_TOKEN_PEPPER", None)
    if not pepper:
        if getattr(settings, "is_hardened_environment", False):
            raise RuntimeError("Account token pepper is not configured")
        pepper = settings.SECRET_KEY
    return hashlib.sha256(f"{pepper}:{token}".encode("utf-8")).hexdigest()


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_at(secret: str, timestamp: int) -> str:
    normalized = secret.strip().replace(" ", "").upper()
    padded = normalized + "=" * (-len(normalized) % 8)
    key = base64.b32decode(padded, casefold=True)
    counter = struct.pack(">Q", timestamp // TOTP_STEP_SECONDS)
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = ((digest[offset] & 0x7F) << 24) | (digest[offset + 1] << 16) | (
        digest[offset + 2] << 8
    ) | digest[offset + 3]
    return str(binary % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp_code(secret: str, code: str, *, now: int | None = None) -> bool:
    return matching_totp_counter(secret, code, now=now) is not None


def matching_totp_counter(secret: str, code: str, *, now: int | None = None) -> int | None:
    normalized_code = re.sub(r"\s+", "", code)
    if not re.fullmatch(rf"[0-9]{{{TOTP_DIGITS}}}", normalized_code):
        return None
    timestamp = int(time.time()) if now is None else now
    try:
        for offset in (-1, 0, 1):
            candidate_timestamp = timestamp + offset * TOTP_STEP_SECONDS
            if hmac.compare_digest(normalized_code, _totp_at(secret, candidate_timestamp)):
                return candidate_timestamp // TOTP_STEP_SECONDS
        return None
    except (ValueError, binascii.Error):
        return None


def _fernet() -> Fernet:
    configured_key = getattr(settings, "MFA_ENCRYPTION_KEY", None)
    if configured_key:
        key = configured_key.encode("ascii")
    else:
        if getattr(settings, "is_hardened_environment", False):
            raise RuntimeError("MFA encryption key is not configured")
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("MFA encryption key is invalid") from exc


def encrypt_mfa_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    try:
        return _fernet().decrypt(encrypted_secret.encode("ascii")).decode("ascii")
    except (FernetInvalidToken, UnicodeDecodeError) as exc:
        raise RuntimeError("Stored MFA secret is invalid") from exc


def new_recovery_codes(count: int = 10) -> list[str]:
    return [secrets.token_urlsafe(12) for _ in range(count)]


def demo() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    assert verify_totp_code(secret, _totp_at(secret, 1_700_000_000), now=1_700_000_000)
    assert not verify_totp_code(secret, "000000", now=1_700_000_000)
    assert hash_account_token("opaque") != "opaque"


if __name__ == "__main__":
    demo()
