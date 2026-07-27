"""Unit tests for app.crud.invitation."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.crud import invitation as invitation_crud


pytestmark = pytest.mark.unit


def _email() -> str:
    return f"inv_{uuid.uuid4().hex[:8]}@example.com"


def test_create_invitation_persists_sha256_token_hash(db_session) -> None:
    email = _email()
    inv, token = invitation_crud.create_invitation(db_session, email)
    assert inv.id > 0
    assert inv.email == email
    assert inv.used is False
    assert inv.attempts == 0
    # token_hash must be the SHA256 of the plaintext token.
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert inv.token_hash == expected


def test_validate_token_ok_when_fresh(db_session) -> None:
    email = _email()
    _, token = invitation_crud.create_invitation(db_session, email)
    ok, message, inv = invitation_crud.validate_token(db_session, token, email)
    assert ok is True
    assert inv is not None
    assert "valide" in message.lower()


def test_validate_token_returns_false_when_expired(db_session) -> None:
    email = _email()
    inv, token = invitation_crud.create_invitation(db_session, email)
    # Force expiration in the past.
    inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    ok, message, _ = invitation_crud.validate_token(db_session, token, email)
    assert ok is False
    assert "expir" in message.lower()


def test_validate_token_returns_false_when_used(db_session) -> None:
    email = _email()
    inv, token = invitation_crud.create_invitation(db_session, email)
    invitation_crud.mark_used(db_session, inv)
    ok, message, _ = invitation_crud.validate_token(db_session, token, email)
    assert ok is False
    assert "utilis" in message.lower() or "deja" in message.lower()


def test_mark_used_flips_flag(db_session) -> None:
    email = _email()
    inv, _ = invitation_crud.create_invitation(db_session, email)
    assert inv.used is False
    invitation_crud.mark_used(db_session, inv)
    db_session.refresh(inv)
    assert inv.used is True
