"""Tests for the barcode feature (Stock + Buvette + OpenFoodFacts)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud import stock as stock_crud
from app.crud import user as user_crud
from app.services import openfoodfacts as off_service


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


def _unique_barcode() -> str:
    """Return a unique 13-digit EAN-like barcode for test isolation."""
    return f"34{uuid.uuid4().int % 10**11:011d}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_stock_item_with_barcode(db_session: Session) -> None:
    """A new stock item can be created with a barcode and is persisted."""
    barcode = _unique_barcode()
    item = stock_crud.create_item(
        db_session,
        nom=f"Article {uuid.uuid4().hex[:6]}",
        categorie="Nourriture",
        sous_categorie=None,
        quantite=5,
        seuil_alerte=2,
        emoji="🍪",
        barcode=barcode,
    )
    assert item.barcode == barcode

    fetched = stock_crud.get_item_by_barcode(db_session, barcode)
    assert fetched is not None
    assert fetched.id == item.id


def test_create_two_items_same_barcode_raises_conflict(db_session: Session) -> None:
    """The second insert with an already-used barcode must raise BARCODE_DUPLICATE."""
    barcode = _unique_barcode()
    stock_crud.create_item(
        db_session,
        nom=f"Premier {uuid.uuid4().hex[:6]}",
        categorie="Nourriture",
        sous_categorie=None,
        quantite=5,
        seuil_alerte=2,
        emoji="🍪",
        barcode=barcode,
    )

    from app.core.errors import ErrorCode
    from app.core.exceptions import AppException

    with pytest.raises(AppException) as exc_info:
        stock_crud.create_item(
            db_session,
            nom=f"Doublon {uuid.uuid4().hex[:6]}",
            categorie="Nourriture",
            sous_categorie=None,
            quantite=3,
            seuil_alerte=1,
            emoji="🍪",
            barcode=barcode,
        )
    assert exc_info.value.code is ErrorCode.BARCODE_DUPLICATE
    assert exc_info.value.status_code == 409


def test_get_item_by_barcode_endpoint_found(
    client: TestClient, db_session: Session
) -> None:
    """GET /stock/items/by-barcode/{code} returns 200 + item when known."""
    barcode = _unique_barcode()
    stock_crud.create_item(
        db_session,
        nom=f"ScanItem {uuid.uuid4().hex[:6]}",
        categorie="Nourriture",
        sous_categorie=None,
        quantite=10,
        seuil_alerte=3,
        emoji="🍫",
        barcode=barcode,
    )
    username, password = _make_admin(db_session)
    token = _login(client, username, password)

    resp = client.get(
        f"/api/v1/stock/items/by-barcode/{barcode}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["barcode"] == barcode
    assert body["quantite"] == 10


def test_get_item_by_barcode_endpoint_unknown_returns_404(
    client: TestClient, db_session: Session
) -> None:
    """Unknown barcodes must give a 404 with the standard error envelope."""
    username, password = _make_admin(db_session)
    token = _login(client, username, password)

    resp = client.get(
        "/api/v1/stock/items/by-barcode/99999999999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["code"] == "RES_3003"  # STOCK_ITEM_NOT_FOUND


def test_lookup_barcode_endpoint_uses_openfoodfacts(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unified lookup falls through to OpenFoodFacts for an unknown local code."""
    # Reset any cached OFF state to keep the test deterministic.
    off_service.reset_cache()

    barcode = _unique_barcode()

    fake_off_response: dict[str, Any] = {
        "status": 1,
        "product": {
            "product_name": "Generic Cookies",
            "product_name_fr": "Biscuits aux pepites",
            "brands": "Acme",
            "image_front_small_url": "https://example.org/img.jpg",
            "image_url": "https://example.org/img-large.jpg",
            "quantity": "200 g",
            "categories_tags": ["en:snacks", "en:biscuits"],
        },
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        # Sanity-check the request the service builds.
        assert barcode in request.url.path
        return httpx.Response(200, json=fake_off_response)

    transport = httpx.MockTransport(_handler)
    real_client_cls = httpx.Client

    def _patched_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs.setdefault("transport", transport)
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr("app.services.openfoodfacts.httpx.Client", _patched_client)

    username, password = _make_admin(db_session)
    token = _login(client, username, password)

    resp = client.get(
        f"/api/v1/stock/lookup-barcode/{barcode}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["barcode"] == barcode
    assert body["found_in"] is None
    assert body["stock_item"] is None
    assert body["buvette_product"] is None
    off = body["openfoodfacts"]
    assert off is not None
    # The fr name must be preferred over the generic one.
    assert off["name"] == "Biscuits aux pepites"
    assert off["brand"] == "Acme"
    assert off["image_url"] == "https://example.org/img.jpg"

    off_service.reset_cache()
