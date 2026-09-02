"""End-to-end tests for /expenses endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.crud import expense as expense_crud


pytestmark = pytest.mark.integration


def _create_expense_payload(montant: str = "12.50") -> dict:
    """Depot minimal valide.

    Fournisseur, pole, categorie, evenement et date d'evenement sont
    obligatoires : ils composent le nom du justificatif transmis au comptable.
    `id_pole` vaut 1, l'un des poles crees par defaut au demarrage de
    l'application ; `id_categorie` vaut 1 pour la meme raison (« Courses »).

    La categorie est demandee **meme sous un pole evenementiel** : l'evenement
    dit a quelle occasion la depense a eu lieu, elle dit ce qui a ete achete.
    """
    return {
        "date_depense": "2024-04-01",
        "montant": montant,
        "fournisseur": "Carrefour",
        "id_pole": "1",
        "id_categorie": "1",
        "evenement_libre": "Repas d'equipe",
        "date_evenement": "2024-04-01",
        "nature_charge": "Achat",
        "commentaires": "Test",
        "remboursement_deja_emis": "0",
        "remise": "0",
    }


def _create_expense_via_api(client, user, headers_factory, **overrides) -> int:
    data = _create_expense_payload()
    data.update(overrides)
    resp = client.post(
        "/api/v1/expenses", data=data, headers=headers_factory(user)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_expense_as_benevole_returns_201(
    client: TestClient, benevole_user, auth_headers
) -> None:
    expense_id = _create_expense_via_api(client, benevole_user, auth_headers)
    assert expense_id > 0


def test_get_my_expenses_returns_only_own(
    client: TestClient, benevole_user, auth_headers
) -> None:
    _create_expense_via_api(client, benevole_user, auth_headers)
    resp = client.get(
        "/api/v1/expenses/me", headers=auth_headers(benevole_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert all(e["id_user"] == benevole_user.id for e in body)


def test_get_all_expenses_as_benevole_forbidden(
    client: TestClient, benevole_user, auth_headers
) -> None:
    resp = client.get("/api/v1/expenses", headers=auth_headers(benevole_user))
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "PERM_2002"


def test_get_all_expenses_as_compta_returns_list(
    client: TestClient, compta_user, benevole_user, auth_headers
) -> None:
    _create_expense_via_api(client, benevole_user, auth_headers)
    resp = client.get("/api/v1/expenses", headers=auth_headers(compta_user))
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_update_own_expense_when_pending_ok(
    client: TestClient, benevole_user, auth_headers
) -> None:
    expense_id = _create_expense_via_api(client, benevole_user, auth_headers)
    resp = client.patch(
        f"/api/v1/expenses/{expense_id}",
        json={"montant": "99.00"},
        headers=auth_headers(benevole_user),
    )
    assert resp.status_code == 200, resp.text
    assert float(resp.json()["montant"]) == 99.0


def test_update_own_expense_when_approved_returns_conflict(
    client: TestClient, benevole_user, auth_headers, db_session
) -> None:
    expense_id = _create_expense_via_api(client, benevole_user, auth_headers)
    # Force status outside the editable range.
    expense = expense_crud.get_expense(db_session, expense_id)
    expense.status = "Approuvée"
    db_session.commit()
    resp = client.patch(
        f"/api/v1/expenses/{expense_id}",
        json={"montant": "1.00"},
        headers=auth_headers(benevole_user),
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "CONF_4005"


def test_validate_expense_by_compta_changes_status(
    client: TestClient, benevole_user, compta_user, auth_headers
) -> None:
    expense_id = _create_expense_via_api(client, benevole_user, auth_headers)
    resp = client.patch(
        f"/api/v1/expenses/{expense_id}/validate",
        json={"status": "Approuvée", "commentaires_compta": "OK"},
        headers=auth_headers(compta_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "Approuvée"
    assert body["commentaires_compta"] == "OK"


def test_un_depot_sans_rib_est_refuse_et_ne_cree_rien(
    client: TestClient, benevole_sans_rib, auth_headers, db_session
) -> None:
    """La comptabilite rembourse par virement : sans RIB, elle ne peut pas payer.

    Elle le reclamait par messages prives, exactement le travers que le RIB en
    document devait supprimer. Le refus tombe **avant toute ecriture** : une note
    creee puis abandonnee laisserait une ligne que personne ne traite.
    """
    reponse = client.post(
        "/api/v1/expenses",
        data=_create_expense_payload(),
        headers=auth_headers(benevole_sans_rib),
    )

    assert reponse.status_code == 422
    assert reponse.json()["code"] == "VAL_5012"
    assert expense_crud.list_expenses_for_user(db_session, benevole_sans_rib.id) == []


def test_un_rib_encore_en_image_ne_vaut_pas_depot(
    client: TestClient, benevole_user, auth_headers, db_session
) -> None:
    """Le controle porte sur le format, pas seulement sur la presence.

    Un compte dont le RIB serait reste une photo — migration non passee, depot
    anterieur — doit s'entendre dire de le redeposer, plutot que d'envoyer a la
    comptabilite une piece qu'elle refuse.
    """
    benevole_user.rib_document_type = "image/png"
    db_session.commit()

    reponse = client.post(
        "/api/v1/expenses",
        data=_create_expense_payload(),
        headers=auth_headers(benevole_user),
    )

    assert reponse.status_code == 422
    assert reponse.json()["code"] == "VAL_5012"
