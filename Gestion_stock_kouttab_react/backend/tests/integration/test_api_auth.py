"""End-to-end tests for the /auth endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints import auth as auth_endpoint
from app.crud import user as user_crud


pytestmark = pytest.mark.integration


def _signup_payload(username: str | None = None, password: str = "Strong#Pass1") -> dict:
    username = username or f"user{uuid.uuid4().hex[:8]}"
    return {
        "username": username,
        "password": password,
        "confirm_password": password,
        "role": "Benevole",
        "nom": "Test",
        "prenom": "User",
        "email": f"{username}@example.com",
    }


@pytest.fixture(autouse=True)
def _clear_login_lockouts():
    """Reset the in-memory lockout dict between tests."""
    auth_endpoint._login_attempts.clear()
    yield
    auth_endpoint._login_attempts.clear()


def test_signup_happy_path_creates_pending_user(client: TestClient) -> None:
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == payload["username"]
    assert body["validation_status"] == "pending"


def test_signup_with_weak_password_returns_password_weak(client: TestClient) -> None:
    payload = _signup_payload(password="weakpass")
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == "AUTH_1020"


def test_signup_username_taken_returns_conflict(
    client: TestClient, db_session: Session
) -> None:
    payload = _signup_payload()
    # First signup OK.
    r1 = client.post("/api/v1/auth/signup", json=payload)
    assert r1.status_code == 201, r1.text
    # Second with same username -> 409 USERNAME_TAKEN.
    payload2 = dict(payload)
    payload2["email"] = f"{payload['username']}_2@example.com"
    r2 = client.post("/api/v1/auth/signup", json=payload2)
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "AUTH_1023"


def test_login_json_with_correct_credentials_returns_tokens(
    client: TestClient, db_session: Session
) -> None:
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
        "/api/v1/auth/login/json",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == payload["username"]


def test_login_json_with_wrong_password_returns_invalid_credentials(
    client: TestClient, db_session: Session
) -> None:
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
        "/api/v1/auth/login/json",
        json={"username": payload["username"], "password": "wrong-password"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == "AUTH_1001"


def test_login_locks_out_after_five_failures(
    client: TestClient, db_session: Session
) -> None:
    payload = _signup_payload()
    user_crud.create_user(
        db_session,
        username=payload["username"],
        password=payload["password"],
        role="Benevole",
        email=payload["email"],
        validation_status="active",
    )
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login/json",
            json={"username": payload["username"], "password": "bad"},
        )
        assert resp.status_code == 401
    # 6th attempt -> locked out.
    resp = client.post(
        "/api/v1/auth/login/json",
        json={"username": payload["username"], "password": "bad"},
    )
    assert resp.status_code == 429, resp.text
    assert resp.json()["code"] == "AUTH_1004"


def test_login_pending_account_returns_account_pending(
    client: TestClient, db_session: Session
) -> None:
    payload = _signup_payload()
    user_crud.create_pending_user(
        db_session,
        username=payload["username"],
        password=payload["password"],
        role="Benevole",
        email=payload["email"],
    )
    resp = client.post(
        "/api/v1/auth/login/json",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "AUTH_1002"


def test_refresh_token_valid_returns_new_access(
    client: TestClient, db_session: Session
) -> None:
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
        "/api/v1/auth/login/json",
        json={"username": payload["username"], "password": payload["password"]},
    )
    refresh_token = login.json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_refresh_with_invalid_token_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "not.a.valid.token"}
    )
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["code"] in ("AUTH_1011", "AUTH_1013")


def test_me_without_token_returns_token_missing(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    # FastAPI's OAuth2PasswordBearer returns 401 when no token is provided.
    assert resp.status_code == 401
    body = resp.json()
    # Either TOKEN_MISSING or TOKEN_INVALID depending on the path taken.
    assert body["code"] in ("AUTH_1012", "AUTH_1011")
