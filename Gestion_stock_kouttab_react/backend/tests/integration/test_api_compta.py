"""Circuit comptable de bout en bout : depot -> PDF nomme -> file d'envoi."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.services import outbox


pytestmark = pytest.mark.integration


@pytest.fixture()
def compta_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "compta_email_raw", "comptabilite@lekouttab.fr")


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4 fake content for tests"


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (60, 30), (10, 90, 160)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _deposit(client, user, headers, *, pole_id, files=None, **overrides):
    payload = {
        "id_pole": str(pole_id),
        "evenement_libre": "Gala d'été 2026",
        "date_evenement": "2026-03-14",
        "commentaire": "Achat de fournitures",
        "fournisseur": "Métro",
        "montant": "142.50",
    }
    payload.update(overrides)
    files = files or [("files", ("facture.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"))]
    resp = client.post(
        "/api/v1/invoices", data=payload, files=files, headers=headers(user)
    )
    return resp


# ---- Referentiel des poles --------------------------------------------------


def test_default_poles_are_available(client: TestClient, benevole_user, auth_headers):
    resp = client.get("/api/v1/poles", headers=auth_headers(benevole_user))
    assert resp.status_code == 200, resp.text
    noms = [p["nom"] for p in resp.json()]
    assert "Pôle événementiel" in noms
    assert "Pôle institut" in noms
    assert "Local" in noms


def test_only_super_admin_can_create_a_pole(
    client: TestClient, benevole_user, compta_user, super_admin_user, auth_headers
):
    for user in (benevole_user, compta_user):
        resp = client.post(
            "/api/v1/poles", json={"nom": "Interdit"}, headers=auth_headers(user)
        )
        assert resp.status_code == 403, resp.text

    ok = client.post(
        "/api/v1/poles",
        json={"nom": "Pôle numérique"},
        headers=auth_headers(super_admin_user),
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["nom"] == "Pôle numérique"


def test_default_pole_cannot_be_deleted(
    client: TestClient, super_admin_user, auth_headers, first_pole
):
    """Il doit etre desactive, pas supprime : des factures le referencent."""
    resp = client.delete(
        f"/api/v1/poles/{first_pole.id}", headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 409, resp.text
    assert "desactivez" in resp.json()["message"].lower()


def test_inactive_pole_disappears_from_the_default_listing(
    client: TestClient, super_admin_user, auth_headers
):
    created = client.post(
        "/api/v1/poles",
        json={"nom": "Pôle temporaire"},
        headers=auth_headers(super_admin_user),
    ).json()
    client.patch(
        f"/api/v1/poles/{created['id']}",
        json={"is_active": False},
        headers=auth_headers(super_admin_user),
    )

    actifs = client.get("/api/v1/poles", headers=auth_headers(super_admin_user)).json()
    assert created["id"] not in [p["id"] for p in actifs]

    tous = client.get(
        "/api/v1/poles?include_inactive=true", headers=auth_headers(super_admin_user)
    ).json()
    assert created["id"] in [p["id"] for p in tous]


# ---- Referentiel des evenements ---------------------------------------------


def test_manual_event_can_be_created_and_selected(
    client: TestClient, admin_benevoles_user, benevole_user, auth_headers, first_pole
):
    created = client.post(
        "/api/v1/events",
        json={"nom": "Fête de fin d'année", "date_evenement": "2026-06-20"},
        headers=auth_headers(admin_benevoles_user),
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["source"] == "manuel"

    resp = _deposit(
        client,
        benevole_user,
        auth_headers,
        pole_id=first_pole.id,
        id_event=str(event["id"]),
        evenement_libre="",
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["evenement"] == "Fête de fin d'année"


def test_benevole_cannot_manage_events(
    client: TestClient, benevole_user, auth_headers
):
    resp = client.post(
        "/api/v1/events", json={"nom": "Interdit"}, headers=auth_headers(benevole_user)
    )
    assert resp.status_code == 403, resp.text


def test_event_listing_stays_available_without_helloasso(
    client: TestClient, benevole_user, auth_headers
):
    """Le depot ne doit jamais dependre de la disponibilite de HelloAsso."""
    resp = client.get("/api/v1/events", headers=auth_headers(benevole_user))
    assert resp.status_code == 200, resp.text


# ---- Depot et mise en file --------------------------------------------------


def test_deposit_requires_pole_and_event(
    client: TestClient, benevole_user, auth_headers, first_pole
):
    missing_event = _deposit(
        client,
        benevole_user,
        auth_headers,
        pole_id=first_pole.id,
        evenement_libre="",
    )
    assert missing_event.status_code == 422, missing_event.text


def test_event_cannot_be_both_selected_and_typed(
    client: TestClient, admin_benevoles_user, benevole_user, auth_headers, first_pole
):
    event = client.post(
        "/api/v1/events",
        json={"nom": "Kermesse"},
        headers=auth_headers(admin_benevoles_user),
    ).json()

    resp = _deposit(
        client,
        benevole_user,
        auth_headers,
        pole_id=first_pole.id,
        id_event=str(event["id"]),
        evenement_libre="Autre chose",
    )
    assert resp.status_code == 422, resp.text


def test_deposit_queues_a_correctly_named_pdf(
    client: TestClient, benevole_user, auth_headers, db_session, first_pole,
    compta_configured,
):
    """Le coeur de la demande : une piece nommee, prete pour le comptable."""
    resp = _deposit(client, benevole_user, auth_headers, pole_id=first_pole.id)
    assert resp.status_code == 201, resp.text
    invoice_id = resp.json()["id"]

    row = outbox.latest_for_entity(db_session, "invoice", invoice_id)
    assert row is not None
    assert json.loads(row.recipients) == ["comptabilite@lekouttab.fr"]

    attachments = json.loads(row.attachments)
    assert len(attachments) == 1
    nom = attachments[0].replace("\\", "/").rsplit("/", 1)[-1]
    # {Pole}_{Evenement}_{Date}.pdf, assaini et sans accent.
    assert nom == "Pole-evenementiel_Gala-dete-2026_2026-03-14.pdf"


def test_photo_deposit_is_converted_to_pdf(
    client: TestClient, benevole_user, auth_headers, db_session, first_pole,
    compta_configured,
):
    """Un justificatif photographie doit arriver en PDF chez le comptable."""
    resp = _deposit(
        client,
        benevole_user,
        auth_headers,
        pole_id=first_pole.id,
        files=[("files", ("ticket.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg"))],
    )
    assert resp.status_code == 201, resp.text

    row = outbox.latest_for_entity(db_session, "invoice", resp.json()["id"])
    attachments = json.loads(row.attachments)
    assert attachments[0].endswith(".pdf")
    with open(attachments[0], "rb") as handle:
        assert handle.read(4) == b"%PDF"


def test_multiple_files_get_distinct_names(
    client: TestClient, benevole_user, auth_headers, db_session, first_pole,
    compta_configured,
):
    """Trois justificatifs d'un meme depot partagent pole, evenement et date."""
    files = [
        ("files", (f"piece{i}.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"))
        for i in range(3)
    ]
    resp = _deposit(
        client, benevole_user, auth_headers, pole_id=first_pole.id, files=files
    )
    assert resp.status_code == 201, resp.text

    row = outbox.latest_for_entity(db_session, "invoice", resp.json()["id"])
    noms = [a.replace("\\", "/").rsplit("/", 1)[-1] for a in json.loads(row.attachments)]
    assert len(noms) == 3
    assert len(set(noms)) == 3, f"noms en collision : {noms}"


def test_deposit_without_compta_email_keeps_the_intent(
    client: TestClient, benevole_user, auth_headers, db_session, first_pole,
    monkeypatch: pytest.MonkeyPatch,
):
    """Adresse non configuree : rien ne doit etre perdu ni consomme."""
    monkeypatch.setattr(settings, "compta_email_raw", "")
    resp = _deposit(client, benevole_user, auth_headers, pole_id=first_pole.id)
    assert resp.status_code == 201, resp.text

    row = outbox.latest_for_entity(db_session, "invoice", resp.json()["id"])
    assert row.status == outbox.STATUS_PENDING
    assert row.attempts == 0
    assert json.loads(row.recipients) == []


def test_resend_is_restricted_to_accounting(
    client: TestClient, benevole_user, compta_user, auth_headers, first_pole,
    compta_configured,
):
    invoice_id = _deposit(
        client, benevole_user, auth_headers, pole_id=first_pole.id
    ).json()["id"]

    refused = client.post(
        f"/api/v1/invoices/{invoice_id}/resend-compta-email",
        headers=auth_headers(benevole_user),
    )
    assert refused.status_code == 403, refused.text

    allowed = client.post(
        f"/api/v1/invoices/{invoice_id}/resend-compta-email",
        headers=auth_headers(compta_user),
    )
    assert allowed.status_code == 200, allowed.text
