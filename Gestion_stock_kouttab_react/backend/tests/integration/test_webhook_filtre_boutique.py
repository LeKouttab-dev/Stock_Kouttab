"""Le webhook ne doit traiter que les ventes de la buvette.

L'association ne dispose que d'**une seule** URL de notification pour tout son
compte HelloAsso — les URL multiples et le filtrage par type d'événement sont
réservés aux comptes partenaires. La même adresse reçoit donc les ventes de la
boutique buvette **et** les inscriptions aux stages d'été.

Sans filtre, une inscription à un stage serait enregistrée comme une vente et
irait décrémenter un stock qui n'a rien à voir avec elle. Le relais WordPress
filtre déjà, mais un filtre côté émetteur ne protège que tant qu'il fonctionne :
celui-ci est le nôtre.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.models import BuvetteProduct, BuvetteSale


pytestmark = pytest.mark.integration

URL = "/api/v1/buvette/webhook/helloasso"


@pytest.fixture()
def produit(db_session):
    article = BuvetteProduct(
        helloasso_tier_id=4242,
        name="Bouteille d'eau",
        price_cents=100,
        quantity=10,
        seuil_alerte=2,
    )
    db_session.add(article)
    db_session.commit()
    return article


def _commande(slug: str | None, *, payment_id: int, item_id: int) -> dict:
    commande: dict = {
        "id": 900 + item_id,
        "date": "2026-08-14T10:00:00Z",
        "payer": {"email": "acheteur@example.test"},
        "items": [
            {
                "id": item_id,
                "tierId": 4242,
                "paymentId": payment_id,
                "quantity": 1,
                "amount": 100,
                "name": "Bouteille d'eau",
            }
        ],
    }
    if slug is not None:
        commande["formSlug"] = slug
    return commande


def _ventes(db_session) -> list[BuvetteSale]:
    return list(db_session.execute(select(BuvetteSale)).scalars().all())


def test_une_vente_de_la_buvette_est_enregistree(client: TestClient, db_session, produit):
    reponse = client.post(
        URL,
        json={"eventType": "Order", "data": _commande("buvette", payment_id=1, item_id=1)},
    )
    assert reponse.status_code == 200

    db_session.expire_all()
    assert len(_ventes(db_session)) == 1
    assert db_session.get(BuvetteProduct, produit.id).quantity == 9


def test_une_inscription_a_un_stage_est_ignoree(client: TestClient, db_session, produit):
    """Le cas qui compte : même URL, événement d'un autre formulaire."""
    reponse = client.post(
        URL,
        json={
            "eventType": "Order",
            "data": _commande("stage-ete-2026", payment_id=2, item_id=2),
        },
    )
    assert reponse.status_code == 200

    db_session.expire_all()
    assert _ventes(db_session) == []
    # Et surtout : le stock n'a pas bougé.
    assert db_session.get(BuvetteProduct, produit.id).quantity == 10


def test_le_slug_se_lit_aussi_dans_le_sous_objet(client: TestClient, db_session, produit):
    """HelloAsso place le formulaire tantôt à la racine, tantôt dans `form`."""
    commande = _commande(None, payment_id=3, item_id=3)
    commande["form"] = {"formSlug": "stage-ete-2026", "formType": "Event"}

    client.post(URL, json={"eventType": "Order", "data": commande})

    db_session.expire_all()
    assert _ventes(db_session) == []


def test_une_commande_sans_slug_reste_acceptee(client: TestClient, db_session, produit):
    """Refuser par défaut ferait perdre des ventes réelles.

    Les commandes de la boutique ne portent pas toujours le slug selon le type
    d'événement. Le refus est réservé à un slug présent et différent.
    """
    client.post(URL, json={"eventType": "Order", "data": _commande(None, payment_id=4, item_id=4)})

    db_session.expire_all()
    assert len(_ventes(db_session)) == 1


def test_le_filtre_suit_la_configuration(client: TestClient, db_session, produit, monkeypatch):
    """Le slug de la boutique est un réglage, pas une constante du code."""
    monkeypatch.setattr(settings, "helloasso_buvette_form_slug", "boutique-hiver")

    client.post(
        URL, json={"eventType": "Order", "data": _commande("buvette", payment_id=5, item_id=5)}
    )
    db_session.expire_all()
    assert _ventes(db_session) == []

    client.post(
        URL,
        json={"eventType": "Order", "data": _commande("boutique-hiver", payment_id=6, item_id=6)},
    )
    db_session.expire_all()
    assert len(_ventes(db_session)) == 1


def test_le_rejeu_ne_compte_qu_une_fois(client: TestClient, db_session, produit):
    """HelloAsso rejoue jusqu'à 16 fois sans réponse 200 — et parfois quand même."""
    charge = {"eventType": "Order", "data": _commande("buvette", payment_id=7, item_id=7)}

    client.post(URL, json=charge)
    client.post(URL, json=charge)

    db_session.expire_all()
    assert len(_ventes(db_session)) == 1
    assert db_session.get(BuvetteProduct, produit.id).quantity == 9
