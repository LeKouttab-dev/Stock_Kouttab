"""End-to-end tests for /buvette endpoints (extends tests/test_buvette.py)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct, BuvetteSale
from app.schemas.buvette import BuvetteProductCreate
from app.services import helloasso as helloasso_service


pytestmark = pytest.mark.integration


def _seed(db: Session, *, tier_id: int, quantity: int = 10, seuil: int = 5):
    return buvette_crud.create_product(
        db,
        BuvetteProductCreate(
            name=f"Cafe_{uuid.uuid4().hex[:6]}",
            price_cents=150,
            quantity=quantity,
            seuil_alerte=seuil,
            emoji="☕",
            helloasso_tier_id=tier_id,
        ),
    )


def _order_payload(*, payment_id: int, item_id: int, tier_id: int, qty: int = 2) -> dict:
    return {
        "eventType": "Order",
        "data": {
            "id": 999_999,
            "items": [
                {
                    "id": item_id,
                    "tierId": tier_id,
                    "paymentId": payment_id,
                    "name": "Cafe",
                    "amount": 300,
                    "quantity": qty,
                }
            ],
            "payer": {
                "firstName": "Alice",
                "lastName": "Martin",
                "email": "alice@example.com",
            },
        },
        "metadata": None,
    }


# ---- Products ----


def test_get_products_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/buvette/products")
    assert resp.status_code == 401


def test_get_products_returns_list(
    client: TestClient, admin_benevoles_user, auth_headers, db_session
) -> None:
    _seed(db_session, tier_id=int(uuid.uuid4().int % 1_000_000_000))
    resp = client.get(
        "/api/v1/buvette/products", headers=auth_headers(admin_benevoles_user)
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


def test_buvette_is_closed_to_simple_volunteers(
    client: TestClient, benevole_user, auth_headers, db_session
) -> None:
    """La buvette est un outil de gestion, pas un ecran de consultation.

    Stock et ventes etaient lisibles par tout compte authentifie ; ils sont
    desormais fermes aux benevoles.
    """
    _seed(db_session, tier_id=int(uuid.uuid4().int % 1_000_000_000))

    for route in ("/api/v1/buvette/products", "/api/v1/buvette/sales"):
        resp = client.get(route, headers=auth_headers(benevole_user))
        assert resp.status_code == 403, f"{route} : {resp.text}"


def test_buvette_stays_readable_by_accounting(
    client: TestClient, compta_user, auth_headers, db_session
) -> None:
    """La comptabilite suit les recettes de la buvette : elle garde la lecture."""
    _seed(db_session, tier_id=int(uuid.uuid4().int % 1_000_000_000))

    for route in ("/api/v1/buvette/products", "/api/v1/buvette/sales"):
        resp = client.get(route, headers=auth_headers(compta_user))
        assert resp.status_code == 200, f"{route} : {resp.text}"


def test_buvette_writes_stay_reserved_to_admins(
    client: TestClient, compta_user, auth_headers, db_session
) -> None:
    """Lire n'est pas ecrire : la comptabilite ne modifie pas le stock."""
    product = _seed(db_session, tier_id=int(uuid.uuid4().int % 1_000_000_000))

    resp = client.patch(
        f"/api/v1/buvette/products/{product.id}",
        json={"quantity": 99},
        headers=auth_headers(compta_user),
    )
    assert resp.status_code == 403, resp.text


def test_patch_product_as_admin_benevoles(
    client: TestClient, admin_benevoles_user, auth_headers, db_session
) -> None:
    product = _seed(db_session, tier_id=int(uuid.uuid4().int % 1_000_000_000))
    resp = client.patch(
        f"/api/v1/buvette/products/{product.id}",
        json={"quantity": 50, "seuil_alerte": 10},
        headers=auth_headers(admin_benevoles_user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quantity"] == 50
    assert body["seuil_alerte"] == 10


# ---- Sync ----


def test_sync_with_mocked_client_returns_sync_result(
    client: TestClient,
    super_admin_user,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_tiers = [
        {"id": int(uuid.uuid4().int % 1_000_000_000), "label": "The", "amount": 200},
    ]

    class _FakeClient:
        def list_shop_tiers(self, *_, **__):
            return fake_tiers

    monkeypatch.setattr(
        "app.api.v1.endpoints.buvette.get_helloasso_client",
        lambda *a, **kw: _FakeClient(),
    )
    resp = client.post(
        "/api/v1/buvette/sync", headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] >= 1
    helloasso_service.reset_helloasso_client()


def test_sync_without_credentials_raises_helloasso_not_configured(
    client: TestClient,
    super_admin_user,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When credentials are missing, the HelloAsso client raises EXT_6004."""
    helloasso_service.reset_helloasso_client()
    # Force creds to empty so the client raises HELLOASSO_NOT_CONFIGURED.
    monkeypatch.setattr(
        "app.services.helloasso.default_settings.helloasso_client_id", ""
    )
    monkeypatch.setattr(
        "app.services.helloasso.default_settings.helloasso_client_secret", ""
    )
    resp = client.post(
        "/api/v1/buvette/sync", headers=auth_headers(super_admin_user)
    )
    # The exception code is EXT_6004 (HELLOASSO_NOT_CONFIGURED), HTTP 503.
    assert resp.status_code == 503, resp.text
    assert resp.json()["code"] == "EXT_6004"
    helloasso_service.reset_helloasso_client()


# ---- Webhook ----


def test_webhook_processes_order_and_decrements_stock(
    client: TestClient, db_session
) -> None:
    tid = int(uuid.uuid4().int % 1_000_000_000)
    product = _seed(db_session, tier_id=tid, quantity=10, seuil=5)
    payload = _order_payload(payment_id=5555, item_id=6666, tier_id=tid, qty=3)

    resp = client.post("/api/v1/buvette/webhook/helloasso", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"

    db_session.expire_all()
    refreshed = db_session.get(BuvetteProduct, product.id)
    assert refreshed.quantity == 7  # 10 - 3

    sales = (
        db_session.query(BuvetteSale)
        .filter(BuvetteSale.helloasso_payment_id == 5555)
        .all()
    )
    assert len(sales) == 1


def test_webhook_idempotent_on_repeat(
    client: TestClient, db_session
) -> None:
    tid = int(uuid.uuid4().int % 1_000_000_000)
    product = _seed(db_session, tier_id=tid, quantity=10, seuil=5)
    payload = _order_payload(payment_id=7777, item_id=8888, tier_id=tid, qty=2)

    r1 = client.post("/api/v1/buvette/webhook/helloasso", json=payload)
    r2 = client.post("/api/v1/buvette/webhook/helloasso", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(BuvetteProduct, product.id)
    assert refreshed.quantity == 8  # 10 - 2 (single decrement)


def test_webhook_malformed_payload_returns_200_ignored(client: TestClient) -> None:
    """Bad payloads must return 200 with status=ignored to prevent retry loops."""
    resp = client.post(
        "/api/v1/buvette/webhook/helloasso", json={"random": "garbage"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ignored"
