"""Chaque courriel au déposant porte un lien d'accès — le bon selon le compte.

Un compte ordinaire est renvoyé vers la page stock concernée. Un compte
« BenevoleFrais » n'a PAS de mot de passe stock : le lien vers l'écran de
connexion serait une impasse. Sa porte d'entrée est l'outil de gestion
(gestion.lekouttab.fr/benevole), où un clic refait le passage signé. Jamais de
jeton dans un courriel : 60 secondes de vie ne survivent pas à une boîte mail.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.crud import expense as expense_crud
from app.db.models import ExpenseFile, OutboundEmail


LIEN_STOCK_NOTES = f"{settings.frontend_url.rstrip('/')}/expenses"
LIEN_STOCK_FACTURES = f"{settings.frontend_url.rstrip('/')}/invoices"
LIEN_GESTION = f"{settings.gestion_url.rstrip('/')}/benevole"


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


def _dernier_envoi(db_session):
    return db_session.execute(
        select(OutboundEmail).order_by(OutboundEmail.id.desc())
    ).scalars().first()


def _valider(client, note_id):
    return client.patch(
        f"/api/v1/expenses/{note_id}/validate",
        json={"status": "Approuvée", "commentaires_compta": ""},
    )


def test_le_courriel_de_statut_mene_a_la_page_stock(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note = _note(db_session, benevole_user)
    _valider(client_authenticated_as(compta_user), note.id)

    envoi = _dernier_envoi(db_session)
    assert LIEN_STOCK_NOTES in envoi.body


def test_un_benevole_frais_est_renvoye_vers_l_outil_de_gestion(
    client_authenticated_as, benevole_frais_user, compta_user, db_session
):
    """Il n'a pas de mot de passe stock : l'écran de connexion serait une
    impasse. Sa porte est l'outil de gestion, qui refait le passage signé."""
    note = _note(db_session, benevole_frais_user)
    _valider(client_authenticated_as(compta_user), note.id)

    envoi = _dernier_envoi(db_session)
    assert LIEN_GESTION in envoi.body
    assert LIEN_STOCK_NOTES not in envoi.body


def test_l_ecart_d_un_justificatif_porte_aussi_le_lien(
    client_authenticated_as, benevole_frais_user, compta_user, db_session
):
    note = _note(db_session, benevole_frais_user)
    piece = ExpenseFile(
        id_note_de_frais=note.id,
        nom_fichier="ticket.jpg",
        chemin_fichier="/tmp/ticket.jpg",
    )
    db_session.add(piece)
    db_session.commit()

    client_authenticated_as(compta_user).request(
        "DELETE",
        f"/api/v1/expenses/{note.id}/files/{piece.id}",
        json={"motif": "Photo illisible."},
    )

    envoi = _dernier_envoi(db_session)
    assert envoi.kind == "piece_ecartee"
    assert LIEN_GESTION in envoi.body


def test_le_refus_d_une_facture_mene_a_la_page_des_factures(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
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
    client_authenticated_as(compta_user).patch(
        f"/api/v1/invoices/{facture.id}/status",
        json={"status": "Refusée", "commentaires_compta": "Pièce illisible."},
    )

    envoi = _dernier_envoi(db_session)
    assert json.loads(envoi.recipients) == [benevole_user.email]
    assert LIEN_STOCK_FACTURES in envoi.body


def test_les_liens_sont_absolus(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Un lien relatif ne s'ouvre pas depuis une boîte mail : le client de
    messagerie n'a pas d'origine à lui donner."""
    note = _note(db_session, benevole_user)
    _valider(client_authenticated_as(compta_user), note.id)

    envoi = _dernier_envoi(db_session)
    assert "http" in envoi.body
