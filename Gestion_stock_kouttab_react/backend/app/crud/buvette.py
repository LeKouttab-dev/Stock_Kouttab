"""CRUD operations for Buvette products and sales (HelloAsso webhook and caisse)."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, undefer

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import BuvetteProduct, BuvetteSale
from app.services import images
from app.schemas.buvette import (
    BuvetteProductCreate,
    BuvetteProductUpdate,
    CaisseVenteIn,
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
        caisse_category=data.caisse_category,
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
    # `None` explicite est une valeur a part entiere : retirer de la tablette.
    if "caisse_category" in payload:
        product.caisse_category = payload["caisse_category"]

    # HelloAsso ecrit ces quatre champs a chaque synchronisation. Une
    # modification a la main les lui retire, sinon le prochain « Synchroniser »
    # annulerait le travail de la personne sans rien dire.
    if any(champ in payload for champ in _CHAMPS_HELLOASSO):
        product.edite_manuellement = True

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


# Les champs que la synchronisation HelloAsso ecrit — et qu'elle cesse d'ecrire
# des qu'ils ont ete modifies a la main.
_CHAMPS_HELLOASSO = ("name", "description", "price_cents", "image_url")


def get_product_by_photo_jeton(db: Session, jeton: str) -> BuvetteProduct | None:
    """Le produit dont la photo est servie sous ce jeton, photo comprise.

    `photo` est `deferred` : il faut la demander explicitement, sinon la lecture
    de l'image declencherait une seconde requete vers une base distante.
    """
    if not jeton:
        return None
    return db.execute(
        select(BuvetteProduct)
        .where(BuvetteProduct.photo_jeton == jeton)
        .options(undefer(BuvetteProduct.photo))
    ).scalars().first()


def enregistrer_photo(db: Session, product_id: int, contenu: bytes) -> BuvetteProduct:
    """Reduit la photo, l'enregistre en base, et lui donne une adresse NEUVE.

    Le jeton est retire au hasard a chaque depot. La tablette met les photos en
    cache par URL en ignorant les en-tetes de cache : reutiliser la meme adresse
    laisserait l'ancienne image affichee en caisse, parfois des jours.
    """
    product = get_product(db, product_id)
    if not product:
        raise AppException(ErrorCode.BUVETTE_PRODUCT_NOT_FOUND)

    octets, type_mime = images.preparer_photo(contenu)
    product.photo = octets
    product.photo_type = type_mime
    product.photo_jeton = secrets.token_urlsafe(24)
    # La photo est un des champs que HelloAsso ecrase : deposer la sienne vaut
    # decision, elle ne doit pas sauter a la synchronisation suivante.
    product.edite_manuellement = True
    db.commit()
    db.refresh(product)
    logger.info(
        "Photo enregistree pour le produit buvette %s (%s octets).",
        product_id,
        len(octets),
    )
    return product


def supprimer_photo(db: Session, product_id: int) -> BuvetteProduct:
    """Retire la photo. La tablette reprend alors l'emoji, jamais une case vide."""
    product = get_product(db, product_id)
    if not product:
        raise AppException(ErrorCode.BUVETTE_PRODUCT_NOT_FOUND)
    product.photo = None
    product.photo_type = None
    product.photo_jeton = None
    db.commit()
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


def _extract_helloasso_price_cents(tier: dict[str, Any]) -> int | None:
    """Prix du tier en centimes, ou ``None`` si HelloAsso ne l'expose pas.

    La boutique renvoie le prix sous ``price`` (verifie sur l'API V5 le
    2026-08-11). Le code lisait ``amount``, un champ qui n'existe pas sur un
    tier de boutique : tous les produits synchronises se retrouvaient a 0 EUR.
    ``amount`` reste accepte en second choix car c'est le nom utilise par les
    *items de commande* dans le webhook, et rien ne garantit que HelloAsso ne
    l'expose pas ailleurs.

    ``None`` — et non ``0`` — quand le prix est introuvable : un prix absent
    n'est pas un prix nul, et l'appelant doit pouvoir conserver la valeur deja
    connue plutot que de l'ecraser.
    """
    for key in ("price", "amount"):
        value = tier.get(key)
        if value is None:
            continue
        try:
            cents = int(value)
        except (TypeError, ValueError):
            continue
        if cents >= 0:
            return cents
    return None


def _extract_helloasso_image_url(tier: dict[str, Any]) -> str | None:
    """URL de l'illustration du tier, ou ``None``.

    HelloAsso imbrique l'image dans ``picture.publicUrl``. Les cles a plat
    (``imageUrl``, ``image_url``) sont conservees en repli.
    """
    picture = tier.get("picture")
    if isinstance(picture, dict):
        url = picture.get("publicUrl") or picture.get("fileName")
        if url:
            return str(url)
    for key in ("imageUrl", "image_url"):
        url = tier.get(key)
        if url:
            return str(url)
    return None


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
            price_cents = _extract_helloasso_price_cents(tier)
            image_url = _extract_helloasso_image_url(tier)
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
                    price_cents=price_cents if price_cents is not None else 0,
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
                # Un produit repris en main dans l'application n'est plus
                # alimente par HelloAsso pour ces champs : nom, description,
                # prix et photo. Sans cela, « Synchroniser » effacait un
                # libelle corrige, un prix ajuste et une photo deposee.
                # Le stock et l'horodatage continuent, eux, de se mettre a jour.
                if not existing.edite_manuellement:
                    existing.name = label
                    existing.description = description
                    # Un prix introuvable ne doit pas ecraser le prix connu :
                    # sinon une synchronisation remet a 0 EUR tout le catalogue.
                    if price_cents is not None:
                        existing.price_cents = price_cents
                    if image_url is not None:
                        existing.image_url = image_url
                else:
                    result.skipped += 1
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


def get_sales_activity(db: Session) -> tuple[datetime | None, int]:
    """Date de la derniere vente recue et nombre total de ventes.

    Sert a savoir si le webhook HelloAsso fonctionne : une vente en base est,
    par construction, une notification recue. C'est la seule verification
    possible, HelloAsso ne permettant pas de relire l'URL enregistree.

    Les ventes de la tablette sont exclues : elles ne passent pas par HelloAsso,
    et les compter afficherait un webhook « actif » qui n'a jamais rien recu.
    """
    row = db.execute(
        select(func.max(BuvetteSale.processed_at), func.count(BuvetteSale.id)).where(
            BuvetteSale.source == "helloasso"
        )
    ).one()
    return row[0], int(row[1] or 0)


def list_sales(db: Session, *, limit: int = 50, offset: int = 0) -> list[BuvetteSale]:
    stmt = (
        select(BuvetteSale)
        .order_by(BuvetteSale.processed_at.desc())
        .limit(max(1, min(limit, 500)))
        .offset(max(0, offset))
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Caisse (tablette SumUp)
# ---------------------------------------------------------------------------


def list_caisse_catalogue(db: Session) -> list[BuvetteProduct]:
    """Produits vendus par la tablette : actifs ET ranges dans un onglet."""
    stmt = (
        select(BuvetteProduct)
        .where(
            BuvetteProduct.is_active.is_(True),
            BuvetteProduct.caisse_category.is_not(None),
        )
        .order_by(BuvetteProduct.caisse_category.asc(), BuvetteProduct.name.asc())
    )
    return list(db.execute(stmt).scalars().all())


def record_caisse_sale(
    db: Session, vente: CaisseVenteIn
) -> tuple[bool, list[BuvetteProduct]]:
    """Enregistre une vente de la tablette et decremente le stock.

    Rend ``(deja_enregistree, produits_a_signaler)``. Le second element liste
    les produits qui viennent de passer sous leur seuil : leur `alert_sent` est
    deja leve, l'appelant n'a plus qu'a envoyer le courriel.

    Idempotence : la tablette renvoie une vente tant qu'elle n'a pas recu de
    reponse, et une coupure pendant la reponse est le cas normal d'un sous-sol.
    Une transaction deja connue ne touche plus au stock.
    """
    # Avant toute ecriture. Un ecart signale une tablette dereglee : enregistrer
    # quand meme graverait un chiffre d'affaires qui ne correspond a aucun
    # encaissement.
    detail = sum(l.quantity * l.unit_price_cents for l in vente.lines)
    if detail != vente.total_cents:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Le total encaisse ne correspond pas au detail du panier.",
            extras={"total_cents": vente.total_cents, "somme_des_lignes": detail},
        )

    deja = db.execute(
        select(func.count(BuvetteSale.id)).where(
            BuvetteSale.caisse_tx_id == vente.transaction_id
        )
    ).scalar_one()
    if deja:
        logger.info("Vente caisse %s deja enregistree : aucun decrement.", vente.transaction_id)
        return True, []

    ids = {l.product_id for l in vente.lines if l.product_id is not None}
    # Une seule requete pour tout le panier : la base est distante.
    produits = (
        {p.id: p for p in db.execute(select(BuvetteProduct).where(BuvetteProduct.id.in_(ids))).scalars()}
        if ids
        else {}
    )

    # L'heure de la tablette, telle qu'elle l'affichait. On garde l'heure
    # murale et on retire le decalage, comme le fait deja le pilote MySQL pour
    # les ventes HelloAsso : l'ecran des ventes lit ces dates comme locales.
    sold_at = vente.sold_at.replace(tzinfo=None) if vente.sold_at else None

    touches: dict[int, BuvetteProduct] = {}
    for rang, ligne in enumerate(vente.lines):
        produit = produits.get(ligne.product_id) if ligne.product_id is not None else None
        if ligne.product_id is not None and produit is None:
            # Supprime cote stock depuis le dernier catalogue : l'argent est
            # encaisse, la vente est gardee plutot que perdue.
            logger.warning(
                "Vente caisse %s : produit %s introuvable, ligne gardee sans decrement.",
                vente.transaction_id,
                ligne.product_id,
            )
        db.add(
            BuvetteSale(
                source="caisse",
                caisse_tx_id=vente.transaction_id,
                caisse_line=rang,
                sumup_tx_code=vente.sumup_tx_code,
                buvette_product_id=produit.id if produit else None,
                product_name_snapshot=ligne.name[:255],
                quantity_sold=ligne.quantity,
                amount_cents=ligne.quantity * ligne.unit_price_cents,
                sold_at=sold_at,
            )
        )
        if produit is not None:
            # Le comptage physique peut etre en retard sur les ventes : la vente
            # passe, le stock s'arrete a zero.
            produit.quantity = max(0, produit.quantity - ligne.quantity)
            touches[produit.id] = produit

    a_signaler: list[BuvetteProduct] = []
    for produit in touches.values():
        if produit.quantity < produit.seuil_alerte and not produit.alert_sent:
            produit.alert_sent = True
            a_signaler.append(produit)

    try:
        db.commit()
    except IntegrityError:
        # Deux envois simultanes de la meme vente : l'autre a gagne.
        db.rollback()
        logger.warning("Vente caisse %s : doublon concurrent ecarte.", vente.transaction_id)
        return True, []

    logger.info(
        "Vente caisse %s enregistree : %d ligne(s), %d centimes.",
        vente.transaction_id,
        len(vente.lines),
        vente.total_cents,
    )
    return False, a_signaler
