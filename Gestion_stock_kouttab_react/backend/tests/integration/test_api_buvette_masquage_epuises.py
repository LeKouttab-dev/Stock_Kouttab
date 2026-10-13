"""Produits épuisés masqués de la tablette après 7 jours (13/10/2026).

- `epuise_depuis` est posé quand le stock tombe à 0 (vente, création à 0,
  inventaire) et effacé dès qu'il repasse au-dessus (réappro, inventaire).
- `GET /buvette/caisse/catalogue` retire un produit à 0 depuis plus de 7 jours,
  sauf les cafés. `is_active` n'est jamais touché : un produit masqué à la main
  le reste après un réappro.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct, est_masque_epuise

pytestmark = pytest.mark.integration

CLE = "cle-de-test-de-la-caisse-au-moins-32-caracteres"
API = "/api/v1/buvette"


@pytest.fixture(autouse=True)
def _caisse_activee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", CLE)


@pytest.fixture()
def admin(client_authenticated_as, admin_benevoles_user) -> TestClient:
    return client_authenticated_as(admin_benevoles_user)


def _creer(admin: TestClient, nom: str, quantite: int, categorie: str = "sucre_sale") -> dict:
    reponse = admin.post(
        f"{API}/products",
        json={"name": nom, "price_cents": 150, "quantity": quantite, "caisse_category": categorie},
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


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


def _au_catalogue(client: TestClient, produit_id: int) -> bool:
    reponse = client.get(f"{API}/caisse/catalogue", headers={"X-Caisse-Key": CLE})
    assert reponse.status_code == 200, reponse.text
    return any(p["id"] == produit_id for p in reponse.json()["products"])


def _vieillir(db: Session, produit_id: int, jours: int) -> None:
    """Fait remonter la date d'épuisement de `jours` jours."""
    db.execute(
        update(BuvetteProduct)
        .where(BuvetteProduct.id == produit_id)
        .values(epuise_depuis=datetime.utcnow() - timedelta(days=jours))
    )
    db.commit()


def _produit(db: Session, produit_id: int) -> BuvetteProduct:
    db.expire_all()
    return db.get(BuvetteProduct, produit_id)


def test_la_vente_du_dernier_article_pose_la_date(admin, client, db_session) -> None:
    produit = _creer(admin, "Twix", 2)
    assert produit["epuise_depuis"] is None

    _vendre(client, produit, 1)
    assert _produit(db_session, produit["id"]).epuise_depuis is None

    _vendre(client, produit, 1)
    assert _produit(db_session, produit["id"]).epuise_depuis is not None


def test_une_nouvelle_vente_a_zero_ne_repousse_pas_la_date(admin, client, db_session) -> None:
    produit = _creer(admin, "Mars", 1)
    _vendre(client, produit, 1)
    _vieillir(db_session, produit["id"], 3)
    avant = _produit(db_session, produit["id"]).epuise_depuis

    _vendre(client, produit, 1)  # vendu quand même : comptage en retard
    assert _produit(db_session, produit["id"]).epuise_depuis == avant


def test_cree_a_zero_compte_comme_epuise(admin, db_session) -> None:
    produit = _creer(admin, "Kinder", 0)
    assert _produit(db_session, produit["id"]).epuise_depuis is not None


def test_visible_a_6_jours_masque_a_8_jours(admin, client, db_session) -> None:
    produit = _creer(admin, "Bounty", 0)

    _vieillir(db_session, produit["id"], 6)
    assert _au_catalogue(client, produit["id"])

    _vieillir(db_session, produit["id"], 8)
    assert not _au_catalogue(client, produit["id"])
    liste = admin.get(f"{API}/products").json()
    vu_par_l_admin = next(p for p in liste if p["id"] == produit["id"])
    assert vu_par_l_admin["masque_epuise"] is True
    assert vu_par_l_admin["is_active"] is True


def test_le_reappro_le_fait_revenir(admin, client, db_session) -> None:
    produit = _creer(admin, "Snickers", 0)
    _vieillir(db_session, produit["id"], 10)
    assert not _au_catalogue(client, produit["id"])

    reponse = admin.post(
        f"{API}/products/{produit['id']}/reappro",
        json={"quantite": 12, "prix_achat_unitaire_cents": 50},
    )
    assert reponse.status_code == 200, reponse.text

    assert _produit(db_session, produit["id"]).epuise_depuis is None
    assert _au_catalogue(client, produit["id"])


def test_les_cafes_ne_sont_jamais_masques(admin, client, db_session) -> None:
    cafe = _creer(admin, "Espresso", 0, "cafe")
    _vieillir(db_session, cafe["id"], 30)
    assert _au_catalogue(client, cafe["id"])


def test_le_reappro_ne_reactive_pas_un_produit_masque_a_la_main(admin, client, db_session) -> None:
    produit = _creer(admin, "Cappuccino", 0)
    assert admin.patch(f"{API}/products/{produit['id']}", json={"is_active": False}).status_code == 200
    _vieillir(db_session, produit["id"], 10)

    admin.post(
        f"{API}/products/{produit['id']}/reappro",
        json={"quantite": 5, "prix_achat_unitaire_cents": 50},
    )

    assert _produit(db_session, produit["id"]).is_active is False
    assert not _au_catalogue(client, produit["id"])


def test_recaler_suit_le_stock_fixe_par_un_inventaire(admin, db_session) -> None:
    """Chemin de l'inventaire : quantité absolue, puis `recaler_epuisement`."""
    plein = _creer(admin, "Oreo", 0)
    vide = _creer(admin, "Prince", 4)
    _vieillir(db_session, plein["id"], 9)
    p_plein = _produit(db_session, plein["id"])
    p_vide = _produit(db_session, vide["id"])
    p_plein.quantity = 6
    p_vide.quantity = 0
    db_session.flush()

    buvette_crud.recaler_epuisement(db_session, {plein["id"], vide["id"]})
    db_session.commit()

    assert _produit(db_session, plein["id"]).epuise_depuis is None
    assert _produit(db_session, vide["id"]).epuise_depuis is not None


def test_regle_de_masquage() -> None:
    maintenant = datetime(2026, 10, 20, 12, 0)
    il_y_a = lambda j: maintenant - timedelta(days=j)  # noqa: E731
    assert est_masque_epuise(0, "boissons", il_y_a(7), maintenant)
    assert not est_masque_epuise(0, "boissons", il_y_a(6), maintenant)
    assert not est_masque_epuise(3, "boissons", il_y_a(30), maintenant)
    assert not est_masque_epuise(0, "cafe", il_y_a(30), maintenant)
    assert not est_masque_epuise(0, "boissons", None, maintenant)
