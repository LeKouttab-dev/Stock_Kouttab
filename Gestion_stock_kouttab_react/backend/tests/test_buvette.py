"""Tests for the Buvette / HelloAsso feature."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud import buvette as buvette_crud
from app.crud import user as user_crud
from app.db.models import BuvetteProduct, BuvetteSale
from app.schemas.buvette import BuvetteProductCreate
from app.services import helloasso as helloasso_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_admin(db: Session, role: str = "AdminBenevoles") -> tuple[str, str]:
    username = f"adm{uuid.uuid4().hex[:8]}"
    password = "Strong#Pass1"
    user_crud.create_user(
        db,
        username=username,
        password=password,
        role=role,
        email=f"{username}@example.com",
        validation_status="active",
    )
    return username, password


def _login(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _seed_product(
    db: Session, *, tier_id: int = 12345, quantity: int = 10, seuil: int = 5
) -> BuvetteProduct:
    product = buvette_crud.create_product(
        db,
        BuvetteProductCreate(
            name="Cafe",
            price_cents=150,
            quantity=quantity,
            seuil_alerte=seuil,
            emoji="☕",
            helloasso_tier_id=tier_id,
        ),
    )
    return product


def _order_payload(
    *,
    order_id: int = 999,
    payment_id: int = 8888,
    item_id: int = 7777,
    tier_id: int = 12345,
    qty: int = 2,
    amount: int = 300,
) -> dict[str, Any]:
    return {
        "eventType": "Order",
        "data": {
            "id": order_id,
            "items": [
                {
                    "id": item_id,
                    "tierId": tier_id,
                    "paymentId": payment_id,
                    "name": "Cafe",
                    "amount": amount,
                    "quantity": qty,
                    "user": {
                        "firstName": "Alice",
                        "lastName": "Martin",
                        "email": "alice@example.com",
                    },
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_products_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/buvette/products")
    assert resp.status_code == 401


def test_list_products_authenticated(
    client: TestClient, db_session: Session
) -> None:
    _seed_product(db_session, tier_id=11111, quantity=8, seuil=3)
    username, password = _make_admin(db_session)
    token = _login(client, username, password)

    resp = client.get(
        "/api/v1/buvette/products",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert any(p["helloasso_tier_id"] == 11111 for p in body)
    target = next(p for p in body if p["helloasso_tier_id"] == 11111)
    assert target["low_stock"] is False
    assert target["quantity"] == 8


def test_webhook_idempotency(client: TestClient, db_session: Session) -> None:
    """Two identical Order events must record only one sale & decrement once."""
    product = _seed_product(db_session, tier_id=22222, quantity=10, seuil=5)
    payload = _order_payload(
        payment_id=4242, item_id=4243, tier_id=22222, qty=2, amount=300
    )

    r1 = client.post("/api/v1/buvette/webhook/helloasso", json=payload)
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "ok"

    r2 = client.post("/api/v1/buvette/webhook/helloasso", json=payload)
    assert r2.status_code == 200, r2.text

    db_session.expire_all()
    refreshed = db_session.get(BuvetteProduct, product.id)
    assert refreshed is not None
    assert refreshed.quantity == 8, "Quantity should drop only once (10 -> 8)."

    sales = (
        db_session.query(BuvetteSale)
        .filter(BuvetteSale.helloasso_payment_id == 4242)
        .filter(BuvetteSale.helloasso_item_id == 4243)
        .all()
    )
    assert len(sales) == 1


def test_sync_from_helloasso_mocked(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sync endpoint should upsert tiers from a mocked HelloAsso client."""
    fake_tiers = [
        {
            "id": 33333,
            "label": "The a la menthe",
            "description": "The marocain",
            "amount": 200,
        },
        {
            "id": 33334,
            "label": "Briouates",
            "description": "Patisserie",
            "amount": 250,
        },
    ]

    class _FakeClient:
        def list_shop_tiers(self, *_: Any, **__: Any) -> list[dict[str, Any]]:
            return fake_tiers

    monkeypatch.setattr(
        "app.api.v1.endpoints.buvette.get_helloasso_client",
        lambda *a, **kw: _FakeClient(),
    )

    username, password = _make_admin(db_session, role="Super Admin")
    token = _login(client, username, password)

    resp = client.post(
        "/api/v1/buvette/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] >= 2
    assert body["updated"] == 0
    assert body["errors"] == []

    # A second sync should now report updated rows.
    resp2 = client.post(
        "/api/v1/buvette/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["updated"] >= 2
    assert body2["created"] == 0

    # Reset the helloasso singleton to keep tests isolated.
    helloasso_service.reset_helloasso_client()
