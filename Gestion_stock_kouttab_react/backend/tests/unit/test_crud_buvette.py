"""Unit tests for app.crud.buvette."""

from __future__ import annotations

import uuid

import pytest

from app.crud import buvette as buvette_crud
from app.schemas.buvette import BuvetteProductCreate


pytestmark = pytest.mark.unit


def _tier_id() -> int:
    # Random-ish tier id within int32 range.
    return int(uuid.uuid4().int % 1_000_000_000)


def _create_product(db, *, tier_id: int | None = None, quantity: int = 10, seuil: int = 5):
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


def _real_tier(tier_id: int, *, label: str = "Cafe capsule", price: int = 100) -> dict:
    """Tier tel que HelloAsso le renvoie reellement.

    Copie conforme d'une reponse de
    ``GET /v5/organizations/{org}/forms/Shop/buvette/public`` relevee le
    2026-08-11. Les tests precedents inventaient une cle ``amount`` absente de
    l'API : ils validaient le code contre lui-meme et laissaient passer un
    catalogue entierement price_cents=0.
    """
    return {
        "id": tier_id,
        "label": label,
        "tierType": "Product",
        "price": price,
        "vatRate": 0.0,
        "paymentFrequency": "Single",
        "isEligibleTaxReceipt": False,
        "picture": {
            "fileName": "cafe.jpg",
            "publicUrl": "https://cdn.helloasso.com/img/photos/items/shops/cafe.jpg",
        },
        "isFavorite": False,
    }


def test_sync_from_helloasso_upsert_keeps_local_quantity(db_session) -> None:
    tid = _tier_id()
    # Pre-create with quantity=42 — sync must not overwrite it.
    product = _create_product(db_session, tier_id=tid, quantity=42, seuil=5)

    result = buvette_crud.sync_from_helloasso(
        db_session,
        [_real_tier(tid, label="Cafe renamed", price=200)],
    )
    assert result.updated == 1
    assert result.created == 0

    db_session.refresh(product)
    assert product.quantity == 42  # untouched
    assert product.name == "Cafe renamed"
    assert product.price_cents == 200


def test_sync_reads_price_and_picture_from_real_helloasso_payload(db_session) -> None:
    tid = _tier_id()
    result = buvette_crud.sync_from_helloasso(db_session, [_real_tier(tid)])

    assert result.created == 1
    product = buvette_crud.get_product_by_tier_id(db_session, tid)
    assert product.price_cents == 100
    assert product.image_url == "https://cdn.helloasso.com/img/photos/items/shops/cafe.jpg"


def test_sync_never_resets_a_known_price_to_zero(db_session) -> None:
    """Un tier sans prix lisible laisse le prix existant intact."""
    tid = _tier_id()
    product = _create_product(db_session, tier_id=tid)
    assert product.price_cents == 150

    result = buvette_crud.sync_from_helloasso(
        db_session,
        [{"id": tid, "label": "Cafe sans prix"}],
    )

    assert result.updated == 1
    db_session.refresh(product)
    assert product.price_cents == 150


def test_sync_accepts_a_free_tier(db_session) -> None:
    """Un prix de 0 EUR est une valeur, pas une absence de valeur."""
    tid = _tier_id()
    product = _create_product(db_session, tier_id=tid)

    buvette_crud.sync_from_helloasso(db_session, [_real_tier(tid, price=0)])

    db_session.refresh(product)
    assert product.price_cents == 0


def test_record_sale_idempotent_on_payment_and_item(db_session) -> None:
    tid = _tier_id()
    product = _create_product(db_session, tier_id=tid, quantity=10, seuil=5)

    sale1, dec1 = buvette_crud.record_sale_and_decrement(
        db_session,
        order_id=1,
        payment_id=42,
        item_id=99,
        tier_id=tid,
        name="Cafe",
        quantity_sold=2,
        amount_cents=300,
        customer=None,
        sold_at=None,
        raw_event=None,
    )
    assert dec1 is not None
    db_session.refresh(product)
    assert product.quantity == 8

    sale2, dec2 = buvette_crud.record_sale_and_decrement(
        db_session,
        order_id=1,
        payment_id=42,
        item_id=99,
        tier_id=tid,
        name="Cafe",
        quantity_sold=2,
        amount_cents=300,
        customer=None,
        sold_at=None,
        raw_event=None,
    )
    # Same composite key → returns the existing sale, no decrement.
    assert sale2.id == sale1.id
    assert dec2 is None
    db_session.refresh(product)
    assert product.quantity == 8


def test_record_sale_decrements_and_flags_low_stock(db_session) -> None:
    tid = _tier_id()
    product = _create_product(db_session, tier_id=tid, quantity=6, seuil=5)
    assert product.alert_sent is False

    _, decremented = buvette_crud.record_sale_and_decrement(
        db_session,
        order_id=2,
        payment_id=100,
        item_id=200,
        tier_id=tid,
        name="Cafe",
        quantity_sold=4,
        amount_cents=600,
        customer=None,
        sold_at=None,
        raw_event=None,
    )
    assert decremented is not None
    db_session.refresh(product)
    assert product.quantity == 2
    assert product.quantity < product.seuil_alerte


def test_record_sale_resets_alert_when_back_above_threshold(db_session) -> None:
    """If quantity > threshold after a sale (rare but possible), alert flag is reset."""
    tid = _tier_id()
    product = _create_product(db_session, tier_id=tid, quantity=20, seuil=5)
    # Manually flag alert as previously sent.
    product.alert_sent = True
    db_session.commit()

    _, decremented = buvette_crud.record_sale_and_decrement(
        db_session,
        order_id=3,
        payment_id=300,
        item_id=400,
        tier_id=tid,
        name="Cafe",
        quantity_sold=1,
        amount_cents=150,
        customer=None,
        sold_at=None,
        raw_event=None,
    )
    assert decremented is not None
    db_session.refresh(product)
    assert product.quantity == 19
    assert product.alert_sent is False  # reset


def test_list_products_returns_inserted_one(db_session) -> None:
    tid = _tier_id()
    product = _create_product(db_session, tier_id=tid)
    products = buvette_crud.list_products(db_session)
    assert any(p.id == product.id for p in products)


def test_list_sales_pagination(db_session) -> None:
    tid = _tier_id()
    _create_product(db_session, tier_id=tid)
    for i in range(3):
        buvette_crud.record_sale_and_decrement(
            db_session,
            order_id=10 + i,
            payment_id=10000 + i,
            item_id=20000 + i,
            tier_id=tid,
            name="Cafe",
            quantity_sold=1,
            amount_cents=150,
            customer=None,
            sold_at=None,
            raw_event=None,
        )
    sales = buvette_crud.list_sales(db_session, limit=2, offset=0)
    assert len(sales) <= 2
