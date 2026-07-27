"""End-to-end tests for /invoices endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _upload_invoice(client, user, headers_factory) -> int:
    files = {"files": ("facture.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    data = {"commentaire": "Une facture", "date_depot": "2024-04-15"}
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
