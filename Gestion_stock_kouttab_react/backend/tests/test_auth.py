"""Smoke tests for the auth flow."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def test_signup_creates_pending_user(client: TestClient, db_session: Session) -> None:
    payload = _signup_payload()
    response = client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == payload["username"]
    assert body["validation_status"] == "pending"


def test_login_requires_active_account(client: TestClient, db_session: Session) -> None:
    payload = _signup_payload()
    client.post("/api/v1/auth/signup", json=payload)
    # User is pending -> login should fail with 403.
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": payload["username"], "password": payload["password"]},
    )
    assert resp.status_code == 403


def test_login_then_me(client: TestClient, db_session: Session) -> None:
    # Manually create an active user via the CRUD layer.
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
        data={"username": payload["username"], "password": payload["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == payload["username"]
