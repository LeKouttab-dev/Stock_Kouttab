"""Depot d'une piece selon ce que son pole attend, de bout en bout.

Les tests unitaires couvrent la regle ; ceux-ci verifient qu'elle traverse
reellement l'API — corps multipart compris — et qu'elle donne le meme resultat
sur les deux ecrans, notes de frais et factures.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.crud import expense as expense_crud
from app.crud import invoice as invoice_crud


pytestmark = pytest.mark.integration


def _fichier() -> dict:
    """Une vraie image : le depot la convertit en PDF et refuse net ce qu'il ne
    sait pas lire — un entete PNG bricole ne passe pas."""
    tampon = io.BytesIO()
    Image.new("RGB", (60, 30), (10, 90, 160)).save(tampon, format="JPEG")
    return {"files": ("ticket.jpg", io.BytesIO(tampon.getvalue()), "image/jpeg")}


# ---- Notes de frais ---------------------------------------------------------


def test_note_sur_pole_local_avec_categorie(
    client: TestClient, benevole_user, auth_headers, local_pole, first_category, db_session
):
    reponse = client.post(
        "/api/v1/expenses",
        data={
            "date_depense": "2026-08-12",
            "montant": "24.90",
            "fournisseur": "Metro",
            "id_pole": str(local_pole.id),
            "id_categorie": str(first_category.id),
            "commentaires": "Eau et gobelets pour le local",
        },
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert corps["categorie"] == first_category.nom
    assert corps["evenement"] is None
    assert corps["date_evenement"] is None

    enregistree = expense_crud.get_expense(db_session, corps["id"])
    assert enregistree is not None
    assert enregistree.id_categorie == first_category.id


def test_note_sur_pole_local_sans_categorie_refusee(
    client: TestClient, benevole_user, auth_headers, local_pole
):
    reponse = client.post(
        "/api/v1/expenses",
        data={
            "date_depense": "2026-08-12",
            "montant": "24.90",
            "fournisseur": "Metro",
            "id_pole": str(local_pole.id),
        },
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 422, reponse.text
    assert "categorie" in reponse.text.lower()


def test_note_sur_pole_local_avec_evenement_refusee(
    client: TestClient, benevole_user, auth_headers, local_pole, first_category
):
    reponse = client.post(
        "/api/v1/expenses",
        data={
            "date_depense": "2026-08-12",
            "montant": "24.90",
            "fournisseur": "Metro",
            "id_pole": str(local_pole.id),
            "id_categorie": str(first_category.id),
            "evenement_libre": "Gala",
        },
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 422, reponse.text


def test_note_sur_pole_evenementiel_inchangee(
    client: TestClient, benevole_user, auth_headers, first_pole
):
    """Le pole evenementiel garde exactement son fonctionnement d'avant."""
    reponse = client.post(
        "/api/v1/expenses",
        data={
            "date_depense": "2026-08-12",
            "montant": "24.90",
            "fournisseur": "Metro",
            "id_pole": str(first_pole.id),
            "evenement_libre": "Gala de fin d'année",
            "date_evenement": "2026-08-20",
        },
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert corps["evenement"] == "Gala de fin d'année"
    assert corps["categorie"] is None


# ---- Factures ---------------------------------------------------------------


def test_facture_sur_pole_local_avec_categorie(
    client: TestClient, benevole_user, auth_headers, local_pole, first_category, db_session
):
    reponse = client.post(
        "/api/v1/invoices",
        data={
            "id_pole": str(local_pole.id),
            "id_categorie": str(first_category.id),
            "fournisseur": "Metro",
            "montant": "40.00",
        },
        files=_fichier(),
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert corps["categorie"] == first_category.nom
    assert corps["evenement"] is None

    enregistree = invoice_crud.get_invoice(db_session, corps["id"])
    assert enregistree is not None
    assert enregistree.id_categorie == first_category.id


def test_facture_sur_pole_local_sans_categorie_refusee(
    client: TestClient, benevole_user, auth_headers, local_pole
):
    reponse = client.post(
        "/api/v1/invoices",
        data={"id_pole": str(local_pole.id), "fournisseur": "Metro"},
        files=_fichier(),
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 422, reponse.text


# ---- Nom du fichier transmis au comptable -----------------------------------


def test_le_fichier_comptable_porte_la_categorie(
    client: TestClient, benevole_user, auth_headers, local_pole, first_category, db_session
):
    """Sans evenement, c'est la categorie qui dit au comptable a quoi la piece
    se rattache : « Local_Courses_2026-08-12.pdf » s'impute sans ouvrir le PDF."""
    reponse = client.post(
        "/api/v1/expenses",
        data={
            "date_depense": "2026-08-12",
            "montant": "24.90",
            "fournisseur": "Metro",
            "id_pole": str(local_pole.id),
            "id_categorie": str(first_category.id),
        },
        files=_fichier(),
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 201, reponse.text

    from app.db.models import OutboundEmail
    from app.services import naming

    envois = db_session.query(OutboundEmail).all()
    assert envois, "aucun envoi comptable prepare"
    pieces = " ".join(e.attachments or "" for e in envois)
    attendu = (
        f"{naming.slugify_component(local_pole.nom)}_"
        f"{naming.slugify_component(first_category.nom)}_2026-08-12.pdf"
    )
    # La date de la depense date le fichier, faute de date d'evenement.
    assert attendu in pieces, f"attendu {attendu} dans {pieces}"
