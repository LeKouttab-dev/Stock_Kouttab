"""Le secret du webhook HelloAsso.

L'endpoint `/buvette/webhook/helloasso` est **public** : c'est HelloAsso qui
appelle, il n'y a pas de session à présenter. Sa seule protection est un jeton
porté par l'URL enregistrée chez HelloAsso.

Ce jeton n'avait aucun test. Le webhook en avait quatre — traitement d'une
commande, idempotence, charge malformée — mais aucun ne vérifiait qu'un appel
sans jeton, ou avec le mauvais, est refusé. Or c'est la seule chose qui sépare
une vente réelle d'une vente forgée : accepter un `Order` inventé crée des
lignes de vente et **décrémente le stock**.

Le 2026-08-13, la production tournait avec `HELLOASSO_WEBHOOK_SECRET` vide :
l'endpoint laissait tout passer. D'où le dernier test de ce fichier.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


pytestmark = pytest.mark.integration

URL = "/api/v1/buvette/webhook/helloasso"

# Charge volontairement invalide : elle traverse le contrôle du secret puis
# échoue au décodage. C'est ce qui permet de distinguer les deux refus —
# « unauthorized » signifie que le secret a bloqué, « invalid_json » qu'il a
# laissé passer. Aucune vente n'est créée dans un cas comme dans l'autre.
CHARGE = "pas du json"


def _poster(client: TestClient, token: str | None = None) -> dict:
    url = URL if token is None else f"{URL}?token={token}"
    return client.post(url, content=CHARGE, headers={"Content-Type": "application/json"}).json()


def test_un_appel_sans_jeton_est_refuse(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "s3cr3t-de-test")

    assert _poster(client)["reason"] == "unauthorized"


def test_un_mauvais_jeton_est_refuse(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "s3cr3t-de-test")

    assert _poster(client, "presque-le-bon")["reason"] == "unauthorized"


def test_le_bon_jeton_passe(client: TestClient, monkeypatch):
    """Il franchit le contrôle et échoue plus loin, sur la charge invalide."""
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "s3cr3t-de-test")

    assert _poster(client, "s3cr3t-de-test")["reason"] == "invalid_json"


def test_le_refus_ne_renseigne_pas_l_appelant(client: TestClient, monkeypatch):
    """200 dans tous les cas.

    Un 401 ou un 403 dirait à un tiers qu'un secret existe et qu'il a visé
    juste ; et HelloAsso, lui, rejouerait en boucle sur une erreur.
    """
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "s3cr3t-de-test")

    reponse = client.post(URL, content=CHARGE, headers={"Content-Type": "application/json"})
    assert reponse.status_code == 200


def test_sans_secret_configure_la_production_refuse(client: TestClient, monkeypatch):
    """Le point qui manquait.

    Secret vide, l'endpoint laissait **tout** passer — n'importe qui connaissant
    l'URL pouvait forger des ventes et vider le stock. En développement, la
    tolérance reste utile : aucune machine locale n'a de secret. En production,
    elle ne se justifie pas.
    """
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "")
    monkeypatch.setattr(settings, "app_env", "production")

    assert _poster(client)["reason"] == "unauthorized"


def test_sans_secret_le_developpement_reste_tolerant(client: TestClient, monkeypatch):
    """Sinon la buvette serait intestable en local, et la suite avec elle."""
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "")
    monkeypatch.setattr(settings, "app_env", "development")

    assert _poster(client)["reason"] == "invalid_json"
