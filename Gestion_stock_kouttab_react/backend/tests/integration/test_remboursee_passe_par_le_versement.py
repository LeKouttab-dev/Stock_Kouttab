"""« Remboursée » se constate, elle ne se déclare pas.

Deux chemins menaient au même statut terminal :

1. **Enregistrer un remboursement** (`POST /reimbursements`) — produit le
   justificatif PDF et tableur, l'envoie, et rattache les notes au versement ;
2. **Choisir « Remboursée » dans la liste déroulante** de l'écran comptable —
   ne produit rien du tout.

Le second laissait des notes marquées payées sans versement enregistré : aucun
document à extraire, rien dans l'onglet « Remboursements », et le statut étant
terminal, **plus aucun moyen de corriger**. C'est exactement ce qui est arrivé
le 2026-08-13 sur une note de 10,37 €.

Un remboursement est un fait comptable — une date, un moyen, un établissement,
une approbation. Le statut n'en est que la trace.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.crud import expense as expense_crud
from app.crud import reimbursement as reimbursement_crud


def _note(db_session, user, statut="Approuvée"):
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


def test_la_liste_deroulante_ne_permet_plus_de_declarer_un_remboursement(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note = _note(db_session, benevole_user)

    reponse = client_authenticated_as(compta_user).patch(
        f"/api/v1/expenses/{note.id}/validate",
        json={"status": "Remboursée", "commentaires_compta": ""},
    )
    assert reponse.status_code == 422

    # Le message doit dire par où passer, sinon le comptable croit à un bug
    # après avoir cliqué sur un choix que l'écran lui proposait.
    assert "Rembourser" in reponse.json()["message"]

    db_session.refresh(note)
    assert note.status == "Approuvée"


def test_le_versement_reste_le_seul_chemin(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note = _note(db_session, benevole_user)

    versement = reimbursement_crud.create_reimbursement(
        db_session, expense_ids=[note.id], cree_par=compta_user.id
    )

    db_session.refresh(note)
    assert note.status == "Remboursée"
    assert note.id_remboursement == versement.id

    # ...et le justificatif est là, c'était tout l'enjeu.
    liste = client_authenticated_as(compta_user).get("/api/v1/reimbursements").json()
    fiche = next(r for r in liste if r["id"] == versement.id)
    assert fiche["a_pdf"] is True


def test_une_note_marquee_a_tort_peut_etre_corrigee(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Sans cette porte de sortie, la note de 10,37 € resterait bloquée.

    Marquée payée, sans document, et « Remboursée » étant terminal, aucune
    transition ne permettait d'y revenir pour enregistrer le versement.
    """
    note = _note(db_session, benevole_user, statut="Remboursée")
    assert note.id_remboursement is None

    reponse = client_authenticated_as(compta_user).patch(
        f"/api/v1/expenses/{note.id}/validate",
        json={"status": "Approuvée", "commentaires_compta": "Versement à enregistrer"},
    )
    assert reponse.status_code == 200

    db_session.refresh(note)
    assert note.status == "Approuvée"

    # Et elle repart dans le circuit normal.
    versement = reimbursement_crud.create_reimbursement(
        db_session, expense_ids=[note.id], cree_par=compta_user.id
    )
    assert versement.montant_total == Decimal("10.37")


def test_une_note_reellement_versee_ne_revient_pas_en_arriere(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Le virement est parti et le justificatif est émis : y revenir le
    contredirait."""
    note = _note(db_session, benevole_user)
    reimbursement_crud.create_reimbursement(
        db_session, expense_ids=[note.id], cree_par=compta_user.id
    )

    reponse = client_authenticated_as(compta_user).patch(
        f"/api/v1/expenses/{note.id}/validate",
        json={"status": "Approuvée", "commentaires_compta": ""},
    )
    assert reponse.status_code == 409

    db_session.refresh(note)
    assert note.status == "Remboursée"


@pytest.mark.parametrize("statut", ["Approuvée", "Refusée", "En attente"])
def test_les_autres_transitions_restent_ouvertes(
    client_authenticated_as, benevole_user, compta_user, db_session, statut
):
    """La correction d'une erreur de saisie ne doit pas devenir impossible."""
    note = _note(db_session, benevole_user, statut="En attente" if statut != "En attente" else "Approuvée")

    reponse = client_authenticated_as(compta_user).patch(
        f"/api/v1/expenses/{note.id}/validate",
        json={"status": statut, "commentaires_compta": ""},
    )
    assert reponse.status_code == 200
