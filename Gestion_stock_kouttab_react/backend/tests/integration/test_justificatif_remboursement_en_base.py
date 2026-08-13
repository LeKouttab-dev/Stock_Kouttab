"""Le justificatif de remboursement doit survivre à la perte du disque.

Les justificatifs de notes de frais et de factures sont passés en base à la
migration `f6b3d1e8a295`, sur un raisonnement simple : la base est sauvegardée
par l'hébergeur, le volume Docker ne l'est pas.

Le justificatif de remboursement, lui, était resté sur le seul disque — la
**dernière** famille de documents dans ce cas. La base gardait un chemin, et
rien d'autre : un `docker compose down -v`, un changement de VPS ou un
`volume prune` laissait des remboursements enregistrés sans leur preuve, alors
que ce document porte le montant versé, le moyen et l'approbation.

Il est reconstructible en théorie — les notes sont toujours là — mais aucun code
ne le fait, et un document reconstruit six mois plus tard n'a pas la même valeur
qu'une pièce émise le jour du virement.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.crud import expense as expense_crud
from app.crud import reimbursement as reimbursement_crud
from app.db.models import Reimbursement


def _note_approuvee(db_session, user, montant="42.90"):
    note = expense_crud.create_expense(
        db_session,
        user_id=user.id,
        date_depense=date(2026, 6, 12),
        rattachement="Frais généraux",
        fournisseur="Carrefour",
        nature_charge="Courses",
        montant=Decimal(montant),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
    )
    note.status = "Approuvée"
    db_session.commit()
    return note


@pytest.fixture()
def remboursement(db_session, benevole_user, compta_user):
    note = _note_approuvee(db_session, benevole_user)
    return reimbursement_crud.create_reimbursement(
        db_session, expense_ids=[note.id], cree_par=compta_user.id
    )


def test_les_documents_sont_ecrits_en_base(remboursement, db_session):
    ligne = db_session.execute(
        select(Reimbursement).where(Reimbursement.id == remboursement.id)
    ).scalar_one()
    db_session.refresh(ligne)

    assert ligne.contenu_pdf and ligne.contenu_pdf.startswith(b"%PDF")
    # Un XLSX est une archive ZIP : « PK » en tête.
    assert ligne.contenu_xlsx and ligne.contenu_xlsx.startswith(b"PK")


def test_le_telechargement_survit_a_la_perte_du_disque(
    client_authenticated_as, benevole_user, remboursement, db_session
):
    """Le cœur du sujet : effacer le volume ne doit plus rien coûter."""
    from pathlib import Path

    for chemin in (remboursement.chemin_pdf, remboursement.chemin_xlsx):
        Path(chemin).unlink()

    client = client_authenticated_as(benevole_user)
    for format_, entete in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        reponse = client.get(
            f"/api/v1/reimbursements/{remboursement.id}/document?format={format_}"
        )
        assert reponse.status_code == 200, format_
        assert reponse.content.startswith(entete)


def test_le_justificatif_d_autrui_reste_refuse(
    client_authenticated_as, admin_benevoles_user, remboursement
):
    """La règle ne bouge pas : rôle comptable **ou** propriétaire."""
    reponse = client_authenticated_as(admin_benevoles_user).get(
        f"/api/v1/reimbursements/{remboursement.id}/document"
    )
    assert reponse.status_code == 403


def test_le_drapeau_de_presence_regarde_le_contenu(
    client_authenticated_as, compta_user, remboursement, db_session
):
    """`a_pdf` testait la présence du **chemin**, pas du fichier.

    L'écran promettait donc un téléchargement qui rendait un 404.
    """
    liste = client_authenticated_as(compta_user).get("/api/v1/reimbursements").json()
    fiche = next(r for r in liste if r["id"] == remboursement.id)
    assert fiche["a_pdf"] is True and fiche["a_xlsx"] is True

    ligne = db_session.get(Reimbursement, remboursement.id)
    ligne.contenu_pdf = None
    ligne.chemin_pdf = None
    db_session.commit()

    liste = client_authenticated_as(compta_user).get("/api/v1/reimbursements").json()
    fiche = next(r for r in liste if r["id"] == remboursement.id)
    assert fiche["a_pdf"] is False
    assert fiche["a_xlsx"] is True


def test_un_remboursement_sans_document_le_dit(
    client_authenticated_as, benevole_user, remboursement, db_session
):
    from pathlib import Path

    ligne = db_session.get(Reimbursement, remboursement.id)
    Path(ligne.chemin_pdf).unlink()
    ligne.contenu_pdf = None
    db_session.commit()

    reponse = client_authenticated_as(benevole_user).get(
        f"/api/v1/reimbursements/{remboursement.id}/document?format=pdf"
    )
    assert reponse.status_code == 404
