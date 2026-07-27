"""Unit tests for app.core.security primitives."""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest

from app.core.exceptions import AppException
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    is_legacy_hash,
    validate_email_str,
    validate_password_strength,
    validate_username,
    verify_password,
    verify_password_legacy,
)


pytestmark = pytest.mark.unit


def test_hash_and_verify_password_bcrypt() -> None:
    plain = "Strong#Pass1"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2")  # bcrypt prefix
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_legacy_sha256() -> None:
    plain = "legacy_pass"
    sha = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    assert verify_password_legacy(plain, sha) is True
    assert verify_password_legacy("nope", sha) is False
    # Wrong hash length -> False (early return).
    assert verify_password_legacy(plain, "deadbeef") is False


def test_is_legacy_hash_detection() -> None:
    sha = hashlib.sha256(b"x").hexdigest()
    bcrypt_hash = hash_password("x")
    assert is_legacy_hash(sha) is True
    assert is_legacy_hash(bcrypt_hash) is False
    assert is_legacy_hash("") is False
    assert is_legacy_hash(None) is False


def test_create_and_decode_access_token_round_trip() -> None:
    token = create_access_token(42, "Super Admin")
    decoded = decode_token(token)
    assert decoded["sub"] == "42"
    assert decoded["role"] == "Super Admin"
    assert decoded["type"] == "access"


def test_decode_token_expired_raises_token_expired() -> None:
    # Negative expiry -> token already expired.
    expired = create_access_token(1, "Benevole", expires_delta=timedelta(seconds=-30))
    with pytest.raises(AppException) as exc_info:
        decode_token(expired)
    assert exc_info.value.code_value == "AUTH_1010"


def test_decode_token_invalid_signature_raises_token_invalid() -> None:
    with pytest.raises(AppException) as exc_info:
        decode_token("not.a.real.token")
    assert exc_info.value.code_value == "AUTH_1011"


def test_validate_password_strength_accepts_strong_password() -> None:
    ok, _ = validate_password_strength("Strong#Pass1")
    assert ok is True


@pytest.mark.parametrize(
    "weak_password",
    [
        "Aa1!",  # too short (4 chars)
        "alllowercase1!",  # no uppercase
        "ALLUPPERCASE1!",  # no lowercase
        "NoSpecialAaB",  # no digit AND no special char
        "NoSpecial1Aa",  # no special char
    ],
)
def test_validate_password_strength_rejects_weak_passwords(weak_password: str) -> None:
    ok, msg = validate_password_strength(weak_password)
    assert ok is False
    assert isinstance(msg, str) and msg


def test_validate_username_accepts_valid_and_rejects_invalid() -> None:
    assert validate_username("alice_42") is True
    assert validate_username("Alice123") is True
    assert validate_username("ab") is False  # too short
    assert validate_username("a" * 21) is False  # too long
    assert validate_username("with space") is False
    assert validate_username("with-dash") is False
    assert validate_username("") is False


def test_validate_email_str() -> None:
    assert validate_email_str("alice@example.com") is True
    assert validate_email_str("a.b+c@sub.example.fr") is True
    assert validate_email_str("nope") is False
    assert validate_email_str("a@b") is False
    assert validate_email_str("") is False
