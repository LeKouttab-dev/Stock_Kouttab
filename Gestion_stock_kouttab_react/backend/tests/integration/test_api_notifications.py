"""Compteurs de dossiers en attente, et ce que chaque role a le droit d'en voir.

Le point sensible n'est pas le comptage : c'est le filtrage. Ces chiffres
alimentent les pastilles du menu et le rappel de connexion, et un benevole n'a
pas a apprendre combien de comptes attendent une validation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.crud import expense as expense_crud


pytestmark = pytest.mark.integration


def _resume(client: TestClient, user, auth_headers) -> dict:
    reponse = client.get("/api/v1/notifications/summary", headers=auth_headers(user))
    assert reponse.status_code == 200, reponse.text
    return reponse.json()


def _note_en_attente(db_session, user, local_pole, first_category) -> None:
    expense_crud.create_expense(
        db_session,
        user_id=user.id,
        date_depense=__import__("datetime").date(2026, 8, 12),
        rattachement=None,
        fournisseur="Metro",
        nature_charge=None,
        montant=Decimal("10"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
        id_pole=local_pole.id,
        pole=local_pole.nom,
        id_categorie=first_category.id,
        categorie=first_category.nom,
    )


def test_la_compta_voit_les_notes_a_valider(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    _note_en_attente(db_session, benevole_user, local_pole, first_category)
    assert _resume(client, compta_user, auth_headers)["notes_a_valider"] == 1


def test_un_benevole_ne_voit_pas_les_notes_des_autres(
    client: TestClient, compta_user, benevole_user, auth_headers, db_session,
    local_pole, first_category,
):
    """Le compteur vaut 0, comme s'il n'y avait rien : le nombre reel n'est
    jamais envoye a qui n'a pas a le connaitre."""
    _note_en_attente(db_session, compta_user, local_pole, first_category)
    assert _resume(client, benevole_user, auth_headers)["notes_a_valider"] == 0


def test_seul_le_super_admin_compte_les_comptes_a_valider(
    client: TestClient, super_admin_user, compta_user, pending_user, auth_headers
):
    assert _resume(client, super_admin_user, auth_headers)["comptes_a_valider"] >= 1
    assert _resume(client, compta_user, auth_headers)["comptes_a_valider"] == 0


def test_un_benevole_n_a_rien_a_traiter(
    client: TestClient, benevole_user, pending_user, auth_headers
):
    resume = _resume(client, benevole_user, auth_headers)
    assert resume == {
        "notes_a_valider": 0,
        "factures_a_traiter": 0,
        "modifications_stock": 0,
        "comptes_a_valider": 0,
        "articles_en_alerte": 0,
    }


def test_l_endpoint_exige_une_authentification(client: TestClient):
    assert client.get("/api/v1/notifications/summary").status_code == 401
