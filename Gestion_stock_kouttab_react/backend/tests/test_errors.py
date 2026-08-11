"""Tests for the unified error envelope (`{code, message, extras}`)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.crud import user as user_crud


def _signup_payload(username: str | None = None) -> dict:
    username = username or f"user{uuid.uuid4().hex[:8]}"
    return {
        "username": username,
        "password": "Strong#Pass1",
        "confirm_password": "Strong#Pass1",
        "role": "Benevole",
        "nom": "Test",
        "prenom": "User",
        "email": f"{username}@example.com",
    }


def test_login_with_wrong_password_returns_invalid_credentials_code(
    client: TestClient, db_session: Session
) -> None:
    """A failed login must yield ``AUTH_1001`` with a French message."""
    payload = _signup_payload()
    user_crud.create_user(
        db_session,
        username=payload["username"],
        password=payload["password"],
        role="Benevole",
        email=payload["email"],
        validation_status="active",
    )
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": payload["username"], "password": "wrong-password"},
    )
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["code"] == ErrorCode.INVALID_CREDENTIALS.value
    assert body["message"] == "Identifiants incorrects."
    # Backwards-compat keys remain present.
    assert body["error"] == ErrorCode.INVALID_CREDENTIALS.value


def test_unknown_endpoint_returns_404_with_code(client: TestClient) -> None:
    """Hitting a missing route must return 404 wrapped in the standard envelope."""
    resp = client.get("/api/v1/this-endpoint-does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == ErrorCode.NOT_FOUND.value
    assert "message" in body and isinstance(body["message"], str)


def test_invalid_signup_body_returns_validation_error(client: TestClient) -> None:
    """Pydantic validation failures expose ``VAL_5001`` and a list of fields."""
    # Missing required fields (no username, no password).
    resp = client.post("/api/v1/auth/signup", json={"role": "Benevole"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == ErrorCode.VALIDATION_ERROR.value
    assert body["message"]
    extras = body.get("extras") or {}
    # We expose either an "errors" list (raw Pydantic) or a "fields" list.
    assert "errors" in extras or "fields" in extras


def test_role_required_returns_perm_2002(client: TestClient, db_session: Session) -> None:
    """A Benevole hitting a Super-Admin-only endpoint receives ``PERM_2002``."""
    payload = _signup_payload()
    user_crud.create_user(
        db_session,
        username=payload["username"],
        password=payload["password"],
        role="Benevole",
        email=payload["email"],
        validation_status="active",
    )
    login = client.post(
        "/api/v1/auth/login",
        data={"username": payload["username"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    resp = client.get(
        "/api/v1/users/pending", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["code"] == ErrorCode.ROLE_REQUIRED.value
