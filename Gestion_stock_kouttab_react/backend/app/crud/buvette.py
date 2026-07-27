"""CRUD operations for Buvette products and HelloAsso-driven sales."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import BuvetteProduct, BuvetteSale
from app.schemas.buvette import (
    BuvetteProductCreate,
    BuvetteProductUpdate,
    SyncResult,
)
from app.utils.validators import validate_barcode


logger = get_logger("crud.buvette")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


def list_products(db: Session) -> list[BuvetteProduct]:
    stmt = select(BuvetteProduct).order_by(
        BuvetteProduct.is_active.desc(), BuvetteProduct.name.asc()
    )
    return list(db.execute(stmt).scalars().all())


def get_product(db: Session, product_id: int) -> BuvetteProduct | None:
    return db.get(BuvetteProduct, product_id)


def get_product_by_tier_id(db: Session, tier_id: int) -> BuvetteProduct | None:
    if tier_id is None:
        return None
    return db.execute(
        select(BuvetteProduct).where(BuvetteProduct.helloasso_tier_id == tier_id)
    ).scalar_one_or_none()


def get_product_by_barcode(db: Session, barcode: str) -> BuvetteProduct | None:
    """Return the buvette product whose barcode matches, or ``None``."""
    if not barcode:
        return None
    return db.execute(
        select(BuvetteProduct).where(BuvetteProduct.barcode == barcode)
    ).scalar_one_or_none()


def _handle_product_integrity_error(
    db: Session,
    exc: IntegrityError,
    *,
    attempted_barcode: str | None,
    attempted_tier_id: int | None,
) -> None:
    """Translate a SQLAlchemy IntegrityError into a precise AppException."""
    db.rollback()
    if attempted_barcode:
        existing = get_product_by_barcode(db, attempted_barcode)
        if existing is not None:
            raise AppException(
                ErrorCode.BARCODE_DUPLICATE,
                detail=(
                    "Ce code-barres est deja associe a un autre produit "
                    f"buvette : {existing.name}."
                ),
                extras={
                    "existing_product_id": existing.id,
                    "existing_product_name": existing.name,
                },
            ) from exc
    if attempted_tier_id is not None:
        raise AppException(
            ErrorCode.CONFLICT,
            detail="Un produit avec ce tier HelloAsso existe deja.",
        ) from exc
    raise AppException(
        ErrorCode.CONFLICT,
        detail="Conflit avec un produit buvette existant.",
    ) from exc


def create_product(db: Session, data: BuvetteProductCreate) -> BuvetteProduct:
    barcode_clean = validate_barcode(data.barcode)
    product = BuvetteProduct(
        helloasso_tier_id=data.helloasso_tier_id,
        name=data.name.strip(),
        description=data.description,
        price_cents=data.price_cents,
        quantity=data.quantity,
        seuil_alerte=data.seuil_alerte,
        emoji=data.emoji or "🥤",
        image_url=data.image_url,
        barcode=barcode_clean,
        is_active=data.is_active,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        _handle_product_integrity_error(
            db,
            exc,
            attempted_barcode=barcode_clean,
            attempted_tier_id=data.helloasso_tier_id,
        )
    db.refresh(product)
    return product


def update_product(
    db: Session, product_id: int, data: BuvetteProductUpdate
) -> BuvetteProduct:
    product = get_product(db, product_id)
    if not product:
        raise AppException(ErrorCode.BUVETTE_PRODUCT_NOT_FOUND)

    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"] is not None:
        product.name = payload["name"].strip()
    if "description" in payload:
        product.description = payload["description"]
    if "price_cents" in payload and payload["price_cents"] is not None:
        product.price_cents = payload["price_cents"]
    if "quantity" in payload and payload["quantity"] is not None:
        product.quantity = payload["quantity"]
    if "seuil_alerte" in payload and payload["seuil_alerte"] is not None:
        product.seuil_alerte = payload["seuil_alerte"]
    if "emoji" in payload and payload["emoji"] is not None:
        product.emoji = payload["emoji"]
    if "image_url" in payload:
        product.image_url = payload["image_url"]
    if "is_active" in payload and payload["is_active"] is not None:
        product.is_active = payload["is_active"]

    barcode_clean: str | None = None
    if "barcode" in payload:
        barcode_clean = validate_barcode(payload["barcode"])
        product.barcode = barcode_clean

    # Reset alert flag if quantity now meets threshold.
    if product.quantity >= product.seuil_alerte and product.alert_sent:
        product.alert_sent = False

    try:
        db.commit()
    except IntegrityError as exc:
        _handle_product_integrity_error(
            db,
            exc,
            attempted_barcode=barcode_clean,
            attempted_tier_id=None,
        )
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    if not product:
        raise AppException(ErrorCode.BUVETTE_PRODUCT_NOT_FOUND)
    db.delete(product)
    db.commit()


# ---------------------------------------------------------------------------
# HelloAsso sync
# ---------------------------------------------------------------------------


def _extract_helloasso_quantity(tier: dict[str, Any]) -> int | None:
    """Try several HelloAsso field names to find the available stock.

    HelloAsso V5 isn't 100% consistent — depending on shop config, a tier
    can carry the available stock under any of these keys. Returns ``None``
    if no quantity info is present (unlimited stock or missing field).
    """
    for key in (
        "currentQuantityAvailable",
        "remainingQuantity",
        "maxAvailableQuantity",
        "stock",
        "quantity",
    ):
        value = tier.get(key)
        if value is None:
            continue
        try:
            qty = int(value)
            if qty >= 0:
                return qty
        except (TypeError, ValueError):
            continue
    return None


def sync_from_helloasso(db: Session, tiers: list[dict[str, Any]]) -> SyncResult:
    """Upsert products from a list of HelloAsso tiers.

    Quantity sync rules :
    - **New product** : always copy the HelloAsso quantity (defaults to 0
      if HelloAsso doesn't expose it).
    - **Existing product whose local quantity is still 0** : copy from
      HelloAsso (the user hasn't done any manual restock yet, so HelloAsso
      remains the source of truth).
    - **Existing product with quantity > 0** : never overridden (the local
      stock is the source of truth once a manual restock has occurred —
      sales arrive via the webhook anyway).
    """
    result = SyncResult()
    now = datetime.utcnow()

    for tier in tiers:
        try:
            tier_id = tier.get("id")
            if tier_id is None:
                result.skipped += 1
                result.errors.append("tier without id")
                continue
            try:
                tier_id_int = int(tier_id)
            except (TypeError, ValueError):
                result.skipped += 1
                result.errors.append(f"tier id not int: {tier_id!r}")
                continue

            label = (tier.get("label") or tier.get("name") or "").strip()
            if not label:
                result.skipped += 1
                result.errors.append(f"tier {tier_id_int} without label")
                continue

            description = tier.get("description")
            amount = tier.get("amount")
            try:
                amount_cents = int(amount) if amount is not None else 0
            except (TypeError, ValueError):
                amount_cents = 0

            image_url = tier.get("imageUrl") or tier.get("image_url")
            helloasso_qty = _extract_helloasso_quantity(tier)
            logger.info(
                "HelloAsso tier %s '%s' : qty extracted = %s (raw keys: %s)",
                tier_id_int,
                label,
                helloasso_qty,
                {
                    k: tier.get(k)
                    for k in (
                        "currentQuantityAvailable",
                        "remainingQuantity",
                        "maxAvailableQuantity",
                        "stock",
                        "quantity",
                    )
                    if k in tier
                },
            )

            existing = get_product_by_tier_id(db, tier_id_int)
            if existing is None:
                product = BuvetteProduct(
                    helloasso_tier_id=tier_id_int,
                    name=label,
                    description=description,
                    price_cents=amount_cents,
                    quantity=helloasso_qty if helloasso_qty is not None else 0,
                    seuil_alerte=5,
                    emoji="🥤",
                    image_url=image_url,
                    is_active=True,
                    last_synced_at=now,
                )
                db.add(product)
                result.created += 1
            else:
                existing.name = label
                existing.description = description
                existing.price_cents = amount_cents
                if image_url is not None:
                    existing.image_url = image_url
                # Only seed the quantity if local stock is still 0 (initial state).
                # Once the user has set a real quantity, we trust the local count.
                if existing.quantity == 0 and helloasso_qty is not None and helloasso_qty > 0:
                    existing.quantity = helloasso_qty
                    # Reset alert flag if we just refilled above the threshold.
                    if existing.quantity >= existing.seuil_alerte and existing.alert_sent:
                        existing.alert_sent = False
                existing.last_synced_at = now
                result.updated += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("sync_from_helloasso: tier failed: %s", exc)
            result.errors.append(str(exc))
            result.skipped += 1

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception("sync_from_helloasso commit failed: %s", exc)
        result.errors.append(f"commit failed: {exc}")
    return result


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


def _find_existing_sale(
    db: Session, payment_id: int | None, item_id: int | None
) -> BuvetteSale | None:
    if payment_id is None or item_id is None:
        return None
    return db.execute(
        select(BuvetteSale).where(
            and_(
                BuvetteSale.helloasso_payment_id == payment_id,
                BuvetteSale.helloasso_item_id == item_id,
            )
        )
    ).scalar_one_or_none()


def record_sale_and_decrement(
    db: Session,
    *,
    order_id: int | None,
    payment_id: int | None,
    item_id: int | None,
    tier_id: int | None,
    name: str,
    quantity_sold: int,
    amount_cents: int,
    customer: dict[str, Any] | None,
    sold_at: datetime | None,
    raw_event: dict[str, Any] | None,
) -> tuple[BuvetteSale, BuvetteProduct | None]:
    """Record a sale (idempotent) and decrement product quantity if known.

    Idempotency key: ``(helloasso_payment_id, helloasso_item_id)``.

    Returns ``(sale, product_or_none)``. The second element is ``None`` if the
    sale was already recorded (no decrement happened) **or** if the product
    matching ``tier_id`` is unknown.
    """
    if quantity_sold <= 0:
        quantity_sold = 1

    existing = _find_existing_sale(db, payment_id, item_id)
    if existing is not None:
        logger.info(
            "Buvette sale already recorded (payment_id=%s item_id=%s) — skipping decrement.",
            payment_id,
            item_id,
        )
        return existing, None

    product = get_product_by_tier_id(db, tier_id) if tier_id is not None else None

    customer = customer or {}
    sale = BuvetteSale(
        helloasso_order_id=order_id,
        helloasso_payment_id=payment_id,
        helloasso_item_id=item_id,
        buvette_product_id=product.id if product else None,
        product_name_snapshot=name[:255] if name else "Produit inconnu",
        quantity_sold=quantity_sold,
        amount_cents=amount_cents,
        customer_first_name=customer.get("firstName") or customer.get("first_name"),
        customer_last_name=customer.get("lastName") or customer.get("last_name"),
        customer_email=customer.get("email"),
        raw_event=json.dumps(raw_event, ensure_ascii=False, default=str)
        if raw_event is not None
        else None,
        sold_at=sold_at,
    )
    db.add(sale)

    decremented_product: BuvetteProduct | None = None
    if product is not None:
        product.quantity = max(0, product.quantity - quantity_sold)
        # Reset / raise alert flag accordingly.
        if product.quantity >= product.seuil_alerte and product.alert_sent:
            product.alert_sent = False
        decremented_product = product

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Race condition: another worker just inserted the same sale.
        existing = _find_existing_sale(db, payment_id, item_id)
        if existing is not None:
            logger.warning(
                "Buvette sale insert raced (payment_id=%s item_id=%s).",
                payment_id,
                item_id,
            )
            return existing, None
        logger.exception("record_sale_and_decrement integrity error: %s", exc)
        raise

    db.refresh(sale)
    if decremented_product is not None:
        db.refresh(decremented_product)
    return sale, decremented_product


def list_sales(db: Session, *, limit: int = 50, offset: int = 0) -> list[BuvetteSale]:
    stmt = (
        select(BuvetteSale)
        .order_by(BuvetteSale.processed_at.desc())
        .limit(max(1, min(limit, 500)))
        .offset(max(0, offset))
    )
    return list(db.execute(stmt).scalars().all())
