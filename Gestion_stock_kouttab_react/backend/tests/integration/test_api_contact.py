"""Espace de contact.

Deux proprietes portent le module : l'auteur ne se declare pas lui-meme, et le
destinataire est resolu cote serveur. Les tests visent celles-la.
"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models import OutboundEmail


MESSAGE = {
    "destinataire": "compta",
    "sujet": "Ma note de frais de juin",
    "message": "Assalamu alaykum, ma note du 12 juin est toujours en attente.",
}


def _dernier_envoi(db_session) -> OutboundEmail:
    return db_session.execute(
        select(OutboundEmail).order_by(OutboundEmail.id.desc())
    ).scalars().first()


def test_le_message_part_en_file_et_non_en_direct(
    client_authenticated_as, benevole_user, db_session
):
    """L'envoi passe par la file.

    Le serveur de messagerie tombe ; une question posee ne doit pas disparaitre
    avec lui, alors que le demandeur, lui, a vu son message partir.
    """
    reponse = client_authenticated_as(benevole_user).post("/api/v1/contact", json=MESSAGE)
    assert reponse.status_code == 200
    assert "comptabilite" in reponse.json()["message"]

    envoi = _dernier_envoi(db_session)
    assert envoi.kind == "contact"
    assert envoi.status == "pending"
    assert "Ma note de frais de juin" in envoi.subject


def test_l_identite_de_l_auteur_vient_du_compte(
    client_authenticated_as, benevole_user, db_session
):
    """Un champ « votre nom » se remplit de n'importe quoi.

    Le corps porte le nom, l'identifiant et l'adresse du compte connecte —
    sinon la reponse ne saurait ou aller, et la question resterait en attente.
    """
    client_authenticated_as(benevole_user).post("/api/v1/contact", json=MESSAGE)

    corps = _dernier_envoi(db_session).body
    assert benevole_user.username in corps
    assert benevole_user.email in corps


def test_le_demandeur_ne_choisit_pas_l_adresse(client_authenticated_as, benevole_user):
    """Sans cela, l'endpoint serait un relais ouvert.

    N'importe qui pourrait faire ecrire l'institut a n'importe quelle adresse.
    Le formulaire n'envoie qu'un mot-cle, et tout le reste est refuse.
    """
    reponse = client_authenticated_as(benevole_user).post(
        "/api/v1/contact",
        json={**MESSAGE, "destinataire": "attaquant@exemple.test"},
    )
    assert reponse.status_code == 422


def test_message_vers_l_administration(
    client_authenticated_as, benevole_user, super_admin_user, db_session
):
    client_authenticated_as(benevole_user).post(
        "/api/v1/contact", json={**MESSAGE, "destinataire": "admin"}
    )

    destinataires = json.loads(_dernier_envoi(db_session).recipients)
    assert super_admin_user.email in destinataires


def test_un_visiteur_anonyme_ne_peut_rien_envoyer(client):
    assert client.post("/api/v1/contact", json=MESSAGE).status_code == 401
