"""Archiver une facture, et filtrer la liste comme pour les notes de frais.

`DELETE /invoices/{id}` détruisait la ligne, ses fichiers et leur contenu en
base. La comptabilité pouvait le déclencher sur **n'importe quel** statut, y
compris « Validée » — c'est-à-dire sur une pièce déjà comptabilisée.

Un bug de filtre est corrigé au passage : `status`, `days` et `search` étaient
ignorés pour un bénévole. Le menu déroulant de son écran ne faisait donc rien,
il changeait seulement la clé de cache et redemandait la même liste.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.crud import invoice as invoice_crud
from app.db.models import Invoice, InvoiceFile


def _facture(db_session, user, local_pole, first_category, statut="En attente"):
    facture = invoice_crud.create_invoice(
        db_session,
        user_id=user.id,
        commentaire=None,
        date_depot=date(2026, 8, 12),
        id_pole=local_pole.id,
        pole=local_pole.nom,
        id_categorie=first_category.id,
        categorie=first_category.nom,
        fournisseur="Action",
    )
    invoice_crud.attach_file(
        db_session,
        invoice_id=facture.id,
        nom_fichier="facture.pdf",
        chemin_fichier="/tmp/introuvable.pdf",
        taille_fichier=12,
        type_fichier="application/pdf",
        contenu=b"%PDF-1.4 facture",
    )
    facture.status = statut
    db_session.commit()
    return facture


# --- Archivage ---------------------------------------------------------------


def test_l_archivage_ne_detruit_rien(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
    facture = _facture(db_session, benevole_user, local_pole, first_category, statut="Validée")
    identifiant = facture.id

    reponse = client_authenticated_as(compta_user).delete(f"/api/v1/invoices/{identifiant}")
    assert reponse.status_code == 200
    assert "archiv" in reponse.json()["message"].lower()

    db_session.expire_all()
    ligne = db_session.execute(
        select(Invoice).where(Invoice.id == identifiant)
    ).scalar_one()
    assert ligne.archived_at is not None
    assert ligne.archived_by == compta_user.id
    # La pièce reste : c'est tout l'objet du changement.
    assert db_session.execute(
        select(InvoiceFile).where(InvoiceFile.id_facture == identifiant)
    ).scalars().all()


def test_la_facture_archivee_sort_des_listes(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
    facture = _facture(db_session, benevole_user, local_pole, first_category)
    compta = client_authenticated_as(compta_user)
    compta.delete(f"/api/v1/invoices/{facture.id}")

    courant = compta.get("/api/v1/invoices").json()
    assert all(f["id"] != facture.id for f in courant)

    archive = compta.get("/api/v1/invoices?include_archived=true").json()
    rangee = next(f for f in archive if f["id"] == facture.id)
    assert rangee["archived_by_name"] == compta_user.full_name

    # Le déposant ne la voit plus non plus.
    miennes = client_authenticated_as(benevole_user).get("/api/v1/invoices/me").json()
    assert all(f["id"] != facture.id for f in miennes)


def test_la_restauration_defait_l_archivage(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
    facture = _facture(db_session, benevole_user, local_pole, first_category)
    compta = client_authenticated_as(compta_user)
    compta.delete(f"/api/v1/invoices/{facture.id}")

    assert compta.post(f"/api/v1/invoices/{facture.id}/restore").status_code == 200
    assert any(f["id"] == facture.id for f in compta.get("/api/v1/invoices").json())


def test_le_deposant_n_archive_que_ce_qui_n_est_pas_traite(
    client_authenticated_as, benevole_user, db_session, local_pole, first_category
):
    en_attente = _facture(db_session, benevole_user, local_pole, first_category)
    traitee = _facture(
        db_session, benevole_user, local_pole, first_category, statut="En cours de traitement"
    )
    client = client_authenticated_as(benevole_user)

    assert client.delete(f"/api/v1/invoices/{en_attente.id}").status_code == 200
    assert client.delete(f"/api/v1/invoices/{traitee.id}").status_code == 403


def test_un_tiers_n_archive_pas_la_facture_d_autrui(
    client_authenticated_as, benevole_user, admin_benevoles_user, db_session,
    local_pole, first_category,
):
    facture = _facture(db_session, benevole_user, local_pole, first_category)
    reponse = client_authenticated_as(admin_benevoles_user).delete(
        f"/api/v1/invoices/{facture.id}"
    )
    assert reponse.status_code == 403


def test_seule_la_comptabilite_restaure(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
    facture = _facture(db_session, benevole_user, local_pole, first_category)
    client_authenticated_as(compta_user).delete(f"/api/v1/invoices/{facture.id}")

    reponse = client_authenticated_as(benevole_user).post(
        f"/api/v1/invoices/{facture.id}/restore"
    )
    assert reponse.status_code == 403


# --- Filtres -----------------------------------------------------------------


def test_le_deposant_peut_enfin_filtrer_par_statut(
    client_authenticated_as, benevole_user, db_session, local_pole, first_category
):
    """Les filtres étaient ignorés pour lui : le menu déroulant ne faisait rien."""
    _facture(db_session, benevole_user, local_pole, first_category, statut="En attente")
    _facture(db_session, benevole_user, local_pole, first_category, statut="Validée")

    client = client_authenticated_as(benevole_user)
    assert len(client.get("/api/v1/invoices/me").json()) == 2

    validees = client.get("/api/v1/invoices/me?status=Validée").json()
    assert len(validees) == 1
    assert validees[0]["status"] == "Validée"


def test_la_recherche_porte_aussi_sur_le_fournisseur(
    client_authenticated_as, compta_user, benevole_user, db_session, local_pole, first_category
):
    _facture(db_session, benevole_user, local_pole, first_category)

    trouvees = client_authenticated_as(compta_user).get("/api/v1/invoices?search=action").json()
    assert len(trouvees) == 1


def test_ouvrir_ses_factures_eteint_la_pastille(
    client_authenticated_as, benevole_user, compta_user, db_session, local_pole, first_category
):
    facture = _facture(db_session, benevole_user, local_pole, first_category)
    client_authenticated_as(compta_user).patch(
        f"/api/v1/invoices/{facture.id}/status",
        json={"status": "Refusée", "commentaires_compta": "Pièce illisible."},
    )

    benevole = client_authenticated_as(benevole_user)
    miennes = benevole.get("/api/v1/invoices/me").json()
    # La liste montre encore le signal, puis il s'éteint.
    assert next(f for f in miennes if f["id"] == facture.id)["non_lu_demandeur"] is True

    resume = benevole.get("/api/v1/notifications/summary").json()
    assert resume["factures_suivies"] == 0
