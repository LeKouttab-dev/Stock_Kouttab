"""La caisse de la buvette : la tablette qui encaisse par SumUp.

Les ventes de la buvette passent désormais par une tablette Android reliée à un
terminal SumUp, et non plus par la boutique HelloAsso. Un encaissement SumUp ne
prévient personne : sans ces routes, le stock ne bougeait plus du tout.

Deux routes, protégées par une clé propre à la tablette (`CAISSE_API_KEY`), et
non par une session : la tablette reste en caisse des journées entières, un
jeton de 30 minutes la déconnecterait en plein service.

- `GET /buvette/caisse/catalogue` : ce que la tablette affiche.
- `POST /buvette/caisse/ventes` : une vente payée, qui décrémente le stock.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct, BuvetteSale
from app.schemas.buvette import BuvetteProductCreate


pytestmark = pytest.mark.integration

CLE = "cle-de-test-de-la-caisse-au-moins-32-caracteres"
CATALOGUE = "/api/v1/buvette/caisse/catalogue"
VENTES = "/api/v1/buvette/caisse/ventes"


@pytest.fixture(autouse=True)
def _caisse_activee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", CLE)


def _entetes(cle: str = CLE) -> dict[str, str]:
    return {"X-Caisse-Key": cle}


def _produit(
    db: Session,
    *,
    nom: str | None = None,
    quantite: int = 10,
    seuil: int = 5,
    categorie: str | None = "sucre_sale",
    actif: bool = True,
    prix: int = 150,
    image: str | None = None,
) -> BuvetteProduct:
    produit = buvette_crud.create_product(
        db,
        BuvetteProductCreate(
            name=nom or f"Produit_{uuid.uuid4().hex[:6]}",
            price_cents=prix,
            quantity=quantite,
            seuil_alerte=seuil,
            emoji="🍫",
            image_url=image,
            is_active=actif,
            caisse_category=categorie,
        ),
    )
    return produit


def _vente(lignes: list[dict[str, Any]], *, tx: str | None = None) -> dict[str, Any]:
    return {
        "transaction_id": tx or str(uuid.uuid4()),
        "sumup_tx_code": "TXCODE1234",
        "total_cents": sum(l["quantity"] * l["unit_price_cents"] for l in lignes),
        "sold_at": "2026-09-19T10:00:00+02:00",
        "lines": lignes,
    }


def _ligne(produit: BuvetteProduct | None, quantite: int = 1, prix: int = 150) -> dict:
    return {
        "product_id": produit.id if produit is not None else None,
        "name": produit.name if produit is not None else "Article libre",
        "quantity": quantite,
        "unit_price_cents": prix,
    }


def _quantite(db: Session, produit_id: int) -> int:
    db.expire_all()
    return db.get(BuvetteProduct, produit_id).quantity


# ---------------------------------------------------------------------------
# La clé
# ---------------------------------------------------------------------------


def test_sans_cle_configuree_la_caisse_n_existe_pas(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clé absente du `.env` : les routes répondent 404, comme le passage signé.

    Sans ce choix, une clé vide comparée à un en-tête vide ouvrirait la porte.
    """
    monkeypatch.setattr(settings, "caisse_api_key", "")

    assert client.get(CATALOGUE, headers=_entetes("")).status_code == 404
    assert client.post(VENTES, json=_vente([]), headers=_entetes("")).status_code == 404


def test_une_vente_sans_cle_ou_avec_la_mauvaise_est_refusee(
    client: TestClient, db_session: Session
) -> None:
    """La seule chose qui sépare une vente réelle d'une vente forgée.

    Accepter une vente inventée décrémente le stock : n'importe qui connaissant
    l'adresse pourrait vider l'inventaire.
    """
    produit = _produit(db_session)
    vente = _vente([_ligne(produit, 3)])

    assert client.post(VENTES, json=vente).status_code == 401
    assert client.post(VENTES, json=vente, headers=_entetes("presque-la-bonne")).status_code == 401
    assert client.get(CATALOGUE, headers=_entetes("presque-la-bonne")).status_code == 401
    assert _quantite(db_session, produit.id) == 10


# ---------------------------------------------------------------------------
# Le catalogue
# ---------------------------------------------------------------------------


def test_le_catalogue_ne_montre_que_les_produits_actifs_et_classes(
    client: TestClient, db_session: Session
) -> None:
    """Un produit sans catégorie de caisse n'apparaît pas sur la tablette.

    Les produits importés de HelloAsso arrivent sans catégorie : c'est ce qui
    permet de choisir ce que la tablette vend, sans rien supprimer.
    """
    visible = _produit(
        db_session,
        nom="Kinder Bueno",
        categorie="sucre_sale",
        quantite=4,
        image="https://cdn.helloasso.com/img/photos/boutiques/kinder-bueno.png",
    )
    _produit(db_session, nom="Sans categorie", categorie=None)
    _produit(db_session, nom="Desactive", categorie="boissons", actif=False)

    reponse = client.get(CATALOGUE, headers=_entetes())

    assert reponse.status_code == 200
    produits = reponse.json()["products"]
    assert [p["name"] for p in produits] == ["Kinder Bueno"]
    assert produits[0] == {
        "id": visible.id,
        "name": "Kinder Bueno",
        "price_cents": 150,
        "category": "sucre_sale",
        "emoji": "🍫",
        "image_url": "https://cdn.helloasso.com/img/photos/boutiques/kinder-bueno.png",
        "quantity": 4,
        "low_stock": True,
    }
    assert "generated_at" in reponse.json()


def test_la_categorie_de_caisse_se_regle_depuis_la_fiche_produit(
    client_authenticated_as, admin_benevoles_user, db_session: Session
) -> None:
    """Sans ce réglage, aucun produit n'atteindrait jamais la tablette."""
    produit = _produit(db_session, categorie=None)
    c = client_authenticated_as(admin_benevoles_user)

    reponse = c.patch(f"/api/v1/buvette/products/{produit.id}", json={"caisse_category": "cafe"})
    assert reponse.status_code == 200
    assert reponse.json()["caisse_category"] == "cafe"

    # Quatrième onglet, pour le miel et ce qui n'est pas un en-cas.
    reponse = c.patch(f"/api/v1/buvette/products/{produit.id}", json={"caisse_category": "epicerie"})
    assert reponse.json()["caisse_category"] == "epicerie"

    # Retirer de la tablette : repasser à null.
    reponse = c.patch(f"/api/v1/buvette/products/{produit.id}", json={"caisse_category": None})
    assert reponse.json()["caisse_category"] is None

    assert c.patch(
        f"/api/v1/buvette/products/{produit.id}", json={"caisse_category": "alcool"}
    ).status_code == 422


# ---------------------------------------------------------------------------
# Les ventes
# ---------------------------------------------------------------------------


def test_une_vente_decremente_le_stock_de_chaque_ligne(
    client: TestClient, db_session: Session
) -> None:
    """Le même produit peut revenir sur deux lignes : prix combo et prix normal."""
    bueno = _produit(db_session, quantite=10)
    expresso = _produit(db_session, quantite=20, categorie="cafe", prix=120)
    vente = _vente(
        [_ligne(bueno, 2), _ligne(expresso, 1, prix=100), _ligne(expresso, 1, prix=120)]
    )

    reponse = client.post(VENTES, json=vente, headers=_entetes())

    assert reponse.status_code == 201
    assert reponse.json() == {
        "transaction_id": vente["transaction_id"],
        "status": "recorded",
        "lines": 3,
    }
    assert _quantite(db_session, bueno.id) == 8
    assert _quantite(db_session, expresso.id) == 18

    lignes = db_session.execute(
        select(BuvetteSale).where(BuvetteSale.caisse_tx_id == vente["transaction_id"])
    ).scalars().all()
    assert len(lignes) == 3
    assert {l.source for l in lignes} == {"caisse"}
    assert {l.sumup_tx_code for l in lignes} == {"TXCODE1234"}
    assert sum(l.amount_cents for l in lignes) == vente["total_cents"]


def test_la_meme_vente_renvoyee_ne_decremente_qu_une_fois(
    client: TestClient, db_session: Session
) -> None:
    """La tablette renvoie tant qu'elle n'a pas eu de réponse.

    Une coupure réseau pendant la réponse est le cas normal d'un sous-sol : la
    vente est arrivée, la tablette ne le sait pas et la renvoie. Décrémenter une
    seconde fois fausserait le stock à chaque coupure.
    """
    produit = _produit(db_session, quantite=10)
    vente = _vente([_ligne(produit, 3)])

    assert client.post(VENTES, json=vente, headers=_entetes()).status_code == 201
    reponse = client.post(VENTES, json=vente, headers=_entetes())

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "already_recorded"
    assert _quantite(db_session, produit.id) == 7


def test_un_total_incoherent_est_refuse_sans_rien_ecrire(
    client: TestClient, db_session: Session
) -> None:
    """Le total encaissé et le détail doivent dire la même chose.

    Un écart signale une tablette déréglée : enregistrer quand même produirait
    un chiffre d'affaires qui ne correspond à aucun encaissement.
    """
    produit = _produit(db_session, quantite=10)
    vente = _vente([_ligne(produit, 2)])
    vente["total_cents"] += 1

    assert client.post(VENTES, json=vente, headers=_entetes()).status_code == 422
    assert _quantite(db_session, produit.id) == 10
    assert db_session.execute(select(BuvetteSale)).scalars().all() == []


@pytest.mark.parametrize(
    "champ, valeur",
    [
        ("transaction_id", "court"),
        ("transaction_id", "pas d'espaces ni de ; dans un identifiant"),
        ("lines", []),
    ],
)
def test_une_vente_malformee_est_refusee(
    client: TestClient, db_session: Session, champ: str, valeur: Any
) -> None:
    produit = _produit(db_session)
    vente = _vente([_ligne(produit)])
    vente[champ] = valeur
    if champ == "lines":
        vente["total_cents"] = 0

    assert client.post(VENTES, json=vente, headers=_entetes()).status_code == 422


def test_un_produit_inconnu_est_vendu_sans_decrement(
    client: TestClient, db_session: Session
) -> None:
    """Un produit supprimé côté stock entre deux rafraîchissements du catalogue.

    La vente a eu lieu, l'argent est encaissé : la refuser la ferait perdre.
    Elle est gardée, sans produit rattaché, et le reste du panier décrémente.
    """
    produit = _produit(db_session, quantite=10)
    fantome = {"product_id": 999_999, "name": "Supprime", "quantity": 1, "unit_price_cents": 200}
    vente = _vente([_ligne(produit, 1), fantome])

    assert client.post(VENTES, json=vente, headers=_entetes()).status_code == 201
    assert _quantite(db_session, produit.id) == 9
    orpheline = db_session.execute(
        select(BuvetteSale).where(BuvetteSale.product_name_snapshot == "Supprime")
    ).scalar_one()
    assert orpheline.buvette_product_id is None


def test_le_stock_ne_descend_pas_sous_zero(client: TestClient, db_session: Session) -> None:
    """Le comptage physique peut être en retard : la vente passe quand même."""
    produit = _produit(db_session, quantite=1)

    assert client.post(VENTES, json=_vente([_ligne(produit, 3)]), headers=_entetes()).status_code == 201
    assert _quantite(db_session, produit.id) == 0


def test_le_passage_sous_le_seuil_previent_une_seule_fois(
    client: TestClient, db_session: Session, admin_benevoles_user, captured_emails
) -> None:
    """Même alerte que pour les ventes HelloAsso, sans en répéter une par vente."""
    produit = _produit(db_session, quantite=6, seuil=5)

    client.post(VENTES, json=_vente([_ligne(produit, 2)]), headers=_entetes())
    client.post(VENTES, json=_vente([_ligne(produit, 1)]), headers=_entetes())

    alertes = [m for m in captured_emails if "Alerte stock buvette" in m.subject]
    assert len(alertes) == 1
    assert admin_benevoles_user.email in alertes[0].recipients


# ---------------------------------------------------------------------------
# Ce que les autres écrans en disent
# ---------------------------------------------------------------------------


def test_la_liste_des_ventes_indique_la_source(
    client: TestClient, client_authenticated_as, admin_benevoles_user, db_session: Session
) -> None:
    produit = _produit(db_session)
    client.post(VENTES, json=_vente([_ligne(produit)]), headers=_entetes())

    ventes = client_authenticated_as(admin_benevoles_user).get("/api/v1/buvette/sales").json()

    assert ventes[0]["source"] == "caisse"
    assert ventes[0]["sumup_tx_code"] == "TXCODE1234"


def test_une_vente_de_caisse_ne_prouve_pas_que_helloasso_nous_appelle(
    client: TestClient, db_session: Session
) -> None:
    """L'état du webhook compte les ventes reçues comme preuve qu'il fonctionne.

    Compter aussi celles de la tablette afficherait un webhook « actif » alors
    que HelloAsso ne nous a jamais rien envoyé : un affichage qui ment.
    """
    produit = _produit(db_session)
    client.post(VENTES, json=_vente([_ligne(produit)]), headers=_entetes())

    derniere, nombre = buvette_crud.get_sales_activity(db_session)

    assert (derniere, nombre) == (None, 0)
