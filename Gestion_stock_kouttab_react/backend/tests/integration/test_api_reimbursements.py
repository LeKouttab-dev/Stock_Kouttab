"""Remboursement groupe, de la selection des notes au justificatif envoye.

Ce que ces tests protegent : de l'argent qui sort. Une note remboursee deux
fois, un remboursement melangeant deux benevoles, ou un justificatif visible du
mauvais compte sont des erreurs qu'on ne rattrape pas apres le virement.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.crud import expense as expense_crud
from app.db.models import Expense, OutboundEmail, Reimbursement


pytestmark = pytest.mark.integration


def _note(db, user, local_pole, first_category, montant="42.50", statut="Approuvée"):
    note = expense_crud.create_expense(
        db,
        user_id=user.id,
        date_depense=date(2026, 8, 3),
        rattachement=None,
        fournisseur="Metro",
        nature_charge="Alimentation",
        montant=Decimal(montant),
        commentaires="Gouter",
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
        id_pole=local_pole.id,
        pole=local_pole.nom,
        id_categorie=first_category.id,
        categorie=first_category.nom,
    )
    note.status = statut
    db.commit()
    return note


def _rembourser(client, compta_user, auth_headers, ids, **extra):
    return client.post(
        "/api/v1/reimbursements",
        json={"expense_ids": ids, **extra},
        headers=auth_headers(compta_user),
    )


# ---- Cas nominal ------------------------------------------------------------


def test_un_versement_solde_plusieurs_notes(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    a = _note(db_session, benevole_user, local_pole, first_category, "30.00")
    b = _note(db_session, benevole_user, local_pole, first_category, "12.50")

    reponse = _rembourser(client, compta_user, auth_headers, [a.id, b.id])

    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert Decimal(str(corps["montant_total"])) == Decimal("42.50")
    assert corps["moyen"] == "Virement bancaire"
    assert corps["etablissement"] == "Wise"
    assert corps["approuve_par"] == "DTC"
    assert corps["a_pdf"] and corps["a_xlsx"]

    db_session.expire_all()
    for note in (db_session.get(Expense, a.id), db_session.get(Expense, b.id)):
        assert note.status == "Remboursée"
        assert note.id_remboursement == corps["id"]


def test_le_justificatif_part_vers_la_comptabilite(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    note = _note(db_session, benevole_user, local_pole, first_category)
    _rembourser(client, compta_user, auth_headers, [note.id])

    envois = db_session.query(OutboundEmail).filter_by(entity_type="reimbursement").all()
    # Deux envois : la comptabilite archive, le benevole recoit sa preuve.
    assert len(envois) == 2
    for envoi in envois:
        assert "Remboursement" in envoi.subject
        # Les deux formats sont joints : le PDF pour archiver, le tableur pour
        # retravailler les chiffres.
        assert ".pdf" in envoi.attachments and ".xlsx" in envoi.attachments


def test_le_benevole_recoit_son_justificatif(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    """Il ne recevait rien du tout.

    `_mettre_en_file` n'ecrivait qu'a `COMPTA_EMAIL` : le benevole apprenait son
    remboursement en consultant son compte bancaire, et n'avait aucune piece a
    produire. C'est pourtant lui que le document nomme.
    """
    note = _note(db_session, benevole_user, local_pole, first_category)
    _rembourser(client, compta_user, auth_headers, [note.id])

    envois = db_session.query(OutboundEmail).filter_by(entity_type="reimbursement").all()
    pour_benevole = [e for e in envois if benevole_user.email in e.recipients]
    assert len(pour_benevole) == 1

    corps = pour_benevole[0].body
    # Salutation de l'institut, et non « Bonjour » : ces courriels s'adressent
    # aux benevoles (cf. services/email_layout.py).
    assert "Assalamu alaykum" in corps
    assert "42.50" in corps or "42,50" in corps


def test_le_benevole_sans_adresse_ne_bloque_pas_le_remboursement(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    """Un compte sans courriel ne doit pas empecher un virement d'etre enregistre."""
    benevole_user.email = None
    db_session.commit()

    note = _note(db_session, benevole_user, local_pole, first_category)
    reponse = _rembourser(client, compta_user, auth_headers, [note.id])
    assert reponse.status_code == 201

    envois = db_session.query(OutboundEmail).filter_by(entity_type="reimbursement").all()
    # Seul celui de la comptabilite : on ne met pas en file un envoi sans
    # destinataire, il resterait « en attente » pour toujours.
    assert len(envois) == 1


def test_les_deux_documents_se_telechargent(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    note = _note(db_session, benevole_user, local_pole, first_category)
    rid = _rembourser(client, compta_user, auth_headers, [note.id]).json()["id"]

    pdf = client.get(
        f"/api/v1/reimbursements/{rid}/document?format=pdf",
        headers=auth_headers(compta_user),
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF-")

    xlsx = client.get(
        f"/api/v1/reimbursements/{rid}/document?format=xlsx",
        headers=auth_headers(compta_user),
    )
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"  # un .xlsx est une archive zip


# ---- Refus ------------------------------------------------------------------


def test_une_note_deja_remboursee_est_refusee(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    """Le risque le plus couteux : virer deux fois la meme depense."""
    note = _note(db_session, benevole_user, local_pole, first_category)
    assert _rembourser(client, compta_user, auth_headers, [note.id]).status_code == 201

    seconde = _rembourser(client, compta_user, auth_headers, [note.id])
    assert seconde.status_code == 409, seconde.text
    assert db_session.query(Reimbursement).count() == 1


def test_deux_benevoles_dans_un_meme_versement_sont_refuses(
    client: TestClient, compta_user, benevole_user, super_admin_user, auth_headers,
    db_session, local_pole, first_category,
):
    a = _note(db_session, benevole_user, local_pole, first_category)
    b = _note(db_session, super_admin_user, local_pole, first_category)

    reponse = _rembourser(client, compta_user, auth_headers, [a.id, b.id])

    assert reponse.status_code == 422, reponse.text
    assert db_session.query(Reimbursement).count() == 0


def test_une_note_non_approuvee_est_refusee(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    note = _note(db_session, benevole_user, local_pole, first_category, statut="En attente")
    reponse = _rembourser(client, compta_user, auth_headers, [note.id])
    assert reponse.status_code == 422, reponse.text


def test_rien_n_est_ecrit_quand_le_lot_est_invalide(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    """Tout ou rien : rembourser deux notes sur trois en silence ne se verrait
    qu'au rapprochement bancaire."""
    valide = _note(db_session, benevole_user, local_pole, first_category)
    invalide = _note(
        db_session, benevole_user, local_pole, first_category, statut="En attente"
    )

    reponse = _rembourser(client, compta_user, auth_headers, [valide.id, invalide.id])

    assert reponse.status_code == 422
    db_session.expire_all()
    assert db_session.get(Expense, valide.id).status == "Approuvée"
    assert db_session.query(Reimbursement).count() == 0


def test_un_moyen_hors_liste_est_refuse(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    note = _note(db_session, benevole_user, local_pole, first_category)
    reponse = _rembourser(
        client, compta_user, auth_headers, [note.id], moyen="Bitcoin"
    )
    assert reponse.status_code == 422, reponse.text


# ---- Droits -----------------------------------------------------------------


def test_un_benevole_ne_peut_pas_rembourser(
    client: TestClient, benevole_user, auth_headers, db_session, local_pole, first_category
):
    note = _note(db_session, benevole_user, local_pole, first_category)
    reponse = client.post(
        "/api/v1/reimbursements",
        json={"expense_ids": [note.id]},
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 403, reponse.text


def test_un_benevole_voit_ses_remboursements_et_pas_ceux_des_autres(
    client: TestClient, compta_user, benevole_user, super_admin_user, auth_headers,
    db_session, local_pole, first_category,
):
    sienne = _note(db_session, benevole_user, local_pole, first_category)
    autre = _note(db_session, super_admin_user, local_pole, first_category)
    _rembourser(client, compta_user, auth_headers, [sienne.id])
    _rembourser(client, compta_user, auth_headers, [autre.id])

    vus = client.get("/api/v1/reimbursements", headers=auth_headers(benevole_user)).json()
    assert [r["id_user"] for r in vus] == [benevole_user.id]


def test_le_justificatif_d_autrui_est_refuse(
    client: TestClient, compta_user, benevole_user, super_admin_user, auth_headers,
    db_session, local_pole, first_category,
):
    note = _note(db_session, super_admin_user, local_pole, first_category)
    rid = _rembourser(client, compta_user, auth_headers, [note.id]).json()["id"]

    reponse = client.get(
        f"/api/v1/reimbursements/{rid}/document", headers=auth_headers(benevole_user)
    )
    assert reponse.status_code == 403, reponse.text


# ---- Regroupement par benevole ----------------------------------------------


def test_la_fiche_benevole_compte_ce_qui_reste_du(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    _note(db_session, benevole_user, local_pole, first_category, "30.00")
    _note(db_session, benevole_user, local_pole, first_category, "20.00")
    _note(
        db_session, benevole_user, local_pole, first_category, "99.00", statut="En attente"
    )

    fiches = client.get(
        "/api/v1/reimbursements/by-volunteer", headers=auth_headers(compta_user)
    ).json()
    fiche = next(f for f in fiches if f["id_user"] == benevole_user.id)

    assert fiche["nb_notes"] == 3
    # Seules les notes approuvees sont dues : celle « En attente » ne l'est pas.
    assert fiche["nb_a_rembourser"] == 2
    assert Decimal(str(fiche["total_du"])) == Decimal("50.00")


def test_le_total_du_tombe_apres_remboursement(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    note = _note(db_session, benevole_user, local_pole, first_category, "30.00")
    _rembourser(client, compta_user, auth_headers, [note.id])

    fiches = client.get(
        "/api/v1/reimbursements/by-volunteer", headers=auth_headers(compta_user)
    ).json()
    fiche = next(f for f in fiches if f["id_user"] == benevole_user.id)
    assert fiche["nb_a_rembourser"] == 0
    assert Decimal(str(fiche["total_du"])) == Decimal("0")
