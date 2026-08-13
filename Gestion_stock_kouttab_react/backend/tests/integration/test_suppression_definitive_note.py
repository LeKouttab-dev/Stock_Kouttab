"""Suppression définitive d'une note de frais.

L'archivage reste le geste normal : une pièce comptable se conserve. Mais une
base de production porte aussi des notes de **test** et des saisies fautives, et
rien ne permettait de les faire disparaître — l'archivage les range, il ne les
retire pas.

Trois garde-fous, parce que l'opération est irréversible :

1. **Super Admin uniquement.** La comptabilité archive ; elle ne détruit pas.
2. **Un motif obligatoire**, écrit en base avant l'effacement — c'est la seule
   trace qui restera de l'existence de la note.
3. **Une confirmation explicite** côté écran, qui dit ce que le geste emporte.

Ces tests figent le périmètre : ce qui part, et ce qui reste.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.crud import expense as expense_crud
from app.crud import reimbursement as reimbursement_crud
from app.db.models import Expense, ExpenseFile, Reimbursement


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


def _supprimer(client, note_id, motif="Note de test"):
    return client.request(
        "DELETE",
        f"/api/v1/expenses/{note_id}/definitif",
        json={"motif": motif},
    )


def test_la_note_et_ses_justificatifs_disparaissent(
    client_authenticated_as, benevole_user, super_admin_user, db_session
):
    note = _note(db_session, benevole_user)
    expense_crud.attach_file(
        db_session,
        expense_id=note.id,
        nom_fichier="ticket.pdf",
        chemin_fichier="/tmp/introuvable.pdf",
        taille_fichier=15,
        type_fichier="application/pdf",
        contenu=b"%PDF-1.4 ticket",
    )

    identifiant = note.id

    reponse = _supprimer(client_authenticated_as(super_admin_user), identifiant)
    assert reponse.status_code == 200

    db_session.expire_all()
    assert db_session.execute(
        select(Expense).where(Expense.id == identifiant)
    ).scalar_one_or_none() is None
    # La cascade emporte les pièces : aucune ligne orpheline.
    restants = db_session.execute(
        select(ExpenseFile).where(ExpenseFile.id_note_de_frais == identifiant)
    ).scalars().all()
    assert restants == []


def test_la_comptabilite_archive_mais_ne_detruit_pas(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Le geste destructeur ne se délègue pas : il n'existe que pour le ménage."""
    note = _note(db_session, benevole_user)

    reponse = _supprimer(client_authenticated_as(compta_user), note.id)
    assert reponse.status_code == 403
    assert db_session.get(Expense, note.id) is not None


def test_un_benevole_ne_supprime_pas_sa_propre_note(
    client_authenticated_as, benevole_user, db_session
):
    note = _note(db_session, benevole_user)
    assert _supprimer(client_authenticated_as(benevole_user), note.id).status_code == 403


def test_le_motif_est_obligatoire(client_authenticated_as, benevole_user, super_admin_user, db_session):
    """Seule trace qui restera : sans elle, la note s'évapore sans explication."""
    note = _note(db_session, benevole_user)

    reponse = _supprimer(client_authenticated_as(super_admin_user), note.id, motif="  ")
    assert reponse.status_code == 422
    assert db_session.get(Expense, note.id) is not None


def test_la_suppression_est_journalisee(
    client_authenticated_as, benevole_user, super_admin_user, db_session, monkeypatch
):
    """La seule trace qui restera de la note.

    On intercepte le logger du module plutôt que d'utiliser `caplog` : celui de
    l'application ne propage pas vers la racine, et `caplog` ne capte rien — le
    test passerait alors en n'observant absolument rien.
    """
    note = _note(db_session, benevole_user)
    identifiant = note.id

    traces: list[str] = []
    monkeypatch.setattr(
        expense_crud.logger,
        "warning",
        lambda message, *args, **_: traces.append(message % args if args else message),
    )

    _supprimer(client_authenticated_as(super_admin_user), identifiant, motif="Jeu d'essai")

    trace = "\n".join(traces)
    assert str(identifiant) in trace
    assert "Jeu d'essai" in trace
    assert super_admin_user.username in trace


def test_un_versement_devenu_vide_part_avec_elle(
    client_authenticated_as, benevole_user, super_admin_user, compta_user, db_session
):
    """Un remboursement dont toutes les notes ont disparu ne documente plus rien.

    Le laisser encombrerait l'onglet « Remboursements » d'un versement sans
    contrepartie — exactement le résidu que ce ménage cherche à retirer.
    """
    note = _note(db_session, benevole_user)
    versement = reimbursement_crud.create_reimbursement(
        db_session, expense_ids=[note.id], cree_par=compta_user.id
    )
    versement_id = versement.id

    _supprimer(client_authenticated_as(super_admin_user), note.id)

    db_session.expire_all()
    assert db_session.execute(
        select(Reimbursement).where(Reimbursement.id == versement_id)
    ).scalar_one_or_none() is None


def test_un_versement_encore_garni_survit(
    client_authenticated_as, benevole_user, super_admin_user, compta_user, db_session
):
    """Il solde d'autres notes : son justificatif reste exact pour celles-là."""
    gardee = _note(db_session, benevole_user)
    supprimee = _note(db_session, benevole_user)
    versement = reimbursement_crud.create_reimbursement(
        db_session, expense_ids=[gardee.id, supprimee.id], cree_par=compta_user.id
    )

    versement_id, gardee_id = versement.id, gardee.id
    _supprimer(client_authenticated_as(super_admin_user), supprimee.id)

    db_session.expire_all()
    assert db_session.execute(
        select(Reimbursement).where(Reimbursement.id == versement_id)
    ).scalar_one_or_none() is not None
    assert db_session.execute(
        select(Expense).where(Expense.id == gardee_id)
    ).scalar_one_or_none() is not None
