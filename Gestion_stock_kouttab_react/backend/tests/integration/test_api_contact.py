"""Espace de contact : fils de discussion.

Le formulaire précédent envoyait un courriel et n'en gardait rien — la réponse
partait de la boîte du comptable, hors de l'application. Ces tests portent sur ce
que le fil apporte : la conversation reste, elle a un état, et chaque partie voit
ce qui l'attend.

Deux propriétés de sécurité héritées du formulaire restent vérifiées : l'auteur
ne se déclare pas, et le destinataire est un mot-clé, jamais une adresse.
"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models import Conversation, OutboundEmail


QUESTION = {
    "destinataire": "compta",
    "sujet": "Ma note de frais de juin",
    "message": "Assalamu alaykum, ma note du 12 juin est toujours en attente.",
}


def _ouvrir(client, **surcharges):
    return client.post("/api/v1/conversations", json={**QUESTION, **surcharges})


def _dernier_envoi(db_session) -> OutboundEmail:
    return db_session.execute(
        select(OutboundEmail).order_by(OutboundEmail.id.desc())
    ).scalars().first()


# --- Ouverture ---------------------------------------------------------------


def test_ouvrir_un_fil_le_conserve(client_authenticated_as, benevole_user, db_session):
    """Ce que le formulaire ne faisait pas : garder la question."""
    reponse = _ouvrir(client_authenticated_as(benevole_user))
    assert reponse.status_code == 200

    fil = reponse.json()
    assert fil["statut"] == "ouverte"
    assert fil["nombre_messages"] == 1
    assert fil["messages"][0]["corps"] == QUESTION["message"]
    assert fil["messages"][0]["de_l_equipe"] is False

    assert db_session.execute(select(Conversation)).scalars().all()


def test_le_courriel_previent_sans_porter_la_conversation(
    client_authenticated_as, benevole_user, db_session
):
    """La notification part toujours, mais le fil ne dépend plus d'elle.

    Un serveur de messagerie en panne retarde un avis ; il ne fait plus perdre
    la question.
    """
    _ouvrir(client_authenticated_as(benevole_user))

    envoi = _dernier_envoi(db_session)
    assert envoi.kind == "conversation"
    assert QUESTION["sujet"] in envoi.subject
    assert QUESTION["message"] in envoi.body


def test_l_identite_de_l_auteur_vient_du_compte(
    client_authenticated_as, benevole_user, db_session
):
    """Un champ « votre nom » se remplit de n'importe quoi."""
    reponse = _ouvrir(client_authenticated_as(benevole_user))
    assert reponse.json()["messages"][0]["auteur_nom"] == benevole_user.full_name
    assert benevole_user.full_name in _dernier_envoi(db_session).body


def test_le_demandeur_ne_choisit_pas_l_adresse(client_authenticated_as, benevole_user):
    """Sans cela, l'endpoint serait un relais de courriel ouvert."""
    reponse = _ouvrir(client_authenticated_as(benevole_user), destinataire="attaquant@test.fr")
    assert reponse.status_code == 422


def test_un_visiteur_anonyme_ne_peut_rien_ouvrir(client):
    assert client.post("/api/v1/conversations", json=QUESTION).status_code == 401


# --- Le fil ------------------------------------------------------------------


def test_la_reponse_de_l_equipe_fait_avancer_le_fil(
    client_authenticated_as, benevole_user, compta_user
):
    fil = _ouvrir(client_authenticated_as(benevole_user)).json()

    apres = client_authenticated_as(compta_user).post(
        f"/api/v1/conversations/{fil['id']}/messages",
        json={"corps": "Elle part au prochain virement."},
    )
    assert apres.status_code == 200

    corps = apres.json()
    assert corps["statut"] == "en_cours"
    # Le fil quitte la pile de l'équipe et allume la pastille du demandeur.
    assert corps["attente_equipe"] is False
    assert corps["non_lu_demandeur"] is True
    assert corps["messages"][-1]["de_l_equipe"] is True


def test_ouvrir_le_fil_eteint_sa_pastille(client_authenticated_as, benevole_user, compta_user):
    fil = _ouvrir(client_authenticated_as(benevole_user)).json()
    client_authenticated_as(compta_user).post(
        f"/api/v1/conversations/{fil['id']}/messages", json={"corps": "C'est noté."}
    )

    client = client_authenticated_as(benevole_user)
    lu = client.get(f"/api/v1/conversations/{fil['id']}").json()
    assert lu["non_lu_demandeur"] is False

    # ...et pas seulement dans la réponse : la liste le confirme.
    liste = client.get("/api/v1/conversations").json()
    assert liste[0]["a_signaler"] is False


def test_relancer_un_fil_traite_le_rouvre(client_authenticated_as, benevole_user, compta_user):
    """Sinon une précision demandée après coup ne serait jamais lue : le fil est
    rangé, plus personne ne le regarde."""
    fil = _ouvrir(client_authenticated_as(benevole_user)).json()
    compta = client_authenticated_as(compta_user)
    compta.patch(f"/api/v1/conversations/{fil['id']}/statut", json={"statut": "traitee"})

    relance = client_authenticated_as(benevole_user).post(
        f"/api/v1/conversations/{fil['id']}/messages", json={"corps": "Une dernière chose…"}
    )
    assert relance.json()["statut"] == "en_cours"
    assert relance.json()["attente_equipe"] is True


def test_la_cloture_est_signalee_au_demandeur(
    client_authenticated_as, benevole_user, compta_user
):
    """Sans quoi il attendrait une réponse qui ne viendra plus."""
    fil = _ouvrir(client_authenticated_as(benevole_user)).json()
    close = client_authenticated_as(compta_user).patch(
        f"/api/v1/conversations/{fil['id']}/statut", json={"statut": "traitee"}
    )
    assert close.json()["statut"] == "traitee"
    assert close.json()["non_lu_demandeur"] is True


# --- Qui voit quoi -----------------------------------------------------------


def test_un_tiers_ne_lit_pas_le_fil_d_un_autre(
    client_authenticated_as, benevole_user, admin_benevoles_user
):
    """`AdminBenevoles` n'est ni le demandeur ni destinataire : une question de
    remboursement peut porter sur des montants, parfois sur un différend."""
    fil = _ouvrir(client_authenticated_as(benevole_user)).json()
    reponse = client_authenticated_as(admin_benevoles_user).get(
        f"/api/v1/conversations/{fil['id']}"
    )
    assert reponse.status_code == 403


def test_la_compta_ne_voit_pas_les_fils_de_l_administration(
    client_authenticated_as, benevole_user, compta_user
):
    _ouvrir(client_authenticated_as(benevole_user), destinataire="admin")

    boite = client_authenticated_as(compta_user).get("/api/v1/conversations/equipe").json()
    assert boite == []


def test_le_super_admin_voit_les_deux_boites(
    client_authenticated_as, benevole_user, super_admin_user
):
    """Il est le recours quand une question a été mal adressée."""
    client = client_authenticated_as(benevole_user)
    _ouvrir(client, destinataire="admin", sujet="Mon compte est bloqué")
    _ouvrir(client, destinataire="compta")

    boite = client_authenticated_as(super_admin_user).get("/api/v1/conversations/equipe").json()
    assert len(boite) == 2


def test_transferer_un_fil_mal_adresse(
    client_authenticated_as, benevole_user, super_admin_user, compta_user
):
    fil = _ouvrir(client_authenticated_as(benevole_user), destinataire="admin").json()

    client_authenticated_as(super_admin_user).patch(
        f"/api/v1/conversations/{fil['id']}/destinataire", json={"destinataire": "compta"}
    )

    boite = client_authenticated_as(compta_user).get("/api/v1/conversations/equipe").json()
    assert [c["id"] for c in boite] == [fil["id"]]


# --- Pastilles ---------------------------------------------------------------


def test_les_compteurs_suivent_le_fil(client_authenticated_as, benevole_user, compta_user):
    benevole = client_authenticated_as(benevole_user)
    compta = client_authenticated_as(compta_user)

    fil = _ouvrir(benevole).json()
    assert compta.get("/api/v1/notifications/summary").json()["conversations_a_traiter"] == 1
    assert benevole.get("/api/v1/notifications/summary").json()["conversations_non_lues"] == 0

    compta.post(f"/api/v1/conversations/{fil['id']}/messages", json={"corps": "Réglé."})
    assert compta.get("/api/v1/notifications/summary").json()["conversations_a_traiter"] == 0
    assert benevole.get("/api/v1/notifications/summary").json()["conversations_non_lues"] == 1


def test_un_benevole_n_apprend_rien_des_fils_des_autres(
    client_authenticated_as, benevole_user, admin_benevoles_user
):
    _ouvrir(client_authenticated_as(benevole_user))
    resume = client_authenticated_as(admin_benevoles_user).get(
        "/api/v1/notifications/summary"
    ).json()
    assert resume["conversations_a_traiter"] == 0


def test_l_equipe_repond_a_son_tour_dans_la_notification(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """La réponse est reprise dans le courriel : obliger à se connecter pour
    savoir de quoi il retourne ferait manquer les demandes urgentes."""
    fil = _ouvrir(client_authenticated_as(benevole_user)).json()
    client_authenticated_as(compta_user).post(
        f"/api/v1/conversations/{fil['id']}/messages",
        json={"corps": "Le virement part vendredi."},
    )

    envoi = _dernier_envoi(db_session)
    assert json.loads(envoi.recipients) == [benevole_user.email]
    assert "Le virement part vendredi." in envoi.body
