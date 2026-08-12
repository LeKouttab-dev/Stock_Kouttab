"""Tickets de justificatif, de l'ouverture a la cloture.

Deux points de vigilance : un ticket porte le nom d'une personne et ce qu'on
lui reclame — un benevole ne doit voir que les siens ; et une piece rattachee
doit appartenir a celui a qui on l'a demandee, sinon la cloture prouve autre
chose que ce qu'elle pretend.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image


pytestmark = pytest.mark.integration


def _ouvrir(client, compta_user, auth_headers, benevole, **extra):
    return client.post(
        "/api/v1/tickets",
        json={"id_user": benevole.id, "libelle": "Facture Metro du 3 août", **extra},
        headers=auth_headers(compta_user),
    )


def _deposer_facture(client, user, auth_headers, local_pole, first_category):
    tampon = io.BytesIO()
    Image.new("RGB", (40, 20), (200, 30, 30)).save(tampon, format="JPEG")
    return client.post(
        "/api/v1/invoices",
        data={
            "id_pole": str(local_pole.id),
            "id_categorie": str(first_category.id),
            "fournisseur": "Metro",
        },
        files={"files": ("f.jpg", io.BytesIO(tampon.getvalue()), "image/jpeg")},
        headers=auth_headers(user),
    )


# ---- Cycle de vie -----------------------------------------------------------


def test_la_comptabilite_ouvre_un_ticket(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    reponse = _ouvrir(
        client, compta_user, auth_headers, benevole_user, montant_attendu="24.90"
    )
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert corps["statut"] == "ouvert"
    assert corps["id_user"] == benevole_user.id
    assert corps["user_full_name"]


def test_seul_le_libelle_est_exige(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    """La comptabilite ouvre un ticket avec ce qu'elle sait : exiger le montant
    exact reviendrait a ne jamais l'ouvrir."""
    reponse = _ouvrir(client, compta_user, auth_headers, benevole_user)
    assert reponse.status_code == 201, reponse.text
    assert reponse.json()["montant_attendu"] is None


def test_la_cloture_rattache_la_piece_recue(
    client: TestClient, compta_user, benevole_user, auth_headers, local_pole, first_category
):
    ticket = _ouvrir(client, compta_user, auth_headers, benevole_user).json()
    facture = _deposer_facture(
        client, benevole_user, auth_headers, local_pole, first_category
    ).json()

    reponse = client.post(
        f"/api/v1/tickets/{ticket['id']}/close",
        json={"id_facture": facture["id"]},
        headers=auth_headers(compta_user),
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["statut"] == "clos"
    assert reponse.json()["id_facture"] == facture["id"]


def test_une_facture_d_un_autre_benevole_est_refusee(
    client: TestClient, compta_user, benevole_user, super_admin_user, auth_headers,
    local_pole, first_category,
):
    """Rattacher la piece de quelqu'un d'autre ferait dire a la cloture le
    contraire de ce qui s'est passe."""
    ticket = _ouvrir(client, compta_user, auth_headers, benevole_user).json()
    facture = _deposer_facture(
        client, super_admin_user, auth_headers, local_pole, first_category
    ).json()

    reponse = client.post(
        f"/api/v1/tickets/{ticket['id']}/close",
        json={"id_facture": facture["id"]},
        headers=auth_headers(compta_user),
    )
    assert reponse.status_code == 422, reponse.text


def test_un_ticket_clos_ne_se_referme_pas(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    ticket = _ouvrir(client, compta_user, auth_headers, benevole_user).json()
    client.post(
        f"/api/v1/tickets/{ticket['id']}/close", json={}, headers=auth_headers(compta_user)
    )
    seconde = client.post(
        f"/api/v1/tickets/{ticket['id']}/close", json={}, headers=auth_headers(compta_user)
    )
    assert seconde.status_code == 409, seconde.text


def test_un_ticket_clos_ne_se_relance_plus(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    ticket = _ouvrir(client, compta_user, auth_headers, benevole_user).json()
    client.post(
        f"/api/v1/tickets/{ticket['id']}/close", json={}, headers=auth_headers(compta_user)
    )
    reponse = client.post(
        f"/api/v1/tickets/{ticket['id']}/remind", headers=auth_headers(compta_user)
    )
    assert reponse.status_code == 409, reponse.text


# ---- Droits -----------------------------------------------------------------


def test_un_benevole_ne_peut_pas_ouvrir_de_ticket(
    client: TestClient, benevole_user, auth_headers
):
    reponse = client.post(
        "/api/v1/tickets",
        json={"id_user": benevole_user.id, "libelle": "Auto-demande"},
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 403, reponse.text


def test_un_benevole_ne_voit_que_ce_qu_on_lui_demande(
    client: TestClient, compta_user, benevole_user, super_admin_user, auth_headers
):
    _ouvrir(client, compta_user, auth_headers, benevole_user, libelle="La mienne")
    _ouvrir(client, compta_user, auth_headers, super_admin_user, libelle="Celle d'un autre")

    miens = client.get("/api/v1/tickets/me", headers=auth_headers(benevole_user)).json()

    assert [t["libelle"] for t in miens] == ["La mienne"]


def test_la_liste_complete_est_reservee_a_la_comptabilite(
    client: TestClient, benevole_user, auth_headers
):
    reponse = client.get("/api/v1/tickets", headers=auth_headers(benevole_user))
    assert reponse.status_code == 403, reponse.text


# ---- Compteurs --------------------------------------------------------------


def test_le_ticket_ouvert_apparait_dans_les_rappels_du_benevole(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    _ouvrir(client, compta_user, auth_headers, benevole_user)

    resume = client.get(
        "/api/v1/notifications/summary", headers=auth_headers(benevole_user)
    ).json()
    assert resume["justificatifs_demandes"] == 1
    # Le compteur global reste l'affaire de la comptabilite.
    assert resume["tickets_ouverts"] == 0

    vue_compta = client.get(
        "/api/v1/notifications/summary", headers=auth_headers(compta_user)
    ).json()
    assert vue_compta["tickets_ouverts"] == 1


def test_la_cloture_fait_retomber_le_compteur(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    ticket = _ouvrir(client, compta_user, auth_headers, benevole_user).json()
    client.post(
        f"/api/v1/tickets/{ticket['id']}/close", json={}, headers=auth_headers(compta_user)
    )

    resume = client.get(
        "/api/v1/notifications/summary", headers=auth_headers(benevole_user)
    ).json()
    assert resume["justificatifs_demandes"] == 0


# ---- Destinataires ----------------------------------------------------------


def test_la_comptabilite_peut_lister_les_destinataires(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    """Le menu deroulant du formulaire etait vide : il interrogeait `GET /users`,
    reserve au Super Admin, et la comptabilite recevait un refus."""
    reponse = client.get("/api/v1/tickets/destinataires", headers=auth_headers(compta_user))

    assert reponse.status_code == 200, reponse.text
    noms = {d["id"]: d["nom_complet"] for d in reponse.json()}
    assert benevole_user.id in noms
    assert noms[benevole_user.id]


def test_les_destinataires_ne_livrent_que_l_identite(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    """Ni adresse, ni role, ni telephone : ce menu n'en a pas besoin."""
    premier = client.get(
        "/api/v1/tickets/destinataires", headers=auth_headers(compta_user)
    ).json()[0]
    assert set(premier) == {"id", "nom_complet"}


def test_un_compte_en_attente_n_est_pas_proposable(
    client: TestClient, compta_user, pending_user, auth_headers
):
    """Lui reclamer une piece enverrait un courriel dans le vide."""
    ids = [
        d["id"]
        for d in client.get(
            "/api/v1/tickets/destinataires", headers=auth_headers(compta_user)
        ).json()
    ]
    assert pending_user.id not in ids


def test_un_benevole_ne_liste_pas_les_destinataires(
    client: TestClient, benevole_user, auth_headers
):
    reponse = client.get("/api/v1/tickets/destinataires", headers=auth_headers(benevole_user))
    assert reponse.status_code == 403, reponse.text
