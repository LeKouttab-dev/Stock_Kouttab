"""Le déposant est prévenu dans l'application, pas seulement par courriel.

Un commentaire de la comptabilité n'allumait rien : il fallait ouvrir « Mes
demandes » et repérer soi-même l'encart bleu. Le seul canal était un courriel
« best-effort » — journalisé en cas d'échec, jamais repris — et il n'arrivait
pas du tout quand `EMAIL_ENABLED` était tombé.

Deux corrections, éprouvées ici :

- une **pastille** allumée par toute décision de la comptabilité, statut *ou*
  commentaire, éteinte quand le déposant ouvre sa liste ;
- le courriel passe par la **file**, qui gère les reprises, et ne ment plus sur
  ce qu'il annonce.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.crud import expense as expense_crud
from app.db.models import Expense, OutboundEmail


def _note(db_session, user, statut="En attente"):
    note = expense_crud.create_expense(
        db_session,
        user_id=user.id,
        date_depense=date(2026, 8, 12),
        rattachement="Frais généraux",
        fournisseur="Action",
        nature_charge="Courses",
        montant=Decimal("10.37"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
    )
    note.status = statut
    db_session.commit()
    return note


def _valider(client, note_id, **payload):
    return client.patch(f"/api/v1/expenses/{note_id}/validate", json=payload)


def _envois(db_session, entity_type):
    return db_session.execute(
        select(OutboundEmail)
        .where(OutboundEmail.entity_type == entity_type)
        .order_by(OutboundEmail.id.desc())
    ).scalars().all()


# --- La pastille -------------------------------------------------------------


def test_un_commentaire_seul_allume_la_pastille(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """C'est le cas signalé : le commentaire porte souvent la demande de
    correction, et il n'allumait rien du tout."""
    note = _note(db_session, benevole_user, statut="Approuvée")

    _valider(
        client_authenticated_as(compta_user),
        note.id,
        status="Approuvée",
        commentaires_compta="Merci de préciser le nombre de repas.",
    )

    resume = client_authenticated_as(benevole_user).get(
        "/api/v1/notifications/summary"
    ).json()
    assert resume["notes_suivies"] == 1


def test_ouvrir_ses_demandes_eteint_la_pastille(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note = _note(db_session, benevole_user)
    _valider(
        client_authenticated_as(compta_user),
        note.id,
        status="Approuvée",
        commentaires_compta="",
    )

    benevole = client_authenticated_as(benevole_user)

    # La liste montre encore la note signalée : éteindre AVANT de sérialiser
    # priverait l'écran du seul signal qu'il devait afficher.
    mes_notes = benevole.get("/api/v1/expenses/me").json()
    assert next(n for n in mes_notes if n["id"] == note.id)["non_lu_demandeur"] is True

    resume = benevole.get("/api/v1/notifications/summary").json()
    assert resume["notes_suivies"] == 0


def test_la_pastille_ne_regarde_que_ses_propres_notes(
    client_authenticated_as, benevole_user, compta_user, admin_benevoles_user, db_session
):
    note = _note(db_session, benevole_user)
    _valider(
        client_authenticated_as(compta_user), note.id, status="Approuvée", commentaires_compta=""
    )

    resume = client_authenticated_as(admin_benevoles_user).get(
        "/api/v1/notifications/summary"
    ).json()
    assert resume["notes_suivies"] == 0


def test_une_decision_sans_changement_n_allume_rien(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Réenregistrer le même statut avec le même commentaire n'apprend rien :
    allumer une pastille pour cela ferait prendre le signal pour du bruit."""
    note = _note(db_session, benevole_user, statut="Approuvée")
    compta = client_authenticated_as(compta_user)
    _valider(compta, note.id, status="Approuvée", commentaires_compta="Vu")
    client_authenticated_as(benevole_user).get("/api/v1/expenses/me")

    _valider(compta, note.id, status="Approuvée", commentaires_compta="Vu")

    db_session.expire_all()
    ligne = db_session.execute(select(Expense).where(Expense.id == note.id)).scalar_one()
    assert ligne.non_lu_demandeur is False


# --- Le courriel -------------------------------------------------------------


def test_le_courriel_de_statut_passe_par_la_file(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Il partait en « best-effort » : un SMTP coupé le faisait disparaître sans
    trace, alors que c'est le seul avis que reçoit le déposant."""
    note = _note(db_session, benevole_user)

    _valider(
        client_authenticated_as(compta_user), note.id, status="Approuvée", commentaires_compta=""
    )

    envoi = _envois(db_session, "expense")[0]
    assert json.loads(envoi.recipients) == [benevole_user.email]
    assert "Approuvée" in envoi.subject


def test_le_courriel_ne_ment_plus_sur_un_commentaire_seul(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Il annonçait « votre note a été approuvée » quand seul le commentaire
    changeait, avec un objet rejouant le statut inchangé."""
    note = _note(db_session, benevole_user, statut="Approuvée")

    _valider(
        client_authenticated_as(compta_user),
        note.id,
        status="Approuvée",
        commentaires_compta="Précisez le nombre de repas.",
    )

    envoi = _envois(db_session, "expense")[0]
    assert "message de la comptabilite" in envoi.subject
    assert "n'a pas change" in envoi.body
    assert "a ete approuvee" not in envoi.body


def test_le_courriel_annonce_bien_un_vrai_changement(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note = _note(db_session, benevole_user)

    _valider(
        client_authenticated_as(compta_user), note.id, status="Approuvée", commentaires_compta=""
    )

    envoi = _envois(db_session, "expense")[0]
    assert "a ete approuvee" in envoi.body


# --- Les factures ------------------------------------------------------------


def test_une_facture_refusee_porte_enfin_son_motif(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
    """La colonne n'existait pas : le déposant apprenait le refus sans savoir
    quoi corriger."""
    from app.crud import invoice as invoice_crud

    facture = invoice_crud.create_invoice(
        db_session,
        user_id=benevole_user.id,
        commentaire=None,
        date_depot=date(2026, 8, 12),
        id_pole=local_pole.id,
        pole=local_pole.nom,
        id_categorie=first_category.id,
        categorie=first_category.nom,
        fournisseur="Action",
    )

    reponse = client_authenticated_as(compta_user).patch(
        f"/api/v1/invoices/{facture.id}/status",
        json={"status": "Refusée", "commentaires_compta": "Pièce illisible."},
    )
    assert reponse.status_code == 200
    assert reponse.json()["commentaires_compta"] == "Pièce illisible."

    envoi = _envois(db_session, "invoice")[0]
    assert "Pièce illisible." in envoi.body
    # Et ce qu'il reste à faire, que l'ancien courriel n'expliquait jamais.
    assert "nouvelle piece corrigee" in envoi.body

    resume = client_authenticated_as(benevole_user).get(
        "/api/v1/notifications/summary"
    ).json()
    assert resume["factures_suivies"] == 1
