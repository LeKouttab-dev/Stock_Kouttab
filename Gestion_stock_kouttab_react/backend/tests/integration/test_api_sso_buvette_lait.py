"""Les boissons au lait de la buvette, basculees depuis gestion.lekouttab.fr.

POST /api/v1/auth/sso/buvette-lait — jeton dedie (typ 'sso-buvette-lait',
60 s) signe du secret partage, `action` dans le jeton. Verrouille ici :

 1. seuls les produits de `BUVETTE_PRODUITS_LAIT_IDS` bougent, jamais un autre ;
 2. une bascule consomme son `jti` : rejouer le meme jeton rend 409 ;
 3. `etat` est une lecture, sans `jti` exige.
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.core.config import settings
from app.db.models import BuvetteProduct


pytestmark = pytest.mark.integration

SECRET_TEST = "secret-partage-de-test-suffisamment-long-1234"
URL = "/api/v1/auth/sso/buvette-lait"


@pytest.fixture()
def sso_actif(monkeypatch):
    monkeypatch.setattr(settings, "sso_shared_secret", SECRET_TEST)
    return SECRET_TEST


@pytest.fixture()
def produits(db_session, monkeypatch):
    def _p(nom, actif):
        p = BuvetteProduct(name=nom, price_cents=250, quantity=0, is_active=actif)
        db_session.add(p)
        return p

    cappuccino = _p("Cappuccino", False)
    latte = _p("Latte macchiato", False)
    expresso = _p("Expresso", True)
    db_session.commit()
    monkeypatch.setattr(
        settings, "buvette_produits_lait_ids", f"{cappuccino.id},{latte.id}"
    )
    return cappuccino, latte, expresso


def _jeton(action: str = "etat", *, typ: str = "sso-buvette-lait", jti: bool = True) -> str:
    maintenant = int(time.time())
    charge = {
        "iss": "gestion.lekouttab.fr",
        "aud": "stock.lekouttab.fr",
        "typ": typ,
        "iat": maintenant,
        "exp": maintenant + 45,
        "email": "Responsable@Example.com",
        "action": action,
    }
    if jti:
        charge["jti"] = str(uuid.uuid4())
    return jose_jwt.encode(charge, SECRET_TEST, algorithm="HS256")


def _actifs(db_session, *produits) -> list[bool]:
    db_session.expire_all()
    return [db_session.get(BuvetteProduct, p.id).is_active for p in produits]


def test_sans_secret_configure_la_porte_n_existe_pas(client: TestClient, produits) -> None:
    assert client.post(URL, json={"token": _jeton()}).status_code == 404


def test_refuse_un_jeton_d_un_autre_type(client: TestClient, sso_actif, produits) -> None:
    resp = client.post(URL, json={"token": _jeton(typ="sso-calendrier")})
    assert resp.status_code == 401


def test_action_inconnue(client: TestClient, sso_actif, produits) -> None:
    assert client.post(URL, json={"token": _jeton("supprimer")}).status_code == 422


def test_etat_sans_jti(client: TestClient, sso_actif, produits) -> None:
    resp = client.post(URL, json={"token": _jeton(jti=False)})
    assert resp.status_code == 200
    corps = resp.json()
    assert corps["actif"] is False
    assert [p["nom"] for p in corps["produits"]] == ["Cappuccino", "Latte macchiato"]


def test_activer_puis_desactiver_ne_touche_que_le_lait(
    client: TestClient, sso_actif, produits, db_session
) -> None:
    cappuccino, latte, expresso = produits

    resp = client.post(URL, json={"token": _jeton("activer")})
    assert resp.status_code == 200
    assert resp.json()["actif"] is True
    assert _actifs(db_session, cappuccino, latte, expresso) == [True, True, True]

    resp = client.post(URL, json={"token": _jeton("desactiver")})
    assert resp.status_code == 200
    assert resp.json()["actif"] is False
    assert all(not p["actif"] for p in resp.json()["produits"])
    assert _actifs(db_session, cappuccino, latte, expresso) == [False, False, True]


def test_bascule_sans_jti_refusee(client: TestClient, sso_actif, produits, db_session) -> None:
    resp = client.post(URL, json={"token": _jeton("activer", jti=False)})
    assert resp.status_code == 401
    assert _actifs(db_session, *produits[:2]) == [False, False]


def test_rejeu_d_une_bascule(client: TestClient, sso_actif, produits) -> None:
    jeton = _jeton("activer")
    assert client.post(URL, json={"token": jeton}).status_code == 200
    assert client.post(URL, json={"token": jeton}).status_code == 409


def test_etat_mixte_compte_comme_desactive(
    client: TestClient, sso_actif, produits, db_session
) -> None:
    cappuccino, _latte, _ = produits
    db_session.get(BuvetteProduct, cappuccino.id).is_active = True
    db_session.commit()
    assert client.post(URL, json={"token": _jeton()}).json()["actif"] is False
