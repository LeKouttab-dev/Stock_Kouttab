"""Un envoi désactivé ne doit jamais s'afficher « Envoyé ».

Le 2026-08-13, la production tournait avec `EMAIL_ENABLED=false`. L'écran des
envois comptables affichait **tout en vert**, et rien ne partait : ni les pièces
au comptable, ni les changements de statut, ni les relances de justificatifs.

La cause tenait en deux lignes. `_send_raw` sortait en silence quand le drapeau
était faux — le commentaire d'alors disait « l'envoi est considéré comme réussi,
pour que le circuit comptable se déroule jusqu'au bout » — et `outbox._deliver`
interprétait ce retour comme une livraison.

L'intention de départ était bonne : en développement, on ne veut arroser
personne. Mais « ne rien envoyer » et « avoir envoyé » ne peuvent pas se dire de
la même façon, sinon une production muette est indiscernable d'une production
saine. C'est ce que ces tests figent.

Le drapeau n'empêche **pas** le démarrage en production : un refus de démarrage
couperait toute l'application, alors que seul le courriel est en cause — et le
couperait précisément au déploiement qui apporte le correctif. On le rend
visible, on ne l'aggrave pas.
"""

from __future__ import annotations

import pytest

# Capturées à l'import, donc AVANT que la fixture `captured_emails` ne les
# remplace : ce sont les vraies fonctions qu'on éprouve ici, pas leurs doublures.
from app.services.email import _send as ENVOI_TOLERANT
from app.services.email import _send_raw as ENVOI_REEL

from app.core.exceptions import AppException
from app.services import outbox


pytestmark = pytest.mark.anyio


async def test_un_envoi_desactive_leve_au_lieu_de_se_taire(captured_emails):
    with pytest.raises(AppException) as erreur:
        await ENVOI_REEL("[Facture] Essai", "corps", ["comptabilite@example.test"])

    # Le motif doit nommer la variable : c'est ce qui transforme un mystère de
    # trois semaines en correction de trente secondes.
    assert "EMAIL_ENABLED" in erreur.value.message
    # Refuser, sans expédier pour autant : le coupe-circuit reste armé.
    assert captured_emails == []


async def test_la_file_marque_l_echec_et_non_l_envoi(db_session, monkeypatch):
    """Le cœur de la panne : la ligne passait à « Envoyé » sans rien envoyer."""
    monkeypatch.setattr("app.services.email._send_raw", ENVOI_REEL)

    ligne = outbox.enqueue(
        db_session,
        kind="facture",
        entity_type="invoice",
        entity_id=1,
        recipients=["comptabilite@example.test"],
        subject="[Facture] Essai",
        body="corps",
    )

    assert await outbox._deliver(db_session, ligne) is False

    db_session.refresh(ligne)
    assert ligne.status == outbox.STATUS_FAILED
    assert ligne.sent_at is None
    assert "EMAIL_ENABLED" in (ligne.last_error or "")


async def test_l_ecran_d_administration_montre_l_echec(
    client_authenticated_as, compta_user, db_session, monkeypatch
):
    """Ce que le comptable voit — la panne était invisible parce que cet écran
    disait « Envoyé »."""
    monkeypatch.setattr("app.services.email._send_raw", ENVOI_REEL)

    ligne = outbox.enqueue(
        db_session,
        kind="facture",
        entity_type="invoice",
        entity_id=2,
        recipients=["comptabilite@example.test"],
        subject="[Facture] Essai",
        body="corps",
    )
    await outbox._deliver(db_session, ligne)

    lignes = client_authenticated_as(compta_user).get("/api/v1/admin/outbound-emails").json()
    vue = next(row for row in lignes if row["id"] == ligne.id)
    assert vue["status"] == outbox.STATUS_FAILED
    assert "EMAIL_ENABLED" in (vue["last_error"] or "")


def test_l_etat_des_envois_est_consultable(client_authenticated_as, compta_user):
    """Pour que l'écran le dise **avant** qu'un envoi n'échoue.

    Une file vide et un drapeau baissé se ressemblent : sans ce signal, il faut
    déposer une pièce pour découvrir que rien ne part.
    """
    reponse = client_authenticated_as(compta_user).get("/api/v1/admin/outbound-emails/etat")
    assert reponse.status_code == 200

    etat = reponse.json()
    # `email_enabled` est faux partout : la suite l'impose avant les imports.
    assert etat["email_enabled"] is False
    # Le reste ne s'affirme PAS en dur : sa valeur depend de la configuration de
    # la machine. Ce test l'a fait, et il a rougi la CI pendant neuf commits —
    # il passait en local, ou le `.env` porte un SMTP, et echouait sur le
    # runner, qui n'en a aucun. Un test ne doit pas dependre de son
    # environnement ; le contrat verifiable est la FORME de la reponse.
    assert isinstance(etat["smtp_configure"], bool)
    assert isinstance(etat["destinataires_compta"], list)
    assert isinstance(etat["en_attente"], int)
    assert isinstance(etat["en_echec"], int)


def test_l_etat_reflete_la_configuration(client_authenticated_as, compta_user, monkeypatch):
    """Le contrat reel : l'ecran dit ce qui est configure, quoi qu'il en soit.

    On maitrise l'entree plutot que de subir celle de la machine.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_user", "")
    etat = client_authenticated_as(compta_user).get(
        "/api/v1/admin/outbound-emails/etat"
    ).json()
    assert etat["smtp_configure"] is False

    monkeypatch.setattr(settings, "smtp_host", "mail.exemple.test")
    monkeypatch.setattr(settings, "smtp_user", "no-reply@exemple.test")
    etat = client_authenticated_as(compta_user).get(
        "/api/v1/admin/outbound-emails/etat"
    ).json()
    assert etat["smtp_configure"] is True


def test_l_etat_reste_ferme_aux_benevoles(client_authenticated_as, benevole_user):
    """Il expose les adresses de la comptabilité et l'état du serveur d'envoi."""
    reponse = client_authenticated_as(benevole_user).get("/api/v1/admin/outbound-emails/etat")
    assert reponse.status_code == 403


async def test_les_notifications_best_effort_restent_tolerantes(captured_emails):
    """`_send` ne doit pas se mettre à faire échouer les requêtes des usagers.

    Un changement de statut qui n'arrive pas est ennuyeux ; une validation de
    note qui renvoie une 500 parce que le courriel est coupé est pire. La
    différence entre les deux chemins d'envoi est la raison d'être de `_send`.
    """
    # Pas de `pytest.raises` : l'appel doit simplement rendre la main. Il
    # traverse la doublure de `_send_raw` posée par la fixture, ce qui suffit
    # — c'est l'absence d'exception qu'on éprouve ici, pas l'envoi.
    await ENVOI_TOLERANT("Sujet", "corps", ["benevole@example.test"])
