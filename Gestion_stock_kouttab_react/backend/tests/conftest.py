"""Shared test fixtures (in-memory SQLite + auth helpers)."""

from __future__ import annotations

import base64
import os
import uuid
from collections.abc import Callable, Generator
from typing import Any

# ---------------------------------------------------------------------------
# Environnement de test, pose AVANT tout import de l'application : `settings`
# est construit a l'import du premier module applicatif, et lit le `.env` du
# poste. Ce qui est defini ici l'emporte (pydantic-settings fait primer les
# variables d'environnement sur le fichier).
# ---------------------------------------------------------------------------

# AUCUN courriel ne part pendant les tests. Ce n'est pas une precaution
# theorique : le `.env` de developpement porte les identifiants SMTP reels de
# l'association, et la suite a arrose la boite de la comptabilite de fausses
# factures (« [Facture] EV(T) — Gala d'ete 2026 ») a chaque execution.
#
# La fixture `captured_emails` n'interceptait que `_send`, alors que le circuit
# comptable — celui qui envoie les PDF — passe par `_send_raw`. Le coupe-circuit
# `EMAIL_ENABLED` existait deja dans `services/email.py` mais rien ne l'armait
# ici : c'est desormais le cas, en amont de tout patch, pour qu'aucun chemin
# d'envoi present ou futur ne puisse joindre un vrai serveur.
os.environ["EMAIL_ENABLED"] = "false"

# Cle de chiffrement du RIB : sans elle, la moindre ecriture de RIB leve
# `CleAbsente`. Valeur fixe et sans secret — elle ne protege rien d'autre
# qu'une base SQLite en memoire.
os.environ.setdefault(
    "RIB_ENCRYPTION_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode()
)

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

from app.core.config import settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.crud import expense_category as category_crud  # noqa: E402
from app.crud import pole as pole_crud  # noqa: E402
from app.crud import user as user_crud  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

from app.api.v1.endpoints import buvette as buvette_endpoint  # noqa: E402
from app.api.v1.endpoints import expenses as expenses_endpoint  # noqa: E402
from app.api.v1.endpoints import invoices as invoices_endpoint  # noqa: E402
from app.db import session as db_session_module  # noqa: E402
from app.services import email as email_service  # noqa: E402
from app.services import outbox as outbox_service  # noqa: E402

# Reference vers la VRAIE fonction d'envoi, capturee avant tout patch : les
# tests qui verifient son comportement (coupe-circuit, TLS) en ont besoin,
# alors que la fixture `captured_emails` la remplace pour tous les autres.
_SEND_RAW_REEL = email_service._send_raw


_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

# Create tables once.
Base.metadata.create_all(bind=_engine)

# Le referentiel des poles est seede par la migration Alembic en production et
# par le lifespan au demarrage — mais ce dernier ouvre une SessionLocal pointant
# sur MySQL, pas sur la base de test. On amorce donc explicitement ici.
_bootstrap = sessionmaker(bind=_engine)()
try:
    pole_crud.ensure_default_poles(_bootstrap)
    category_crud.ensure_default_categories(_bootstrap)
finally:
    _bootstrap.close()


def _override_get_db() -> Generator[Session, None, None]:
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# `dependency_overrides` ne couvre que l'injection FastAPI. Les traitements
# differes (BackgroundTasks, cron de la file d'envoi) ouvrent leur propre
# `SessionLocal` parce que la session de la requete est deja fermee quand ils
# s'executent — ils viseraient donc la base reelle. On redirige toutes les
# references deja importees vers la base de test.
for _module in (
    db_session_module,
    outbox_service,
    invoices_endpoint,
    expenses_endpoint,
    buvette_endpoint,
):
    _module.SessionLocal = _TestingSessionLocal  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def first_pole():
    """Pole « Pôle événementiel » du referentiel de base.

    Cible explicitement un pole ``is_default`` : les tests peuvent en creer
    d'autres, et un tri par ordre ferait remonter un pole ad hoc en tete.
    """
    db = _TestingSessionLocal()
    try:
        poles = [p for p in pole_crud.list_poles(db) if p.is_default]
        assert poles, "le referentiel de poles par defaut n'a pas ete amorce"
        return poles[0]
    finally:
        db.close()


@pytest.fixture()
def local_pole():
    """Pole « Local » : le cas sans evenement, avec categorie obligatoire."""
    db = _TestingSessionLocal()
    try:
        poles = [p for p in pole_crud.list_poles(db) if not p.requiert_evenement]
        assert poles, "aucun pole sans evenement dans le referentiel de base"
        return poles[0]
    finally:
        db.close()


@pytest.fixture()
def first_category():
    """Premiere categorie de depense du referentiel de base (« Courses »)."""
    db = _TestingSessionLocal()
    try:
        categories = category_crud.list_categories(db)
        assert categories, "le referentiel de categories n'a pas ete amorce"
        return categories[0]
    finally:
        db.close()


@pytest.fixture()
def send_raw_reel():
    """La vraie ``_send_raw``, pour les tests qui verifient son comportement.

    Passer par la fonction du module rendrait ces tests inoperants : la
    fixture `captured_emails` l'a remplacee pour empecher tout envoi.
    """
    return _SEND_RAW_REEL


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


@pytest.fixture(autouse=True)
def _isolate_test_state() -> Generator[None, None, None]:
    """Remet la base a son etat initial entre chaque test.

    La suite partageait une base SQLite unique sans jamais rien nettoyer,
    contrairement a ce qu'annonce le CLAUDE.md. Les tests etaient donc
    sensibles a leur ordre d'execution — un pole cree par un test faisait par
    exemple echouer une assertion d'un autre.

    On vide les tables plutot que d'envelopper chaque test dans une transaction
    a annuler : les endpoints committent, les traitements differes ouvrent leur
    propre session, et une transaction externe partagee via ``StaticPool``
    donnerait des interactions difficiles a diagnostiquer. Le nettoyage
    explicite est plus lent de quelques millisecondes, mais previsible.

    Le limiteur de debit est desactive par defaut : ``TestClient`` presente
    toujours la meme IP, les quotas seraient consommes par l'accumulation des
    tests plutot que par le scenario teste.
    """
    limiter.enabled = False
    yield
    limiter.reset()
    limiter.enabled = settings.rate_limit_enabled

    db = _TestingSessionLocal()
    try:
        # Ordre inverse des dependances : les tables filles d'abord.
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        # Le referentiel de base fait partie de l'etat initial attendu.
        pole_crud.ensure_default_poles(db)
        category_crud.ensure_default_categories(db)
    finally:
        db.close()


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

    async def _fake_status_change(*, recipient, subject, body, auteur_email=None):
        sent.append(_SentEmail(subject, body, [recipient], kind="status_change"))

    async def _fake_send_raw(subject, body, recipients, *, html=False, attachments=None):  # noqa: ANN001
        """Envois du circuit comptable — ceux qui portent les PDF.

        Deuxieme barriere apres `EMAIL_ENABLED=false` : sans ce patch, un test
        rejoignait le vrai serveur SMTP, et la boite de la comptabilite recevait
        les fausses factures de la suite a chaque execution.
        """
        sent.append(_SentEmail(subject, body, list(recipients), kind="compta"))

    monkeypatch.setattr("app.services.email._send", _fake_send)
    monkeypatch.setattr("app.services.email._send_raw", _fake_send_raw)
    monkeypatch.setattr(
        "app.services.email.send_admin_invitation", _fake_admin_invitation
    )
    monkeypatch.setattr(
        "app.services.email.send_status_change", _fake_status_change
    )
    return sent
