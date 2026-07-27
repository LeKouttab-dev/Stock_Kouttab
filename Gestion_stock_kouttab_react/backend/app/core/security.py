"""Security primitives: password hashing, JWT, validation helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException


def _bcrypt_safe(password: str) -> bytes:
    """Encode and clamp to 72 bytes (bcrypt's hard limit)."""
    encoded = password.encode("utf-8")
    return encoded[:72]


# ---- Password hashing -------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(_bcrypt_safe(plain), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a bcrypt hash."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_bcrypt_safe(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_password_legacy(plain: str, hashed: str) -> bool:
    """Verify a legacy SHA256 hash (Streamlit version)."""
    if not plain or not hashed:
        return False
    if len(hashed) != 64:
        return False
    try:
        sha = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        return sha == hashed.lower()
    except Exception:  # noqa: BLE001
        return False


def is_legacy_hash(hashed: str | None) -> bool:
    """Detect a SHA256-only hash from the legacy app."""
    if not hashed:
        return False
    return len(hashed) == 64 and all(c in "0123456789abcdefABCDEF" for c in hashed)


# ---- JWT --------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str | int,
    role: str,
    expires_delta: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Sign a short-lived access token."""
    expire = _now() + (expires_delta or timedelta(minutes=settings.jwt_access_token_minutes))
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "iat": int(_now().timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | int) -> str:
    """Sign a long-lived refresh token."""
    expire = _now() + timedelta(days=settings.jwt_refresh_token_days)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "iat": int(_now().timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises :class:`AppException` with ``TOKEN_EXPIRED`` when the JWT is past its
    ``exp`` claim, and ``TOKEN_INVALID`` for any other parsing/signature error.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except ExpiredSignatureError as exc:
        raise AppException(ErrorCode.TOKEN_EXPIRED) from exc
    except JWTError as exc:
        raise AppException(ErrorCode.TOKEN_INVALID) from exc


# ---- Validators -------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_SPECIAL_RE = re.compile(r"[!@#$%^&*()_\-+=\[\]{}|;:,.<>?/~`'\"\\]")


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Enforce 8+ chars, uppercase, lowercase, digit and symbol."""
    if not password or len(password) < 8:
        return False, "Le mot de passe doit faire au moins 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return False, "Le mot de passe doit contenir au moins une majuscule."
    if not re.search(r"[a-z]", password):
        return False, "Le mot de passe doit contenir au moins une minuscule."
    if not re.search(r"[0-9]", password):
        return False, "Le mot de passe doit contenir au moins un chiffre."
    if not _SPECIAL_RE.search(password):
        return False, "Le mot de passe doit contenir au moins un caractere special."
    return True, "OK"


def validate_username(username: str) -> bool:
    if not username:
        return False
    return bool(_USERNAME_RE.match(username))


def validate_email_str(email: str) -> bool:
    if not email:
        return False
    return bool(_EMAIL_RE.match(email))


# ---- Invitation token hashing ----------------------------------------------

def hash_invitation_token(token: str) -> str:
    """SHA256 hash of an invitation token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
