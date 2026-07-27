"""Shared test fixtures (in-memory SQLite + auth helpers)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from typing import Any

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Speed up bcrypt for the test suite (rounds=4 instead of 12).
# This shaves ~10 minutes off the full run because every fixture creating a user
# pays the cost. Hashing remains genuine bcrypt — only the work factor changes.
_orig_gensalt = bcrypt.gensalt


def _fast_gensalt(rounds: int = 12, prefix: bytes = b"2b") -> bytes:  # noqa: ARG001
    return _orig_gensalt(rounds=4, prefix=prefix)


bcrypt.gensalt = _fast_gensalt  # type: ignore[assignment]

from app.core.security import create_access_token  # noqa: E402
from app.crud import user as user_crud  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

# Create tables once.
Base.metadata.create_all(bind=_engine)


def _override_get_db() -> Generator[Session, None, None]:
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# User fixtures (factories that create active accounts in DB)
# ---------------------------------------------------------------------------


_DEFAULT_PASSWORD = "Strong#Pass1"


def _unique_username(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _make_user(
    db: Session,
    *,
    role: str,
    validation_status: str = "active",
    prefix: str | None = None,
):
    username = _unique_username(prefix or role.lower().replace(" ", "_"))
    user = user_crud.create_user(
        db,
        username=username,
        password=_DEFAULT_PASSWORD,
        role=role,
        email=f"{username}@example.com",
        validation_status=validation_status,
    )
    # Stash the plaintext password on the instance so tests can log in with it.
    user._plain_password = _DEFAULT_PASSWORD  # type: ignore[attr-defined]
    return user


@pytest.fixture()
def super_admin_user(db_session: Session):
    """Active Super Admin user."""
    return _make_user(db_session, role="Super Admin", prefix="su")


@pytest.fixture()
def admin_benevoles_user(db_session: Session):
    """Active AdminBenevoles user."""
    return _make_user(db_session, role="AdminBenevoles", prefix="ab")


@pytest.fixture()
def compta_user(db_session: Session):
    """Active Compta user."""
    return _make_user(db_session, role="Compta", prefix="cp")


@pytest.fixture()
def benevole_user(db_session: Session):
    """Active Benevole user."""
    return _make_user(db_session, role="Benevole", prefix="be")


@pytest.fixture()
def pending_user(db_session: Session):
    """Pending Benevole (status='pending')."""
    return _make_user(
        db_session, role="Benevole", validation_status="pending", prefix="pd"
    )


# ---------------------------------------------------------------------------
# Auth header / pre-authenticated client factories
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_headers() -> Callable[[Any], dict[str, str]]:
    """Return a factory: ``auth_headers(user) -> {"Authorization": "Bearer <token>"}``.

    Builds the access token directly via :func:`create_access_token` so we
    don't need a round-trip through ``/auth/login``.
    """

    def _factory(user) -> dict[str, str]:
        token = create_access_token(user.id, user.role)
        return {"Authorization": f"Bearer {token}"}

    return _factory


@pytest.fixture()
def client_authenticated_as(
    auth_headers: Callable[[Any], dict[str, str]],
) -> Callable[[Any], TestClient]:
    """Return a factory yielding a TestClient pre-loaded with ``Authorization``."""

    def _factory(user) -> TestClient:
        c = TestClient(app)
        c.headers.update(auth_headers(user))
        return c

    return _factory


# ---------------------------------------------------------------------------
# Email mock — capture sent emails into a list instead of hitting SMTP.
# ---------------------------------------------------------------------------


class _SentEmail:
    """Minimal record for a captured email."""

    def __init__(
        self, subject: str, body: str, recipients: list[str], **extras: Any
    ) -> None:
        self.subject = subject
        self.body = body
        self.recipients = recipients
        self.extras = extras

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SentEmail to={self.recipients!r} subject={self.subject!r}>"


@pytest.fixture(autouse=True)
def captured_emails(monkeypatch: pytest.MonkeyPatch) -> list[_SentEmail]:
    """Patch ``app.services.email`` so every send is captured into a list.

    `autouse=True` to prevent any test from accidentally hitting a real SMTP
    server (and hanging on the network timeout).
    """
    sent: list[_SentEmail] = []

    async def _fake_send(subject, body, recipients, html=False):  # noqa: ANN001
        sent.append(_SentEmail(subject, body, list(recipients)))

    async def _fake_admin_invitation(*, email, invitation_url, expires_at):
        sent.append(
            _SentEmail(
                "Invitation administrateur",
                f"link={invitation_url} until={expires_at}",
                [email],
                kind="admin_invitation",
                invitation_url=invitation_url,
            )
        )

    async def _fake_status_change(*, recipient, subject, body):
        sent.append(_SentEmail(subject, body, [recipient], kind="status_change"))

    monkeypatch.setattr("app.services.email._send", _fake_send)
    monkeypatch.setattr(
        "app.services.email.send_admin_invitation", _fake_admin_invitation
    )
    monkeypatch.setattr(
        "app.services.email.send_status_change", _fake_status_change
    )
    return sent
