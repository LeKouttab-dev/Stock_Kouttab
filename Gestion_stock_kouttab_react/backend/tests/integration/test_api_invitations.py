"""End-to-end tests for /invitations and admin-setup."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.crud import invitation as invitation_crud


pytestmark = pytest.mark.integration


def _email() -> str:
    return f"invitee_{uuid.uuid4().hex[:8]}@example.com"


def test_create_invitation_as_super_admin_returns_token(
    client: TestClient, super_admin_user, auth_headers, captured_emails
) -> None:
    email = _email()
    resp = client.post(
        "/api/v1/invitations",
        json={"email": email},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == email
    assert body["token"]


def test_create_invitation_as_benevole_forbidden(
    client: TestClient, benevole_user, auth_headers
) -> None:
    resp = client.post(
        "/api/v1/invitations",
        json={"email": _email()},
        headers=auth_headers(benevole_user),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "PERM_2002"


def test_validate_invitation_when_valid(
    client: TestClient, super_admin_user, auth_headers, captured_emails
) -> None:
    email = _email()
    create = client.post(
        "/api/v1/invitations",
        json={"email": email},
        headers=auth_headers(super_admin_user),
    )
    token = create.json()["token"]
    resp = client.get(
        f"/api/v1/auth/validate-invitation?token={token}&email={email}"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True


def test_validate_invitation_when_expired(
    client: TestClient, super_admin_user, auth_headers, captured_emails, db_session
) -> None:
    email = _email()
    create = client.post(
        "/api/v1/invitations",
        json={"email": email},
        headers=auth_headers(super_admin_user),
    )
    token = create.json()["token"]
    # Force expiration in DB.
    inv = invitation_crud.get_by_email(db_session, email)
    inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    resp = client.get(
        f"/api/v1/auth/validate-invitation?token={token}&email={email}"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["valid"] is False


def test_admin_setup_with_valid_token_creates_super_admin(
    client: TestClient, super_admin_user, auth_headers, captured_emails
) -> None:
    email = _email()
    create = client.post(
        "/api/v1/invitations",
        json={"email": email},
        headers=auth_headers(super_admin_user),
    )
    token = create.json()["token"]
    new_username = f"sa_{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/auth/admin-setup",
        json={
            "email": email,
            "token": token,
            "username": new_username,
            "password": "Strong#Pass1",
            "nom": "Admin",
            "prenom": "New",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["role"] == "Super Admin"
    assert body["user"]["username"] == new_username
