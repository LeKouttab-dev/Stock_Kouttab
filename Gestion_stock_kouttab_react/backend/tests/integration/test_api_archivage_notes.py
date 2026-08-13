"""Archivage d'une note de frais, en remplacement de la suppression.

La suppression effaçait la ligne **et** les justificatifs. Une pièce comptable
que l'association doit conserver plusieurs années disparaissait sur un clic,
sans trace de son existence. Ces tests portent sur ce point : ce qui sort des
listes doit rester en base, et se retrouver.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.crud import expense as expense_crud
from app.db.models import Expense


def _note_remboursee(db_session, user):
    note = expense_crud.create_expense(
        db_session,
        user_id=user.id,
        date_depense=date(2026, 6, 12),
        rattachement="Frais généraux",
        fournisseur="Carrefour",
        nature_charge="Courses",
        montant=Decimal("42.90"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
    )
    note.status = "Remboursée"
    db_session.commit()
    return note


def test_l_archivage_ne_detruit_rien(client_authenticated_as, benevole_user, compta_user, db_session):
    note = _note_remboursee(db_session, benevole_user)

    reponse = client_authenticated_as(compta_user).delete(f"/api/v1/expenses/{note.id}")
    assert reponse.status_code == 200
    assert "archiv" in reponse.json()["message"].lower()

    # Le point entier de la migration : la ligne existe toujours.
    en_base = db_session.execute(select(Expense).where(Expense.id == note.id)).scalar_one()
    db_session.refresh(en_base)
    assert en_base.archived_at is not None
    assert en_base.archived_by == compta_user.id


def test_la_note_archivee_sort_des_listes_courantes(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note = _note_remboursee(db_session, benevole_user)
    client = client_authenticated_as(compta_user)
    client.delete(f"/api/v1/expenses/{note.id}")

    courant = client.get("/api/v1/expenses").json()
    assert all(n["id"] != note.id for n in courant)

    # ...et se retrouve dès qu'on la demande, avec la trace de qui l'a rangée.
    archive = client.get("/api/v1/expenses?include_archived=true").json()
    rangee = next(n for n in archive if n["id"] == note.id)
    assert rangee["archived_at"] is not None
    assert rangee["archived_by_name"] == compta_user.full_name


def test_le_benevole_ne_voit_plus_sa_note_archivee(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Sinon elle traînerait parmi ses demandes, laissant croire qu'il reste
    quelque chose à suivre."""
    note = _note_remboursee(db_session, benevole_user)
    client_authenticated_as(compta_user).delete(f"/api/v1/expenses/{note.id}")

    mes_notes = client_authenticated_as(benevole_user).get("/api/v1/expenses/me").json()
    assert all(n["id"] != note.id for n in mes_notes)


def test_la_restauration_defait_l_archivage(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """C'est ce qui rend l'opération sans danger : un clic de trop se répare."""
    note = _note_remboursee(db_session, benevole_user)
    client = client_authenticated_as(compta_user)
    client.delete(f"/api/v1/expenses/{note.id}")

    assert client.post(f"/api/v1/expenses/{note.id}/restore").status_code == 200

    courant = client.get("/api/v1/expenses").json()
    assert any(n["id"] == note.id for n in courant)


def test_les_justificatifs_survivent_a_l_archivage(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """L'ancienne suppression effaçait les fichiers du disque au passage.

    Ce sont précisément les pièces qu'il faut pouvoir produire des années après.
    """
    note = _note_remboursee(db_session, benevole_user)
    expense_crud.attach_file(
        db_session,
        expense_id=note.id,
        nom_fichier="ticket.pdf",
        chemin_fichier="/tmp/introuvable.pdf",
        taille_fichier=15,
        type_fichier="application/pdf",
        contenu=b"%PDF-1.4 ticket",
    )

    client = client_authenticated_as(compta_user)
    client.delete(f"/api/v1/expenses/{note.id}")

    archive = client.get("/api/v1/expenses?include_archived=true").json()
    rangee = next(n for n in archive if n["id"] == note.id)
    assert len(rangee["files"]) == 1

    fichier = rangee["files"][0]
    contenu = client.get(f"/api/v1/expenses/{note.id}/files/{fichier['id']}")
    assert contenu.status_code == 200
    assert contenu.content == b"%PDF-1.4 ticket"


def test_un_benevole_ne_peut_pas_archiver(client_authenticated_as, benevole_user, db_session):
    note = _note_remboursee(db_session, benevole_user)
    reponse = client_authenticated_as(benevole_user).delete(f"/api/v1/expenses/{note.id}")
    assert reponse.status_code == 403
