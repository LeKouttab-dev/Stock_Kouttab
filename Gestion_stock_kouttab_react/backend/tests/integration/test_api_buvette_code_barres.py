"""Relier un code-barres a un produit buvette existant, sans rien ecraser.

Les produits de la buvette viennent de HelloAsso et n'ont jamais ete scannes.
Scanner un code inconnu propose de le relier a un produit existant : le PATCH
ne porte alors que `{barcode}`. Proprietes verrouillees ici :

 1. **Relier un code ne touche a rien d'autre** : ni photo, ni nom, ni prix, et
    `edite_manuellement` reste faux (sinon la synchro HelloAsso cesserait de
    mettre a jour un produit qu'on a seulement scanne).
 2. **Un code deja pris est refuse explicitement** (409), le message nomme le
    produit qui le porte.
 3. **`null` ou "" retire le code.**
 4. **La synchro HelloAsso ne vide jamais le code-barres.**
 5. **La liste des produits expose `barcode`.**
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct


pytestmark = pytest.mark.integration

CODE = "3017620422003"
AUTRE_CODE = "8000500310427"
PHOTO_HELLOASSO = "https://cdn.helloasso.com/img/kinder-bueno.jpg"


@pytest.fixture()
def produit_helloasso(db_session) -> BuvetteProduct:
    p = BuvetteProduct(
        helloasso_tier_id=424242,
        name="KINDER - BUENO",
        description="Barre chocolatee",
        price_cents=150,
        quantity=10,
        seuil_alerte=5,
        emoji="🍫",
        image_url=PHOTO_HELLOASSO,
        is_active=True,
        caisse_category="sucre_sale",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def autre_produit(db_session) -> BuvetteProduct:
    p = BuvetteProduct(
        name="Canette de soda",
        price_cents=120,
        quantity=4,
        seuil_alerte=5,
        barcode=AUTRE_CODE,
        is_active=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _patch(client, headers, product_id, corps):
    return client.patch(
        f"/api/v1/buvette/products/{product_id}", json=corps, headers=headers
    )


def test_relier_un_code_ne_touche_ni_photo_ni_nom_ni_prix(
    client: TestClient, admin_benevoles_user, auth_headers, produit_helloasso, db_session
):
    reponse = _patch(
        client, auth_headers(admin_benevoles_user), produit_helloasso.id, {"barcode": CODE}
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["barcode"] == CODE
    assert corps["name"] == "KINDER - BUENO"
    assert corps["price_cents"] == 150
    assert corps["image_url"] == PHOTO_HELLOASSO
    assert corps["description"] == "Barre chocolatee"
    assert corps["caisse_category"] == "sucre_sale"
    assert corps["quantity"] == 10
    assert corps["edite_manuellement"] is False

    db_session.expire_all()
    en_base = db_session.get(BuvetteProduct, produit_helloasso.id)
    assert en_base.barcode == CODE
    assert en_base.image_url == PHOTO_HELLOASSO
    assert en_base.edite_manuellement is False


def test_le_code_relie_retrouve_le_produit_au_scan_suivant(
    client: TestClient, admin_benevoles_user, auth_headers, produit_helloasso
):
    headers = auth_headers(admin_benevoles_user)
    assert _patch(client, headers, produit_helloasso.id, {"barcode": CODE}).status_code == 200
    reponse = client.get(f"/api/v1/buvette/products/by-barcode/{CODE}", headers=headers)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["id"] == produit_helloasso.id


def test_un_code_deja_pris_est_refuse_en_nommant_le_produit(
    client: TestClient,
    admin_benevoles_user,
    auth_headers,
    produit_helloasso,
    autre_produit,
    db_session,
):
    reponse = _patch(
        client,
        auth_headers(admin_benevoles_user),
        produit_helloasso.id,
        {"barcode": AUTRE_CODE},
    )
    assert reponse.status_code == 409, reponse.text
    corps = reponse.json()
    assert corps["message"] == "Ce code-barres est déjà associé à Canette de soda."
    assert corps["extras"]["existing_product_id"] == autre_produit.id

    db_session.expire_all()
    assert db_session.get(BuvetteProduct, produit_helloasso.id).barcode is None
    assert db_session.get(BuvetteProduct, autre_produit.id).barcode == AUTRE_CODE


def test_renvoyer_son_propre_code_est_accepte(
    client: TestClient, admin_benevoles_user, auth_headers, autre_produit
):
    reponse = _patch(
        client, auth_headers(admin_benevoles_user), autre_produit.id, {"barcode": AUTRE_CODE}
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["barcode"] == AUTRE_CODE


@pytest.mark.parametrize("valeur", [None, "", "   "])
def test_null_ou_vide_retire_le_code(
    client: TestClient, admin_benevoles_user, auth_headers, autre_produit, valeur
):
    reponse = _patch(
        client, auth_headers(admin_benevoles_user), autre_produit.id, {"barcode": valeur}
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["barcode"] is None
    assert reponse.json()["edite_manuellement"] is False


def test_un_code_invalide_est_refuse(
    client: TestClient, admin_benevoles_user, auth_headers, produit_helloasso
):
    reponse = _patch(
        client, auth_headers(admin_benevoles_user), produit_helloasso.id, {"barcode": "abc"}
    )
    assert reponse.status_code == 422, reponse.text


def test_la_liste_des_produits_expose_le_code_barres(
    client: TestClient, admin_benevoles_user, auth_headers, produit_helloasso, autre_produit
):
    reponse = client.get(
        "/api/v1/buvette/products", headers=auth_headers(admin_benevoles_user)
    )
    assert reponse.status_code == 200, reponse.text
    par_id = {p["id"]: p for p in reponse.json()}
    assert "barcode" in par_id[produit_helloasso.id]
    assert par_id[produit_helloasso.id]["barcode"] is None
    assert par_id[autre_produit.id]["barcode"] == AUTRE_CODE


@pytest.mark.parametrize("edite_manuellement", [False, True])
def test_la_synchro_helloasso_ne_vide_jamais_le_code_barres(
    db_session, produit_helloasso, edite_manuellement
):
    produit_helloasso.barcode = CODE
    produit_helloasso.edite_manuellement = edite_manuellement
    db_session.commit()

    tiers = [
        {
            "id": 424242,
            "label": "KINDER - BUENO (nouveau libelle)",
            "description": "Barre",
            "price": 160,
            "picture": {"publicUrl": "https://cdn.helloasso.com/img/autre.jpg"},
        }
    ]
    resultat = buvette_crud.sync_from_helloasso(db_session, tiers)
    assert not resultat.errors

    db_session.expire_all()
    en_base = db_session.get(BuvetteProduct, produit_helloasso.id)
    assert en_base.barcode == CODE
