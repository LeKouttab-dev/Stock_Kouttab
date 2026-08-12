"""Les justificatifs vivent EN BASE, et pas seulement sur le disque du VPS.

C'est tout l'enjeu : la base est sauvegardee par O2Switch, le disque du VPS ne
l'est pas. Une piece qui n'existerait qu'en local disparaitrait avec la machine,
et il s'agit de documents a conserver plusieurs annees.

Le test decisif est `test_le_justificatif_survit_a_la_perte_du_disque` : il
efface le fichier local et verifie que le telechargement fonctionne toujours.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db.models import InvoiceFile


pytestmark = pytest.mark.integration


def _image() -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (60, 40), (12, 90, 200)).save(tampon, format="JPEG")
    return tampon.getvalue()


def _deposer(client, user, auth_headers, local_pole, first_category, octets=None):
    contenu = octets or _image()
    reponse = client.post(
        "/api/v1/invoices",
        data={
            "id_pole": str(local_pole.id),
            "id_categorie": str(first_category.id),
            "fournisseur": "Metro",
        },
        files={"files": ("ticket.jpg", io.BytesIO(contenu), "image/jpeg")},
        headers=auth_headers(user),
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json(), contenu


def test_le_depot_ecrit_le_contenu_en_base(
    client: TestClient, benevole_user, auth_headers, db_session, local_pole, first_category
):
    facture, octets = _deposer(
        client, benevole_user, auth_headers, local_pole, first_category
    )

    ligne = db_session.query(InvoiceFile).filter_by(id_facture=facture["id"]).one()
    assert ligne.contenu == octets, "le justificatif doit etre stocke en base"
    # Le chemin reste renseigne : cache local et trace de l'origine.
    assert ligne.chemin_fichier


def test_le_justificatif_survit_a_la_perte_du_disque(
    client: TestClient, benevole_user, auth_headers, db_session, local_pole, first_category
):
    """LE test : on simule la disparition du volume, la piece reste servie."""
    facture, octets = _deposer(
        client, benevole_user, auth_headers, local_pole, first_category
    )
    ligne = db_session.query(InvoiceFile).filter_by(id_facture=facture["id"]).one()

    Path(ligne.chemin_fichier).unlink()
    assert not Path(ligne.chemin_fichier).exists()

    reponse = client.get(
        f"/api/v1/invoices/{facture['id']}/files/{ligne.id}",
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.content == octets


def test_le_telechargement_rend_les_octets_exacts(
    client: TestClient, benevole_user, auth_headers, db_session, local_pole, first_category
):
    facture, octets = _deposer(
        client, benevole_user, auth_headers, local_pole, first_category
    )
    ligne = db_session.query(InvoiceFile).filter_by(id_facture=facture["id"]).one()

    reponse = client.get(
        f"/api/v1/invoices/{facture['id']}/files/{ligne.id}",
        headers=auth_headers(benevole_user),
    )

    assert reponse.content == octets
    assert reponse.headers["content-type"].startswith("image/jpeg")
    assert "ticket.jpg" in reponse.headers.get("content-disposition", "")


def test_une_piece_ancienne_sans_contenu_reste_lisible(
    client: TestClient, benevole_user, auth_headers, db_session, local_pole, first_category
):
    """Repli sur le disque : les depots anterieurs a la migration ont une
    colonne vide, et doivent continuer de se telecharger."""
    facture, octets = _deposer(
        client, benevole_user, auth_headers, local_pole, first_category
    )
    ligne = db_session.query(InvoiceFile).filter_by(id_facture=facture["id"]).one()
    ligne.contenu = None
    db_session.commit()

    reponse = client.get(
        f"/api/v1/invoices/{facture['id']}/files/{ligne.id}",
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 200
    assert reponse.content == octets


def test_une_piece_perdue_des_deux_cotes_est_signalee(
    client: TestClient, benevole_user, auth_headers, db_session, local_pole, first_category
):
    facture, _ = _deposer(client, benevole_user, auth_headers, local_pole, first_category)
    ligne = db_session.query(InvoiceFile).filter_by(id_facture=facture["id"]).one()
    Path(ligne.chemin_fichier).unlink()
    ligne.contenu = None
    db_session.commit()

    reponse = client.get(
        f"/api/v1/invoices/{facture['id']}/files/{ligne.id}",
        headers=auth_headers(benevole_user),
    )
    # 410 et non 404 : la piece a existe, la ligne la reference toujours. Le
    # code du projet (`FILE_PHYSICALLY_MISSING`) dit exactement cela.
    assert reponse.status_code == 410, reponse.text


def test_le_circuit_comptable_fonctionne_sans_le_disque(
    client: TestClient, benevole_user, compta_user, auth_headers, db_session,
    local_pole, first_category,
):
    """La conversion en PDF travaille sur un chemin : sans fichier local, elle
    doit rematerialiser la piece depuis la base plutot que d'echouer."""
    from app.db.models import OutboundEmail

    facture, _ = _deposer(client, benevole_user, auth_headers, local_pole, first_category)
    ligne = db_session.query(InvoiceFile).filter_by(id_facture=facture["id"]).one()
    Path(ligne.chemin_fichier).unlink()

    db_session.query(OutboundEmail).delete()
    db_session.commit()

    reponse = client.post(
        f"/api/v1/invoices/{facture['id']}/resend-compta-email",
        headers=auth_headers(compta_user),
    )

    assert reponse.status_code == 200, reponse.text
    envois = db_session.query(OutboundEmail).all()
    assert envois, "l'envoi comptable doit etre prepare malgre le disque vide"
    assert ".pdf" in (envois[0].attachments or "")


def test_le_contenu_n_est_pas_charge_en_listant(
    client: TestClient, benevole_user, auth_headers, local_pole, first_category
):
    """`deferred=True` : lister les factures ne doit pas rapatrier les octets de
    tous les justificatifs depuis une base distante."""
    _deposer(client, benevole_user, auth_headers, local_pole, first_category)

    reponse = client.get("/api/v1/invoices/me", headers=auth_headers(benevole_user))

    assert reponse.status_code == 200
    fichiers = reponse.json()[0].get("files") or []
    assert fichiers, "la facture doit lister sa piece"
    assert "contenu" not in fichiers[0], "le binaire n'a rien a faire dans la liste"
