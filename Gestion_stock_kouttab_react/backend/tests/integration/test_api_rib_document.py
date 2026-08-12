"""Depot et consultation du releve d'identite bancaire en document.

L'IBAN saisi sert au virement, ce document sert de preuve. C'est donc une piece
bancaire : ce qui compte ici n'est pas tant qu'elle se depose que **qu'elle ne se
recupere pas par quelqu'un d'autre**.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import Admin


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _deposer(client, contenu: bytes = PDF, nom: str = "rib.pdf", mime: str = "application/pdf"):
    return client.post("/api/v1/users/me/rib-document", files={"file": (nom, contenu, mime)})


def test_depot_puis_relecture_par_le_proprietaire(client_authenticated_as, benevole_user):
    client = client_authenticated_as(benevole_user)

    reponse = _deposer(client)
    assert reponse.status_code == 200
    # Le profil annonce la piece sans la transporter : l'ecran doit savoir
    # qu'elle existe, pas recevoir ses octets a chaque affichage.
    assert reponse.json()["rib_document_nom"] == "rib.pdf"

    telechargement = client.get("/api/v1/users/me/rib-document")
    assert telechargement.status_code == 200
    assert telechargement.content == PDF
    assert 'filename="rib.pdf"' in telechargement.headers["content-disposition"]


def test_la_compta_telecharge_le_rib_du_benevole(
    client_authenticated_as, benevole_user, compta_user
):
    _deposer(client_authenticated_as(benevole_user))

    reponse = client_authenticated_as(compta_user).get(
        f"/api/v1/users/{benevole_user.id}/rib-document"
    )
    assert reponse.status_code == 200
    assert reponse.content == PDF


def test_un_benevole_ne_lit_pas_le_rib_d_un_autre(
    client_authenticated_as, benevole_user, admin_benevoles_user
):
    """La regle qui compte.

    Deviner l'identifiant d'un collegue est trivial — ils se suivent. Sans ce
    controle, les coordonnees bancaires de tout l'institut se lisent en changeant
    un chiffre dans l'URL. `AdminBenevoles` n'y a pas droit non plus : la matrice
    reserve le RIB a la Compta et au Super Admin.
    """
    _deposer(client_authenticated_as(benevole_user))

    reponse = client_authenticated_as(admin_benevoles_user).get(
        f"/api/v1/users/{benevole_user.id}/rib-document"
    )
    assert reponse.status_code == 403


def test_suppression_par_le_proprietaire(client_authenticated_as, benevole_user, db_session):
    client = client_authenticated_as(benevole_user)
    _deposer(client)

    assert client.delete("/api/v1/users/me/rib-document").status_code == 200
    assert client.get("/api/v1/users/me/rib-document").status_code == 404

    ligne = db_session.execute(
        select(Admin).where(Admin.id == benevole_user.id)
    ).scalar_one()
    db_session.refresh(ligne)
    assert ligne.rib_document is None


def test_un_executable_deguise_en_pdf_est_refuse(client_authenticated_as, benevole_user):
    """La validation porte sur le contenu, jamais sur le nom ni sur l'en-tete.

    Les deux se falsifient depuis un navigateur.
    """
    reponse = _deposer(
        client_authenticated_as(benevole_user),
        contenu=b"MZ\x90\x00\x03" + b"\x00" * 200,
        nom="rib.pdf",
    )
    assert reponse.status_code == 415


def test_aucune_copie_sur_le_disque(client_authenticated_as, benevole_user, tmp_path, monkeypatch):
    """Le document ne vit qu'en base.

    Les justificatifs gardent un cache disque parce que la chaine comptable a
    besoin d'un chemin pour joindre un fichier a un courriel. Un RIB n'est jamais
    envoye : une copie de plus serait une surface de fuite de plus, dans un
    volume qui n'est pas sauvegarde.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    _deposer(client_authenticated_as(benevole_user))

    assert list(tmp_path.rglob("*.pdf")) == []
