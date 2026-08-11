"""Mot de passe oublie : emission, usage unique, et absence de fuite."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.crud import password_reset as reset_crud
from app.db.models import PasswordReset


pytestmark = pytest.mark.integration


def _demander(client: TestClient, identifiant: str):
    return client.post("/api/v1/auth/forgot-password", json={"identifiant": identifiant})


def test_forgot_password_answers_the_same_for_an_unknown_account(
    client: TestClient, benevole_user
) -> None:
    """La reponse ne doit pas reveler si un compte existe.

    Distinguer les cas transformerait l'endpoint en oracle : n'importe qui
    pourrait verifier si une adresse est enregistree dans l'association.
    """
    connu = _demander(client, benevole_user.username)
    inconnu = _demander(client, "compte-qui-nexiste-pas")

    assert connu.status_code == 200
    assert inconnu.status_code == 200
    assert connu.json() == inconnu.json()


def test_forgot_password_emits_a_token(client: TestClient, benevole_user, db_session) -> None:
    assert _demander(client, benevole_user.username).status_code == 200

    lignes = db_session.query(PasswordReset).filter_by(id_user=benevole_user.id).all()
    assert len(lignes) == 1
    # Le jeton lui-meme n'est jamais stocke, seulement son empreinte.
    assert len(lignes[0].token_hash) == 64
    assert lignes[0].used_at is None


def test_a_new_request_invalidates_the_previous_link(
    client: TestClient, benevole_user, db_session
) -> None:
    """Deux demandes ne doivent pas laisser deux liens actifs."""
    _demander(client, benevole_user.username)
    _demander(client, benevole_user.username)

    lignes = db_session.query(PasswordReset).filter_by(id_user=benevole_user.id).all()
    actifs = [r for r in lignes if r.used_at is None]
    assert len(lignes) == 2
    assert len(actifs) == 1


def test_reset_changes_the_password_and_consumes_the_token(
    client: TestClient, benevole_user, db_session
) -> None:
    token = reset_crud.create_reset_token(db_session, benevole_user)

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "Nouveau#Pass1"},
    )
    assert resp.status_code == 200, resp.text

    connexion = client.post(
        "/api/v1/auth/login/json",
        json={"username": benevole_user.username, "password": "Nouveau#Pass1"},
    )
    assert connexion.status_code == 200, connexion.text

    # Rejouer le meme lien doit echouer : usage unique.
    rejeu = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "Encore#Autre2"},
    )
    assert rejeu.status_code >= 400


def test_an_expired_token_is_refused(client: TestClient, benevole_user, db_session) -> None:
    token = reset_crud.create_reset_token(db_session, benevole_user)
    ligne = db_session.query(PasswordReset).filter_by(id_user=benevole_user.id).one()
    ligne.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "Nouveau#Pass1"},
    )
    assert resp.status_code >= 400


def test_reset_refuses_a_weak_password(client: TestClient, benevole_user, db_session) -> None:
    token = reset_crud.create_reset_token(db_session, benevole_user)

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "azertyui"},
    )
    assert resp.status_code >= 400

    # Le jeton n'est pas consomme par un refus : l'utilisateur doit pouvoir
    # reessayer sans redemander un courriel.
    ligne = db_session.query(PasswordReset).filter_by(id_user=benevole_user.id).one()
    assert ligne.used_at is None


def test_validate_endpoint_reports_token_state(
    client: TestClient, benevole_user, db_session
) -> None:
    token = reset_crud.create_reset_token(db_session, benevole_user)

    bon = client.get("/api/v1/auth/reset-password/validate", params={"token": token})
    assert bon.status_code == 200 and bon.json()["valid"] is True

    mauvais = client.get(
        "/api/v1/auth/reset-password/validate", params={"token": "x" * 40}
    )
    assert mauvais.status_code == 200 and mauvais.json()["valid"] is False


def test_a_pending_account_gets_no_reset_link(
    client: TestClient, db_session, pending_user
) -> None:
    """Un compte non valide ne doit pas pouvoir se donner un mot de passe."""
    assert _demander(client, pending_user.username).status_code == 200
    assert db_session.query(PasswordReset).filter_by(id_user=pending_user.id).count() == 0
