"""Le role BenevoleFrais est confine aux notes de frais — cote serveur.

Le menu ne protege rien : ces tests verrouillent les 403 de l'API elle-meme.
Ils verifient aussi qu'un Benevole classique ne perd rien au passage.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


HORS_PERIMETRE = [
    "/api/v1/stock/items",
    "/api/v1/invoices/me",
    "/api/v1/conversations",
]

DANS_LE_PERIMETRE = [
    "/api/v1/expenses/me",
    "/api/v1/reimbursements",
    "/api/v1/poles",
    "/api/v1/expense-categories",
    "/api/v1/events",
    "/api/v1/notifications/summary",
    "/api/v1/users/me/profile",
]


@pytest.mark.parametrize("url", HORS_PERIMETRE)
def test_benevole_frais_est_refuse_hors_perimetre(
    client: TestClient, auth_headers, benevole_frais_user, url: str
) -> None:
    resp = client.get(url, headers=auth_headers(benevole_frais_user))
    assert resp.status_code == 403, f"{url} -> {resp.status_code} {resp.text}"
    assert resp.json()["code"] == "PERM_2002"


@pytest.mark.parametrize("url", DANS_LE_PERIMETRE)
def test_benevole_frais_garde_tout_le_perimetre_frais(
    client: TestClient, auth_headers, benevole_frais_user, url: str
) -> None:
    resp = client.get(url, headers=auth_headers(benevole_frais_user))
    assert resp.status_code == 200, f"{url} -> {resp.status_code} {resp.text}"


@pytest.mark.parametrize("url", HORS_PERIMETRE)
def test_un_benevole_classique_ne_perd_rien(
    client: TestClient, auth_headers, benevole_user, url: str
) -> None:
    resp = client.get(url, headers=auth_headers(benevole_user))
    assert resp.status_code == 200, f"{url} -> {resp.status_code} {resp.text}"
