"""End-to-end tests for /stock endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.crud import stock as stock_crud


pytestmark = pytest.mark.integration


def _name(prefix: str = "art") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _seed_item(db, **kwargs):
    base = dict(
        nom=_name(),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=10,
        seuil_alerte=2,
    )
    base.update(kwargs)
    return stock_crud.create_item(db, **base)


def test_get_items_returns_list(
    client: TestClient, benevole_user, auth_headers, db_session
) -> None:
    _seed_item(db_session)
    resp = client.get("/api/v1/stock/items", headers=auth_headers(benevole_user))
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_create_item_as_benevole_forbidden(
    client: TestClient, benevole_user, auth_headers
) -> None:
    payload = {
        "nom": _name("ben"),
        "categorie": "Nourriture",
        "sous_categorie": None,
        "quantite": 10,
        "seuil_alerte": 2,
        "emoji": "🍔",
    }
    resp = client.post(
        "/api/v1/stock/items", json=payload, headers=auth_headers(benevole_user)
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "PERM_2002"


def test_create_item_as_admin_benevoles_ok(
    client: TestClient, admin_benevoles_user, auth_headers
) -> None:
    payload = {
        "nom": _name("ab"),
        "categorie": "Nourriture",
        "sous_categorie": None,
        "quantite": 10,
        "seuil_alerte": 2,
        "emoji": "🍔",
    }
    resp = client.post(
        "/api/v1/stock/items",
        json=payload,
        headers=auth_headers(admin_benevoles_user),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["nom"] == payload["nom"]


def test_create_item_duplicate_name_returns_conflict(
    client: TestClient, admin_benevoles_user, auth_headers
) -> None:
    payload = {
        "nom": _name("dup"),
        "categorie": "Nourriture",
        "sous_categorie": None,
        "quantite": 10,
        "seuil_alerte": 2,
        "emoji": "🍔",
    }
    r1 = client.post(
        "/api/v1/stock/items", json=payload, headers=auth_headers(admin_benevoles_user)
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/stock/items", json=payload, headers=auth_headers(admin_benevoles_user)
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "CONF_4002"


def test_patch_item_quantity_works_for_admin(
    client: TestClient, admin_benevoles_user, auth_headers, db_session
) -> None:
    item = _seed_item(db_session, quantite=20, seuil_alerte=5)
    resp = client.patch(
        f"/api/v1/stock/items/{item.id}",
        json={"quantite": 30},
        headers=auth_headers(admin_benevoles_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quantite"] == 30


def test_delete_item_as_admin(
    client: TestClient, admin_benevoles_user, auth_headers, db_session
) -> None:
    item = _seed_item(db_session)
    resp = client.delete(
        f"/api/v1/stock/items/{item.id}",
        headers=auth_headers(admin_benevoles_user),
    )
    assert resp.status_code == 200, resp.text


def test_get_categories(client: TestClient, benevole_user, auth_headers) -> None:
    resp = client.get(
        "/api/v1/stock/categories", headers=auth_headers(benevole_user)
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_create_patch_delete_category(
    client: TestClient, admin_benevoles_user, auth_headers
) -> None:
    name = f"Cat_{uuid.uuid4().hex[:6]}"
    new_name = f"{name}_new"
    h = auth_headers(admin_benevoles_user)
    r1 = client.post(
        "/api/v1/stock/categories",
        json={"nom": name, "is_default": False},
        headers=h,
    )
    assert r1.status_code == 201, r1.text
    r2 = client.patch(
        f"/api/v1/stock/categories/{name}",
        json={"new_name": new_name},
        headers=h,
    )
    assert r2.status_code == 200, r2.text
    r3 = client.delete(f"/api/v1/stock/categories/{new_name}", headers=h)
    assert r3.status_code == 200, r3.text


def test_create_modification_request_as_benevole(
    client: TestClient, benevole_user, auth_headers, db_session
) -> None:
    item = _seed_item(db_session, quantite=10, seuil_alerte=2)
    resp = client.post(
        "/api/v1/stock/modifications",
        json={
            "id_stock": item.id,
            "quantite_demandee": 5,
            "commentaires": "Besoin de descendre.",
        },
        headers=auth_headers(benevole_user),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "En attente"
    assert body["quantite_demandee"] == 5


def test_approve_modification_updates_stock_and_status(
    client: TestClient, benevole_user, admin_benevoles_user, auth_headers, db_session
) -> None:
    item = _seed_item(db_session, quantite=10, seuil_alerte=2)
    # Create a modification as Benevole.
    create_resp = client.post(
        "/api/v1/stock/modifications",
        json={
            "id_stock": item.id,
            "quantite_demandee": 7,
            "commentaires": None,
        },
        headers=auth_headers(benevole_user),
    )
    assert create_resp.status_code == 201, create_resp.text
    modif_id = create_resp.json()["id"]

    # Approve as AdminBenevoles.
    approve_resp = client.post(
        f"/api/v1/stock/modifications/{modif_id}/approve",
        headers=auth_headers(admin_benevoles_user),
    )
    assert approve_resp.status_code == 200, approve_resp.text
    body = approve_resp.json()
    assert body["status"] in ("Approuvée", "Approuvee")
    db_session.refresh(item)
    assert item.quantite == 7
