"""Menu de la tablette : ordre des produits par onglet et étiquettes (10/10/2026).

La tablette garde l'ordre du catalogue qu'elle reçoit : trier le catalogue
côté serveur suffit à ranger son menu.

- `GET /buvette/caisse/catalogue` : onglet, puis `ordre_caisse` (non rangés en
  fin), puis nom ; chaque produit porte `etiquette: {type, texte} | null`.
- `PUT /buvette/caisse/ordre` : réécrit `ordre_caisse` de 1 à n pour un onglet.
- `GET /buvette/caisse/ordre-par-ventes` : ordre proposé, non enregistré.
- `PATCH /buvette/products/{id}` : `etiquette_type` / `etiquette_texte`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct, BuvetteSale

pytestmark = pytest.mark.integration

CLE = "cle-de-test-de-la-caisse-au-moins-32-caracteres"
API = "/api/v1/buvette"


@pytest.fixture(autouse=True)
def _caisse_activee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", CLE)


@pytest.fixture()
def admin(client_authenticated_as, admin_benevoles_user) -> TestClient:
    return client_authenticated_as(admin_benevoles_user)


def _creer(admin: TestClient, nom: str, categorie: str | None = "boissons", **extra) -> dict:
    reponse = admin.post(
        f"{API}/products",
        json={
            "name": nom,
            "price_cents": 150,
            "quantity": 20,
            "caisse_category": categorie,
            **extra,
        },
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _catalogue(client: TestClient) -> list[dict]:
    reponse = client.get(f"{API}/caisse/catalogue", headers={"X-Caisse-Key": CLE})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["products"]


def _ids_du_catalogue(client: TestClient, ids: list[int]) -> list[int]:
    return [p["id"] for p in _catalogue(client) if p["id"] in ids]


def _vendre(client: TestClient, produit: dict, quantite: int) -> None:
    corps = {
        "transaction_id": str(uuid.uuid4()),
        "sumup_tx_code": None,
        "total_cents": quantite * produit["price_cents"],
        "sold_at": datetime.now(buvette_crud.PARIS).isoformat(),
        "lines": [
            {
                "product_id": produit["id"],
                "name": produit["name"],
                "quantity": quantite,
                "unit_price_cents": produit["price_cents"],
            }
        ],
    }
    reponse = client.post(f"{API}/caisse/ventes", json=corps, headers={"X-Caisse-Key": CLE})
    assert reponse.status_code == 201, reponse.text


# ---------------------------------------------------------------------------
# Tri du catalogue
# ---------------------------------------------------------------------------


def test_le_catalogue_suit_l_ordre_choisi_puis_le_nom(admin, client: TestClient) -> None:
    """Rangés d'abord (1..n), puis les non rangés par nom ; onglets séparés."""
    a = _creer(admin, "Zz Eau")
    b = _creer(admin, "Aa Jus")
    c = _creer(admin, "Mm Soda")
    d = _creer(admin, "Bb Thé")
    cafe = _creer(admin, "Aa Café", "cafe")
    ids = [a["id"], b["id"], c["id"], d["id"], cafe["id"]]

    # Avant tout rangement : ordre alphabétique (comportement d'avant).
    boissons = [i for i in _ids_du_catalogue(client, ids) if i != cafe["id"]]
    assert boissons == [b["id"], d["id"], c["id"], a["id"]]

    reponse = admin.put(
        f"{API}/caisse/ordre", json={"categorie": "boissons", "product_ids": [a["id"], c["id"]]}
    )
    assert reponse.status_code == 200, reponse.text

    # a et c rangés en tête ; b et d, absents de la liste, suivent dans leur ordre.
    boissons = [i for i in _ids_du_catalogue(client, ids) if i != cafe["id"]]
    assert boissons == [a["id"], c["id"], b["id"], d["id"]]
    # L'onglet reste le premier critère (clé « boissons » avant « cafe »).
    complet = _ids_du_catalogue(client, ids)
    assert complet.index(cafe["id"]) > complet.index(d["id"])


def test_un_produit_ajoute_apres_le_rangement_passe_en_fin(admin, client: TestClient) -> None:
    a = _creer(admin, "Yy Eau")
    b = _creer(admin, "Xx Jus")
    admin.put(
        f"{API}/caisse/ordre", json={"categorie": "boissons", "product_ids": [a["id"], b["id"]]}
    )
    nouveau = _creer(admin, "Aa Nouveau")

    assert _ids_du_catalogue(client, [a["id"], b["id"], nouveau["id"]]) == [
        a["id"],
        b["id"],
        nouveau["id"],
    ]


def test_changer_d_onglet_efface_le_rang(admin, db_session: Session) -> None:
    a = _creer(admin, "Eau")
    admin.put(f"{API}/caisse/ordre", json={"categorie": "boissons", "product_ids": [a["id"]]})
    reponse = admin.patch(f"{API}/products/{a['id']}", json={"caisse_category": "epicerie"})
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["ordre_caisse"] is None


def test_le_tri_du_catalogue_compile_pour_mariadb() -> None:
    """Pas de `NULLS LAST` : MariaDB le refuse (cf. test_sql_dialect_compat)."""
    stmt = select(BuvetteProduct).order_by(*buvette_crud._ORDRE_ONGLET)
    sql = str(stmt.compile(dialect=mysql.dialect())).upper()
    assert "NULLS" not in sql


# ---------------------------------------------------------------------------
# PUT /caisse/ordre
# ---------------------------------------------------------------------------


def test_l_ordre_reecrit_les_rangs_de_1_a_n(admin, db_session: Session) -> None:
    a, b, c = (_creer(admin, f"P{i}") for i in range(3))
    reponse = admin.put(
        f"{API}/caisse/ordre",
        json={"categorie": "boissons", "product_ids": [c["id"], a["id"], b["id"]]},
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["categorie"] == "boissons"
    rangs = {p["product_id"]: p["ordre_caisse"] for p in corps["produits"]}
    assert (rangs[c["id"]], rangs[a["id"]], rangs[b["id"]]) == (1, 2, 3)
    assert sorted(rangs.values()) == list(range(1, len(rangs) + 1))


def test_un_produit_d_un_autre_onglet_est_refuse(admin, db_session: Session) -> None:
    a = _creer(admin, "Eau")
    autre = _creer(admin, "Chips", "sucre_sale")
    reponse = admin.put(
        f"{API}/caisse/ordre", json={"categorie": "boissons", "product_ids": [a["id"], autre["id"]]}
    )
    assert reponse.status_code == 422
    db_session.expire_all()
    assert db_session.get(BuvetteProduct, a["id"]).ordre_caisse is None


def test_un_doublon_ou_un_onglet_inconnu_est_refuse(admin) -> None:
    a = _creer(admin, "Eau")
    doublon = admin.put(
        f"{API}/caisse/ordre", json={"categorie": "boissons", "product_ids": [a["id"], a["id"]]}
    )
    assert doublon.status_code == 422
    inconnu = admin.put(f"{API}/caisse/ordre", json={"categorie": "glaces", "product_ids": []})
    assert inconnu.status_code == 422


def test_ranger_le_menu_est_reserve_a_la_gestion(
    client_authenticated_as, compta_user, admin_stock_user, admin
) -> None:
    a = _creer(admin, "Eau")
    corps = {"categorie": "boissons", "product_ids": [a["id"]]}
    assert (
        client_authenticated_as(compta_user).put(f"{API}/caisse/ordre", json=corps).status_code
        == 403
    )
    assert (
        client_authenticated_as(admin_stock_user).put(f"{API}/caisse/ordre", json=corps).status_code
        == 200
    )


# ---------------------------------------------------------------------------
# GET /caisse/ordre-par-ventes
# ---------------------------------------------------------------------------


def test_l_ordre_par_ventes_propose_sans_enregistrer(
    admin, client: TestClient, db_session: Session
) -> None:
    peu = _creer(admin, "Aa Peu vendu")
    beaucoup = _creer(admin, "Zz Beaucoup vendu")
    jamais = _creer(admin, "Mm Jamais vendu")
    _vendre(client, peu, 1)
    _vendre(client, beaucoup, 3)
    # Une vente HelloAsso compte aussi (toutes sources).
    db_session.add(
        BuvetteSale(
            source="helloasso",
            buvette_product_id=beaucoup["id"],
            product_name_snapshot=beaucoup["name"],
            quantity_sold=2,
            amount_cents=300,
            sold_at=datetime.now(buvette_crud.PARIS).replace(tzinfo=None),
        )
    )
    # Une vente trop ancienne pour la période ne compte pas.
    db_session.add(
        BuvetteSale(
            source="helloasso",
            buvette_product_id=jamais["id"],
            product_name_snapshot=jamais["name"],
            quantity_sold=50,
            amount_cents=7500,
            sold_at=datetime.now(buvette_crud.PARIS).replace(tzinfo=None) - timedelta(days=40),
        )
    )
    db_session.commit()

    reponse = admin.get(f"{API}/caisse/ordre-par-ventes", params={"categorie": "boissons"})
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["jours"] == 30
    mes = [
        p for p in corps["produits"] if p["product_id"] in (peu["id"], beaucoup["id"], jamais["id"])
    ]
    assert [p["product_id"] for p in mes] == [beaucoup["id"], peu["id"], jamais["id"]]
    assert [p["quantite_vendue"] for p in mes] == [5, 1, 0]

    # Sur 90 jours, la vente ancienne remonte « jamais » en tête.
    long = admin.get(
        f"{API}/caisse/ordre-par-ventes", params={"categorie": "boissons", "jours": 90}
    )
    premiers = [
        p["product_id"]
        for p in long.json()["produits"]
        if p["product_id"] in (peu["id"], beaucoup["id"], jamais["id"])
    ]
    assert premiers[0] == jamais["id"]

    # Rien n'a été enregistré.
    db_session.expire_all()
    assert db_session.get(BuvetteProduct, beaucoup["id"]).ordre_caisse is None


def test_l_ordre_par_ventes_valide_ses_parametres(admin) -> None:
    assert (
        admin.get(f"{API}/caisse/ordre-par-ventes", params={"categorie": "glaces"}).status_code
        == 422
    )
    assert (
        admin.get(
            f"{API}/caisse/ordre-par-ventes", params={"categorie": "cafe", "jours": 0}
        ).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# Étiquettes
# ---------------------------------------------------------------------------


def _etiquette_au_catalogue(client: TestClient, produit_id: int):
    return next(p for p in _catalogue(client) if p["id"] == produit_id)["etiquette"]


def test_sans_etiquette_le_catalogue_renvoie_null(admin, client: TestClient) -> None:
    a = _creer(admin, "Eau")
    assert _etiquette_au_catalogue(client, a["id"]) is None


@pytest.mark.parametrize(
    ("type_", "texte"),
    [
        ("nouveaute", "Nouveauté"),
        ("edition_limitee", "Édition limitée"),
        ("derniers", "Derniers exemplaires"),
        ("coup_de_coeur", "Coup de cœur"),
        ("promo", "Promo"),
    ],
)
def test_une_etiquette_fixe_porte_son_libelle(admin, client: TestClient, type_, texte) -> None:
    a = _creer(admin, "Eau")
    # Le texte envoyé avec un type fixe est ignoré.
    reponse = admin.patch(
        f"{API}/products/{a['id']}", json={"etiquette_type": type_, "etiquette_texte": "ignoré"}
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["etiquette_type"] == type_
    assert reponse.json()["etiquette_texte"] is None
    assert _etiquette_au_catalogue(client, a["id"]) == {"type": type_, "texte": texte}


def test_une_etiquette_libre_est_nettoyee_et_bornee(admin, client: TestClient) -> None:
    a = _creer(admin, "Eau")
    reponse = admin.patch(
        f"{API}/products/{a['id']}",
        json={"etiquette_type": "libre", "etiquette_texte": "  Fait   maison\u200b "},
    )
    assert reponse.status_code == 200, reponse.text
    assert _etiquette_au_catalogue(client, a["id"]) == {"type": "libre", "texte": "Fait maison"}

    # 20 caractères : accepté ; 21 : refusé, l'étiquette précédente reste.
    assert (
        admin.patch(
            f"{API}/products/{a['id']}",
            json={"etiquette_type": "libre", "etiquette_texte": "x" * 20},
        ).status_code
        == 200
    )
    trop_long = admin.patch(
        f"{API}/products/{a['id']}", json={"etiquette_type": "libre", "etiquette_texte": "x" * 21}
    )
    assert trop_long.status_code == 422
    assert _etiquette_au_catalogue(client, a["id"]) == {"type": "libre", "texte": "x" * 20}

    vide = admin.patch(
        f"{API}/products/{a['id']}", json={"etiquette_type": "libre", "etiquette_texte": "  "}
    )
    assert vide.status_code == 422
    sans_texte = admin.patch(f"{API}/products/{a['id']}", json={"etiquette_type": "libre"})
    assert sans_texte.status_code == 422


def test_retirer_l_etiquette_et_type_inconnu(admin, client: TestClient) -> None:
    a = _creer(admin, "Eau")
    admin.patch(f"{API}/products/{a['id']}", json={"etiquette_type": "promo"})
    reponse = admin.patch(f"{API}/products/{a['id']}", json={"etiquette_type": None})
    assert reponse.status_code == 200
    assert reponse.json()["etiquette_type"] is None
    assert _etiquette_au_catalogue(client, a["id"]) is None

    inconnu = admin.patch(f"{API}/products/{a['id']}", json={"etiquette_type": "soldes"})
    assert inconnu.status_code == 422


def test_l_etiquette_ne_marque_pas_edite_manuellement(admin) -> None:
    """Ce n'est pas un champ HelloAsso : la synchro doit continuer à tout mettre à jour."""
    a = _creer(admin, "Eau")
    reponse = admin.patch(f"{API}/products/{a['id']}", json={"etiquette_type": "nouveaute"})
    assert reponse.json()["edite_manuellement"] is False
