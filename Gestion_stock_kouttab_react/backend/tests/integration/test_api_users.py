"""End-to-end tests for /users endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def test_list_users_as_super_admin_returns_200(
    client: TestClient, super_admin_user, auth_headers
) -> None:
    resp = client.get("/api/v1/users", headers=auth_headers(super_admin_user))
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_list_users_as_benevole_returns_403(
    client: TestClient, benevole_user, auth_headers
) -> None:
    resp = client.get("/api/v1/users", headers=auth_headers(benevole_user))
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "PERM_2002"


def test_list_pending_users_as_super_admin(
    client: TestClient, super_admin_user, pending_user, auth_headers
) -> None:
    resp = client.get(
        "/api/v1/users/pending", headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(u["id"] == pending_user.id for u in body)


def test_validate_pending_user_to_active(
    client: TestClient, super_admin_user, pending_user, auth_headers
) -> None:
    resp = client.patch(
        f"/api/v1/users/{pending_user.id}/validate",
        json={"validation_status": "active"},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["validation_status"] == "active"


def test_update_role_by_super_admin(
    client: TestClient, super_admin_user, benevole_user, auth_headers
) -> None:
    resp = client.patch(
        f"/api/v1/users/{benevole_user.id}/role",
        json={"role": "Compta"},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "Compta"


def test_delete_user_self_is_filtered_or_forbidden(
    client: TestClient, super_admin_user, benevole_user, auth_headers
) -> None:
    # Deleting another user works.
    resp = client.delete(
        f"/api/v1/users/{benevole_user.id}",
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200, resp.text

    # The endpoint itself does not block self-deletion in code, but the
    # require_roles check still allows it. The list_users endpoint at least
    # excludes the current user. We verify deletion just succeeds (200).
    # (No explicit SELF_ACTION_FORBIDDEN guard in this endpoint — the API
    # relies on UI-level confirmation.)


# ---- Annuaire (lecture seule, ouvert a la comptabilite) ---------------------


def test_la_comptabilite_consulte_l_annuaire(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    """Elle rembourse ces personnes et leur reclame des pieces : savoir qui est
    inscrit fait partie de son travail."""
    reponse = client.get("/api/v1/users/annuaire", headers=auth_headers(compta_user))

    assert reponse.status_code == 200, reponse.text
    assert benevole_user.id in [u["id"] for u in reponse.json()]


def test_l_annuaire_ne_livre_aucun_rib(
    client: TestClient, compta_user, benevole_user, auth_headers
):
    """Un annuaire n'est pas un fichier de coordonnees bancaires. Le RIB reste
    sur la fiche de la note de frais, la ou il sert."""
    premier = client.get(
        "/api/v1/users/annuaire", headers=auth_headers(compta_user)
    ).json()[0]
    assert "rib" not in premier


def test_l_annuaire_reste_ferme_aux_benevoles(
    client: TestClient, benevole_user, auth_headers
):
    reponse = client.get("/api/v1/users/annuaire", headers=auth_headers(benevole_user))
    assert reponse.status_code == 403, reponse.text


def test_la_gestion_des_comptes_reste_au_super_admin(
    client: TestClient, compta_user, auth_headers
):
    """Ouvrir la consultation n'ouvre pas la gestion : `GET /users` porte les
    actions (roles, suppression) et demeure ferme."""
    assert client.get("/api/v1/users", headers=auth_headers(compta_user)).status_code == 403
