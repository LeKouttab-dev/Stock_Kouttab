"""End-to-end tests for /invoices endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _upload_invoice(client, user, headers_factory, pole=None, **overrides) -> int:
    files = {"files": ("facture.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    data = {
        "commentaire": "Une facture",
        "date_depot": "2024-04-15",
        "id_pole": str(pole.id) if pole is not None else "1",
        # Demandee sous tous les poles, evenementiels compris : elle dit ce qui
        # a ete achete, la ou l'evenement dit a quelle occasion.
        "id_categorie": "1",
        "evenement_libre": "Gala de printemps",
        "date_evenement": "2024-04-10",
    }
    data.update(overrides)
    resp = client.post(
        "/api/v1/invoices", data=data, files=files, headers=headers_factory(user)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_invoice_via_multipart_returns_201(
    client: TestClient, benevole_user, auth_headers
) -> None:
    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    assert invoice_id > 0


def test_get_my_invoices_returns_list(
    client: TestClient, benevole_user, auth_headers
) -> None:
    _upload_invoice(client, benevole_user, auth_headers)
    resp = client.get("/api/v1/invoices/me", headers=auth_headers(benevole_user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert all(inv["id_user"] == benevole_user.id for inv in body)


def test_list_invoices_with_status_filter(
    client: TestClient, compta_user, benevole_user, auth_headers
) -> None:
    _upload_invoice(client, benevole_user, auth_headers)
    resp = client.get(
        "/api/v1/invoices?status=En attente", headers=auth_headers(compta_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(inv["status"] == "En attente" for inv in body)


def test_update_invoice_status_by_compta_ok(
    client: TestClient, benevole_user, compta_user, auth_headers
) -> None:
    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    resp = client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "Validée"},
        headers=auth_headers(compta_user),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "Validée"


def test_update_invoice_status_by_benevole_forbidden(
    client: TestClient, benevole_user, auth_headers
) -> None:
    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    resp = client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "Validée"},
        headers=auth_headers(benevole_user),
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "PERM_2002"


def test_invoice_status_traceability_records_the_validator(
    client: TestClient, benevole_user, compta_user, auth_headers
) -> None:
    """Qui a valide quoi, et quand : indispensable en comptabilite."""
    from app.db.models import Invoice

    from tests.conftest import _TestingSessionLocal

    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    resp = client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "Validée"},
        headers=auth_headers(compta_user),
    )
    assert resp.status_code == 200, resp.text

    db = _TestingSessionLocal()
    try:
        invoice = db.get(Invoice, invoice_id)
        assert invoice.validated_by == compta_user.id
        assert invoice.validated_at is not None
    finally:
        db.close()


def test_validated_invoice_cannot_be_reopened(
    client: TestClient, benevole_user, compta_user, auth_headers
) -> None:
    """'Validée' est un etat terminal : plus de retour arriere."""
    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    ok = client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "Validée"},
        headers=auth_headers(compta_user),
    )
    assert ok.status_code == 200, ok.text

    back = client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "En attente"},
        headers=auth_headers(compta_user),
    )
    assert back.status_code == 422, back.text
    assert "interdite" in back.json()["message"].lower()


def test_owner_can_delete_a_pending_invoice(
    client: TestClient, benevole_user, auth_headers
) -> None:
    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    resp = client.delete(
        f"/api/v1/invoices/{invoice_id}", headers=auth_headers(benevole_user)
    )
    assert resp.status_code == 200, resp.text


def test_owner_cannot_delete_an_invoice_already_processed(
    client: TestClient, benevole_user, compta_user, auth_headers
) -> None:
    """Une piece prise en charge par la compta ne doit plus etre destructible."""
    invoice_id = _upload_invoice(client, benevole_user, auth_headers)
    client.patch(
        f"/api/v1/invoices/{invoice_id}/status",
        json={"status": "En cours de traitement"},
        headers=auth_headers(compta_user),
    )
    resp = client.delete(
        f"/api/v1/invoices/{invoice_id}", headers=auth_headers(benevole_user)
    )
    assert resp.status_code == 403, resp.text

    # La comptabilite, elle, conserve la main.
    resp_compta = client.delete(
        f"/api/v1/invoices/{invoice_id}", headers=auth_headers(compta_user)
    )
    assert resp_compta.status_code == 200, resp_compta.text
