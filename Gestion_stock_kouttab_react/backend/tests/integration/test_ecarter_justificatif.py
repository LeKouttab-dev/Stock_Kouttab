"""Écarter un justificatif, et pouvoir en redéposer un.

Les deux vont ensemble. Aucun endpoint ne permettait d'ajouter une pièce à une
note déjà créée — `attach_file` n'était appelé qu'à la création, et l'écran
conseillait de « supprimer cette note et la recréer ». Écarter la seule pièce
d'une note l'aurait donc laissée vide, sans aucun recours : l'écran serait
devenu un piège.

Écarter, et non effacer : la pièce sort du dossier et du circuit comptable, mais
reste en base. Une pièce jointe à un dossier est une trace, même refusée.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from PIL import Image

from app.crud import expense as expense_crud
from app.db.models import ExpenseFile


def _image() -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 80, 180)).save(tampon, format="JPEG")
    return tampon.getvalue()


def _note_avec_piece(db_session, user, statut="En attente"):
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
    piece = expense_crud.attach_file(
        db_session,
        expense_id=note.id,
        nom_fichier="ticket.pdf",
        chemin_fichier="/tmp/introuvable.pdf",
        taille_fichier=12,
        type_fichier="application/pdf",
        contenu=b"%PDF-1.4 ticket",
    )
    db_session.commit()
    return note, piece


def _ecarter(client, note_id, file_id, motif="Ticket illisible"):
    return client.request(
        "DELETE", f"/api/v1/expenses/{note_id}/files/{file_id}", json={"motif": motif}
    )


# --- Écarter -----------------------------------------------------------------


def test_la_piece_sort_du_dossier_sans_quitter_la_base(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note, piece = _note_avec_piece(db_session, benevole_user)

    reponse = _ecarter(client_authenticated_as(compta_user), note.id, piece.id)
    assert reponse.status_code == 200

    db_session.expire_all()
    ligne = db_session.get(ExpenseFile, piece.id)
    assert ligne is not None, "la pièce reste en base"
    assert ligne.ecarte_at is not None
    assert ligne.ecarte_par == compta_user.id
    assert ligne.motif_ecart == "Ticket illisible"


def test_le_motif_est_obligatoire(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Il est montré au déposant : sans lui, il redépose la même pièce."""
    note, piece = _note_avec_piece(db_session, benevole_user)

    reponse = _ecarter(client_authenticated_as(compta_user), note.id, piece.id, motif="  ")
    assert reponse.status_code == 422

    db_session.expire_all()
    assert db_session.get(ExpenseFile, piece.id).ecarte_at is None


def test_le_deposant_ne_peut_pas_ecarter(
    client_authenticated_as, benevole_user, db_session
):
    note, piece = _note_avec_piece(db_session, benevole_user)
    assert _ecarter(client_authenticated_as(benevole_user), note.id, piece.id).status_code == 403


def test_une_piece_d_une_autre_note_est_refusee(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """Les identifiants se suivent : sans ce contrôle, celui d'une autre note
    passerait."""
    _, piece_a = _note_avec_piece(db_session, benevole_user)
    note_b, _ = _note_avec_piece(db_session, benevole_user)

    reponse = _ecarter(client_authenticated_as(compta_user), note_b.id, piece_a.id)
    assert reponse.status_code == 404


def test_le_deposant_est_prevenu(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """C'est une demande d'action : il doit redéposer quelque chose."""
    note, piece = _note_avec_piece(db_session, benevole_user)
    _ecarter(client_authenticated_as(compta_user), note.id, piece.id)

    resume = client_authenticated_as(benevole_user).get(
        "/api/v1/notifications/summary"
    ).json()
    assert resume["notes_suivies"] == 1


def test_l_ecart_et_son_motif_sont_visibles(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note, piece = _note_avec_piece(db_session, benevole_user)
    _ecarter(client_authenticated_as(compta_user), note.id, piece.id, motif="Montant illisible")

    mes_notes = client_authenticated_as(benevole_user).get("/api/v1/expenses/me").json()
    fichier = next(n for n in mes_notes if n["id"] == note.id)["files"][0]
    assert fichier["ecarte_at"] is not None
    assert fichier["motif_ecart"] == "Montant illisible"


def test_la_restauration_defait_l_ecart(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    note, piece = _note_avec_piece(db_session, benevole_user)
    compta = client_authenticated_as(compta_user)
    _ecarter(compta, note.id, piece.id)

    assert compta.post(
        f"/api/v1/expenses/{note.id}/files/{piece.id}/restore"
    ).status_code == 200

    db_session.expire_all()
    ligne = db_session.get(ExpenseFile, piece.id)
    assert ligne.ecarte_at is None and ligne.motif_ecart is None


def test_une_piece_ecartee_ne_part_plus_au_comptable(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """C'est le comptable lui-même qui l'a retirée du dossier."""
    from app.services import compta_dispatch

    note, piece = _note_avec_piece(db_session, benevole_user)
    _ecarter(client_authenticated_as(compta_user), note.id, piece.id)

    db_session.expire_all()
    note_fraiche = expense_crud.get_expense(db_session, note.id)
    envois = compta_dispatch.prepare_expense_dispatch(db_session, note_fraiche)

    # Le courriel part quand même — une note sans ticket se signale, le dépôt de
    # pièce étant facultatif — mais il ne porte plus la pièce écartée.
    assert len(envois) == 1
    assert envois[0].attachments in ("[]", None)


# --- Redéposer ---------------------------------------------------------------


def test_le_deposant_peut_ajouter_une_piece(
    client_authenticated_as, benevole_user, db_session
):
    """Sans cela, écarter la seule pièce d'une note la laisserait vide."""
    note, _ = _note_avec_piece(db_session, benevole_user)

    reponse = client_authenticated_as(benevole_user).post(
        f"/api/v1/expenses/{note.id}/files",
        files={"files": ("remplacement.jpg", io.BytesIO(_image()), "image/jpeg")},
    )
    assert reponse.status_code == 201, reponse.text
    assert len(reponse.json()["files"]) == 2

    # Convertie comme n'importe quel justificatif.
    nouvelle = reponse.json()["files"][-1]
    assert nouvelle["type_fichier"] == "application/pdf"


def test_une_note_soldee_n_accepte_plus_de_piece(
    client_authenticated_as, benevole_user, db_session
):
    """Le versement est parti et son justificatif est émis."""
    note, _ = _note_avec_piece(db_session, benevole_user, statut="Remboursée")

    reponse = client_authenticated_as(benevole_user).post(
        f"/api/v1/expenses/{note.id}/files",
        files={"files": ("tardif.jpg", io.BytesIO(_image()), "image/jpeg")},
    )
    assert reponse.status_code == 403


def test_la_comptabilite_peut_ajouter_a_tout_moment(
    client_authenticated_as, benevole_user, compta_user, db_session
):
    """C'est elle qui constate le manque, et parfois elle a la pièce en main."""
    note, _ = _note_avec_piece(db_session, benevole_user, statut="Remboursée")

    reponse = client_authenticated_as(compta_user).post(
        f"/api/v1/expenses/{note.id}/files",
        files={"files": ("scan.jpg", io.BytesIO(_image()), "image/jpeg")},
    )
    assert reponse.status_code == 201


def test_un_tiers_ne_depose_pas_sur_la_note_d_autrui(
    client_authenticated_as, benevole_user, admin_benevoles_user, db_session
):
    note, _ = _note_avec_piece(db_session, benevole_user)

    reponse = client_authenticated_as(admin_benevoles_user).post(
        f"/api/v1/expenses/{note.id}/files",
        files={"files": ("intrus.jpg", io.BytesIO(_image()), "image/jpeg")},
    )
    assert reponse.status_code == 403
