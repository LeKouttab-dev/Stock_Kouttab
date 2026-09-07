"""Accepter une demande de compte prévient le demandeur.

La demande d'inscription prévenait les Super Admins ; leur réponse ne prévenait
personne. Le demandeur restait devant un écran de connexion qui refusait son mot
de passe — le compte n'était plus `pending`, mais rien ne le lui disait, et le
seul moyen de l'apprendre était de réessayer au hasard. C'est arrivé à un
bénévole validé le 2026-09-07.

L'avis passe par la file, comme les courriels de statut : c'est le seul message
que reçoit le demandeur, et un SMTP coupé le ferait disparaître sans trace.
"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.core.config import settings
from app.db.models import OutboundEmail


def _valider(client, user_id, statut="active"):
    return client.patch(
        f"/api/v1/users/{user_id}/validate", json={"validation_status": statut}
    )


def _envois(db_session, user_id):
    return list(
        db_session.execute(
            select(OutboundEmail).where(
                OutboundEmail.kind == "compte_valide",
                OutboundEmail.entity_id == user_id,
            )
        )
        .scalars()
        .all()
    )


def test_le_demandeur_est_prevenu_que_son_compte_est_ouvert(
    client_authenticated_as, super_admin_user, pending_user, db_session
):
    assert _valider(client_authenticated_as(super_admin_user), pending_user.id).status_code == 200

    envois = _envois(db_session, pending_user.id)
    assert len(envois) == 1
    assert json.loads(envois[0].recipients) == [pending_user.email]
    assert pending_user.username in envois[0].body


def test_l_avis_porte_le_lien_de_connexion(
    client_authenticated_as, super_admin_user, pending_user, db_session
):
    """Sans adresse, le demandeur doit retrouver le domaine de mémoire — c'est
    exactement ce qu'on lui demandait de faire jusqu'ici."""
    _valider(client_authenticated_as(super_admin_user), pending_user.id)

    corps = _envois(db_session, pending_user.id)[0].body
    assert f"{settings.frontend_url.rstrip('/')}/login" in corps


def test_un_benevole_frais_est_renvoye_vers_l_outil_de_gestion(
    client_authenticated_as, super_admin_user, pending_user, db_session
):
    """Il n'a pas de mot de passe stock : l'écran de connexion serait une
    impasse (cf. services/liens)."""
    pending_user.role = "BenevoleFrais"
    db_session.commit()

    _valider(client_authenticated_as(super_admin_user), pending_user.id)

    corps = _envois(db_session, pending_user.id)[0].body
    assert f"{settings.gestion_url.rstrip('/')}/benevole" in corps
    assert f"{settings.frontend_url.rstrip('/')}/login" not in corps


def test_valider_deux_fois_n_envoie_qu_un_avis(
    client_authenticated_as, super_admin_user, pending_user, db_session
):
    """Rouvrir la fiche d'un compte déjà actif ne doit pas lui réannoncer une
    validation vieille de trois semaines."""
    client = client_authenticated_as(super_admin_user)
    _valider(client, pending_user.id)
    _valider(client, pending_user.id)

    assert len(_envois(db_session, pending_user.id)) == 1


def test_un_compte_sans_adresse_ne_bloque_pas_la_validation(
    client_authenticated_as, super_admin_user, pending_user, db_session
):
    """L'adresse est facultative à l'inscription : son absence ne doit pas
    faire échouer la validation, seulement priver de l'avis."""
    pending_user.email = None
    db_session.commit()

    reponse = _valider(client_authenticated_as(super_admin_user), pending_user.id)

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["validation_status"] == "active"
    assert _envois(db_session, pending_user.id) == []


def test_un_refus_n_envoie_rien(
    client_authenticated_as, super_admin_user, pending_user, db_session
):
    """Le refus supprime le compte (comportement hérité). Lui écrire « votre
    compte est actif » serait faux ; lui écrire un refus n'a pas été demandé."""
    user_id = pending_user.id
    _valider(client_authenticated_as(super_admin_user), user_id, statut="rejected")

    assert _envois(db_session, user_id) == []
