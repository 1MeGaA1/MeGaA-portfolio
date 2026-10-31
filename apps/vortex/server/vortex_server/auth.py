"""Password hashing (stdlib scrypt) and in-memory staff tokens."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return "scrypt$%s$%s" % (
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, salt_b64, digest_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return hmac.compare_digest(digest, expected)


def new_station_key() -> str:
    return secrets.token_urlsafe(24)


@dataclass
class TokenInfo:
    staff_id: int
    expires_at: float


class TokenStore:
    """Bearer tokens for the admin panel. Lives in memory: a server restart
    simply asks staff to log in again."""

    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self._tokens: dict[str, TokenInfo] = {}

    def issue(self, staff_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = TokenInfo(staff_id, time.time() + self.ttl)
        return token

    def resolve(self, token: str | None) -> int | None:
        if not token:
            return None
        info = self._tokens.get(token)
        if info is None:
            return None
        if info.expires_at < time.time():
            self._tokens.pop(token, None)
            return None
        return info.staff_id

    def revoke(self, token: str | None) -> None:
        if token:
            self._tokens.pop(token, None)
