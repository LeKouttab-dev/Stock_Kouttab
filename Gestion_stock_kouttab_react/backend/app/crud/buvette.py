"""CRUD operations for Buvette products and sales (HelloAsso webhook and caisse)."""

from __future__ import annotations

import json
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, undefer

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.core.security import validate_email_str
from app.db.models import (
    Admin,
    BuvetteProduct,
    BuvetteReapprovisionnement,
    BuvetteReglage,
    BuvetteSale,
    CaisseEtat,
    ClotureCaisse,
)
from app.services import images
from app.schemas.buvette import (
    BuvetteProductCreate,
    BuvetteProductUpdate,
    CaisseEtatIn,
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


def create_product(
    db: Session, data: BuvetteProductCreate, *, fait_par: str | None = None
) -> BuvetteProduct:
    """Cree un produit. Une quantite initiale > 0 est tracee comme premier reappro.

    Sans cette ligne « Stock initial », le recapitulatif des mouvements d'un
    inventaire verrait apparaitre du stock venu de nulle part.
    """
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
        db.flush()
        if data.quantity > 0:
            db.add(
                BuvetteReapprovisionnement(
                    buvette_product_id=product.id,
                    nom_snapshot=product.name[:255],
                    quantite=data.quantity,
                    prix_achat_unitaire_cents=None,
                    total_cents=None,
                    origine=ORIGINE_APP,
                    commentaire=COMMENTAIRE_STOCK_INITIAL,
                    fait_par=fait_par,
                    stock_avant=0,
                    stock_apres=data.quantity,
                    created_at=_maintenant_utc(),
                )
            )
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
    if "quantity" in payload:
        # Une valeur absolue lue a l'ecran effacerait une vente ou un reappro
        # concurrent, et ne laisserait aucune trace dans les mouvements.
        raise AppException(ErrorCode.VALIDATION_ERROR, detail=MESSAGE_QUANTITE_REFUSEE)
    if "name" in payload and payload["name"] is not None:
        product.name = payload["name"].strip()
    if "description" in payload:
        product.description = payload["description"]
    if "price_cents" in payload and payload["price_cents"] is not None:
        product.price_cents = payload["price_cents"]
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


def _decrementer(db: Session, produit: BuvetteProduct, quantite: int) -> None:
    """Retire `quantite` du stock EN BASE, sans descendre sous zero.

    `UPDATE ... SET quantity = CASE ...` et non `produit.quantity = ...` : la
    seconde forme ecrit une valeur absolue calculee sur une lecture anterieure,
    et effacerait un reapprovisionnement (`reapprovisionner`) commite entre la
    lecture et l'ecriture. Le produit est ensuite relu dans la transaction.
    """
    db.execute(
        update(BuvetteProduct)
        .where(BuvetteProduct.id == produit.id)
        .values(
            quantity=case(
                (BuvetteProduct.quantity > quantite, BuvetteProduct.quantity - quantite),
                else_=0,
            )
        )
        .execution_options(synchronize_session=False)
    )
    db.refresh(produit, attribute_names=["quantity"])


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
        _decrementer(db, product, quantity_sold)
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
            _decrementer(db, produit, ligne.quantity)
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



# ---------------------------------------------------------------------------
# Reapprovisionnement (increment atomique)
# ---------------------------------------------------------------------------


ORIGINE_APP = "app"
ORIGINE_TABLETTE = "tablette"
COMMENTAIRE_STOCK_INITIAL = "Stock initial"
MESSAGE_QUANTITE_REFUSEE = (
    "Le stock se change par un réapprovisionnement ou un inventaire."
)


def _maintenant_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def reapprovisionner(
    db: Session,
    product_id: int,
    quantite: int,
    *,
    prix_achat_unitaire_cents: int | None = None,
    origine: str = ORIGINE_TABLETTE,
    commentaire: str | None = None,
    fait_par: str | None = None,
) -> tuple[BuvetteProduct, BuvetteReapprovisionnement]:
    """Ajoute `quantite` au stock, de facon ATOMIQUE, et trace le reappro.

    `UPDATE ... SET quantity = quantity + :quantite` : la base fait l'addition.
    Une quantite absolue lue a l'ecran, parfois des minutes plus tot, aurait
    ecrase une vente ou un autre reappro passe entre-temps. Ici, rien ne se perd.

    Le stock APRES est relu dans la meme transaction, juste apres l'UPDATE : la
    ligne est alors verrouillee (InnoDB) jusqu'au commit, aucune vente ne peut
    s'intercaler entre l'addition et la lecture. `stock_avant` s'en deduit.

    Le dernier prix d'achat du produit est memorise s'il est fourni (ecran web) ;
    un reappro de la tablette n'en porte pas et laisse l'ancien en place.

    Le drapeau `alert_sent` retombe quand le stock repasse au seuil : la
    prochaine baisse previendra de nouveau.
    """
    if quantite < 1:
        # Le schema borne deja ; ceci protege les appels internes.
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Le reappro doit etre positif.")
    valeurs: dict[str, Any] = {"quantity": BuvetteProduct.quantity + quantite}
    if prix_achat_unitaire_cents is not None:
        valeurs["dernier_prix_achat_cents"] = prix_achat_unitaire_cents
    resultat = db.execute(
        update(BuvetteProduct)
        .where(BuvetteProduct.id == product_id)
        .values(**valeurs)
        .execution_options(synchronize_session=False)
    )
    if not resultat.rowcount:
        db.rollback()
        raise AppException(ErrorCode.BUVETTE_PRODUCT_NOT_FOUND)
    db.execute(
        update(BuvetteProduct)
        .where(
            BuvetteProduct.id == product_id,
            BuvetteProduct.quantity >= BuvetteProduct.seuil_alerte,
            BuvetteProduct.alert_sent.is_(True),
        )
        .values(alert_sent=False)
        .execution_options(synchronize_session=False)
    )
    nom, stock_apres = db.execute(
        select(BuvetteProduct.name, BuvetteProduct.quantity).where(
            BuvetteProduct.id == product_id
        )
    ).one()
    texte = (commentaire or "").strip() or None
    reappro = BuvetteReapprovisionnement(
        buvette_product_id=product_id,
        nom_snapshot=(nom or "")[:255],
        quantite=quantite,
        prix_achat_unitaire_cents=prix_achat_unitaire_cents,
        total_cents=(
            quantite * prix_achat_unitaire_cents
            if prix_achat_unitaire_cents is not None
            else None
        ),
        origine=origine,
        commentaire=texte[:255] if texte else None,
        fait_par=fait_par,
        stock_avant=stock_apres - quantite,
        stock_apres=stock_apres,
        created_at=_maintenant_utc(),
    )
    db.add(reappro)
    db.commit()
    db.refresh(reappro)
    produit = db.execute(
        select(BuvetteProduct)
        .where(BuvetteProduct.id == product_id)
        .execution_options(populate_existing=True)
    ).scalar_one()
    logger.info(
        "Reappro buvette (%s) : produit %s +%d -> %d (par %s).",
        origine,
        product_id,
        quantite,
        produit.quantity,
        fait_par,
    )
    return produit, reappro


# ---------------------------------------------------------------------------
# Moyens de paiement, journees, regroupement des ventes
# ---------------------------------------------------------------------------


PARIS = ZoneInfo("Europe/Paris")
MOYENS = ("carte", "especes", "helloasso")


def aujourd_hui() -> date:
    """La date du jour A PARIS : le serveur tourne en UTC, la buvette non."""
    return datetime.now(PARIS).date()


def moyen_de_paiement(sale: BuvetteSale) -> str:
    """`carte`, `especes` ou `helloasso`, deduit sans colonne dediee.

    Une vente de la tablette payee par SumUp porte le code de transaction rendu
    par SumUp ; une vente en especes n'en a pas. Tout ce qui n'est pas la
    tablette vient de la boutique HelloAsso.
    """
    if sale.source == "caisse":
        return "carte" if sale.sumup_tx_code else "especes"
    return "helloasso"


def _instant(sale: BuvetteSale) -> datetime:
    """Heure murale de la vente (`sold_at`), a defaut l'heure de reception."""
    instant = sale.sold_at or sale.processed_at
    return instant.replace(tzinfo=None) if instant.tzinfo else instant


def _cle_vente(sale: BuvetteSale) -> str:
    """Une vente = une transaction de la tablette, ou une commande HelloAsso."""
    if sale.source == "caisse" and sale.caisse_tx_id:
        return sale.caisse_tx_id
    if sale.helloasso_order_id is not None:
        return f"ha-{sale.helloasso_order_id}"
    # Ligne HelloAsso sans commande (ancien format) : vente a elle seule.
    return f"ha-ligne-{sale.id}"


def _verifier_periode(debut: date, fin: date, *, max_jours: int = 366) -> None:
    if fin < debut:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="La date de fin precede la date de debut."
        )
    if (fin - debut).days >= max_jours:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"Periode trop longue : {max_jours} jours au plus.",
        )


def lignes_de_la_periode(db: Session, debut: date, fin: date) -> list[BuvetteSale]:
    """Les lignes de vente dont le jour (cf. `_instant`) tombe dans [debut, fin].

    Le filtrage se fait en base sur `COALESCE(sold_at, processed_at)`, portable
    MariaDB et SQLite ; les regroupements se font ensuite en Python : quelques
    centaines de lignes par jour au plus, et aucune fonction de date propre a
    un SGBD (cf. tests/unit/test_sql_dialect_compat.py).
    """
    instant = func.coalesce(BuvetteSale.sold_at, BuvetteSale.processed_at)
    stmt = (
        select(BuvetteSale)
        .where(
            instant >= datetime.combine(debut, datetime.min.time()),
            instant < datetime.combine(fin + timedelta(days=1), datetime.min.time()),
        )
        .order_by(BuvetteSale.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _grouper(lignes: list[BuvetteSale]) -> dict[str, list[BuvetteSale]]:
    groupes: dict[str, list[BuvetteSale]] = defaultdict(list)
    for ligne in lignes:
        groupes[_cle_vente(ligne)].append(ligne)
    return groupes


def _client(lignes: list[BuvetteSale]) -> str | None:
    for ligne in lignes:
        nom = " ".join(
            p for p in (ligne.customer_first_name, ligne.customer_last_name) if p
        ).strip()
        if nom:
            return nom
    return None


def ventes_regroupees(
    lignes_vente: list[BuvetteSale], moyen: str | None = None
) -> list[dict[str, Any]]:
    """Lignes de vente regroupees par vente (cf. `_cle_vente`), plus recentes d'abord.

    Seule definition d'une « vente » et de son moyen de paiement : l'onglet
    Paiements, l'inventaire (especes) et les exports Excel la partagent.
    """
    ventes: list[dict[str, Any]] = []
    for cle, lignes in _grouper(lignes_vente).items():
        premiere = lignes[0]
        moyen_vente = moyen_de_paiement(premiere)
        if moyen and moyen_vente != moyen:
            continue
        ventes.append(
            {
                "cle": cle,
                "moyen": moyen_vente,
                "sold_at": min(_instant(l) for l in lignes),
                "total_cents": sum(l.amount_cents for l in lignes),
                "sumup_tx_code": next(
                    (l.sumup_tx_code for l in lignes if l.sumup_tx_code), None
                ),
                "helloasso_order_id": premiere.helloasso_order_id,
                "client": _client(lignes),
                "articles": [
                    {
                        "nom": l.product_name_snapshot,
                        "quantite": l.quantity_sold,
                        "montant_cents": l.amount_cents,
                    }
                    for l in sorted(lignes, key=lambda x: (x.caisse_line or 0, x.id))
                ],
            }
        )
    ventes.sort(key=lambda v: (v["sold_at"], v["cle"]), reverse=True)
    return ventes


def paiements(
    db: Session, debut: date, fin: date, moyen: str | None = None
) -> dict[str, Any]:
    """Ventes regroupees de la periode, plus recentes d'abord, avec totaux."""
    _verifier_periode(debut, fin)
    ventes = ventes_regroupees(lignes_de_la_periode(db, debut, fin), moyen)

    totaux: dict[str, int] = {f"{m}_cents": 0 for m in MOYENS}
    for vente in ventes:
        totaux[f"{vente['moyen']}_cents"] += vente["total_cents"]
    totaux["total_cents"] = sum(v["total_cents"] for v in ventes)
    totaux["nb_ventes"] = len(ventes)
    return {"paiements": ventes, "totaux": totaux}


def statistiques(db: Session, debut: date, fin: date) -> dict[str, Any]:
    """CA et nombre de ventes par jour, par heure, par produit et par moyen.

    « ventes » compte des ventes regroupees (un panier), pas des lignes.
    """
    _verifier_periode(debut, fin)
    lignes = lignes_de_la_periode(db, debut, fin)

    nb_jours = (fin - debut).days + 1
    par_jour = {debut + timedelta(days=i): [0, 0] for i in range(nb_jours)}
    par_heure = {h: [0, 0] for h in range(24)}
    par_moyen = {m: [0, 0] for m in MOYENS}
    par_produit: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for lignes_vente in _grouper(lignes).values():
        instant = min(_instant(l) for l in lignes_vente)
        total = sum(l.amount_cents for l in lignes_vente)
        moyen = moyen_de_paiement(lignes_vente[0])
        for cumul in (par_jour.get(instant.date()), par_heure[instant.hour], par_moyen[moyen]):
            if cumul is not None:
                cumul[0] += total
                cumul[1] += 1
        for l in lignes_vente:
            par_produit[l.product_name_snapshot][0] += l.quantity_sold
            par_produit[l.product_name_snapshot][1] += l.amount_cents

    produits = sorted(par_produit.items(), key=lambda kv: (-kv[1][1], kv[0]))[:15]
    return {
        "par_jour": [
            {"jour": j, "ca_cents": v[0], "ventes": v[1]} for j, v in sorted(par_jour.items())
        ],
        "par_heure": [
            {"heure": h, "ca_cents": v[0], "ventes": v[1]} for h, v in par_heure.items()
        ],
        "par_produit": [
            {"nom": nom, "quantite": v[0], "ca_cents": v[1]} for nom, v in produits
        ],
        "par_moyen": [
            {"moyen": m, "ca_cents": v[0], "ventes": v[1]} for m, v in par_moyen.items()
        ],
    }


# ---------------------------------------------------------------------------
# Cloture de caisse especes
# ---------------------------------------------------------------------------


def especes_attendues(db: Session, jour: date) -> tuple[int, int]:
    """(montant attendu en caisse, nombre de ventes en especes) pour ce jour.

    Seules les ventes de la tablette sans code SumUp sont des especes : une
    commande HelloAsso est payee en ligne et n'entre jamais dans la caisse.
    """
    lignes = [
        l
        for l in lignes_de_la_periode(db, jour, jour)
        if moyen_de_paiement(l) == "especes"
    ]
    return sum(l.amount_cents for l in lignes), len(_grouper(lignes))


def get_cloture(db: Session, jour: date) -> ClotureCaisse | None:
    return db.execute(
        select(ClotureCaisse).where(ClotureCaisse.jour == jour)
    ).scalar_one_or_none()


def list_clotures(db: Session, limit: int = 30) -> list[ClotureCaisse]:
    return list(
        db.execute(
            select(ClotureCaisse)
            .order_by(ClotureCaisse.jour.desc(), ClotureCaisse.id.desc())
            .limit(max(1, min(limit, 366)))
        ).scalars()
    )


def cloturer(
    db: Session,
    *,
    jour: date,
    compte_cents: int,
    commentaire: str | None,
    saisi_par: str | None,
) -> ClotureCaisse:
    """Enregistre la cloture du jour. Une seule par jour (409 sinon).

    L'attendu est calcule ICI, au moment de la saisie, et fige avec l'ecart :
    il ne doit pas venir de l'ecran, qui peut afficher un chiffre perime.
    """
    if jour > aujourd_hui():
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="On ne cloture pas une journee a venir."
        )
    if get_cloture(db, jour) is not None:
        raise AppException(
            ErrorCode.CONFLICT, detail="La caisse de ce jour est deja cloturee."
        )
    attendu, _ = especes_attendues(db, jour)
    texte = (commentaire or "").strip() or None
    cloture = ClotureCaisse(
        jour=jour,
        attendu_cents=attendu,
        compte_cents=compte_cents,
        ecart_cents=compte_cents - attendu,
        commentaire=texte,
        saisi_par=saisi_par,
        created_at=datetime.utcnow(),
    )
    db.add(cloture)
    try:
        db.commit()
    except IntegrityError as exc:
        # Deux saisies simultanees : l'index unique sur `jour` a tranche.
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail="La caisse de ce jour est deja cloturee."
        ) from exc
    db.refresh(cloture)
    logger.info(
        "Cloture caisse %s : attendu %d, compte %d, ecart %d (par %s).",
        jour,
        attendu,
        compte_cents,
        cloture.ecart_cents,
        saisi_par,
    )
    return cloture


# ---------------------------------------------------------------------------
# Etat de la tablette
# ---------------------------------------------------------------------------


def enregistrer_etat(db: Session, etat: CaisseEtatIn, *, _essai: int = 0) -> CaisseEtat:
    """Remplace le dernier etat connu de la tablette (ligne unique)."""
    ligne = db.get(CaisseEtat, CaisseEtat.ID_UNIQUE)
    if ligne is None:
        ligne = CaisseEtat(id=CaisseEtat.ID_UNIQUE)
        db.add(ligne)
    for champ, valeur in etat.model_dump().items():
        setattr(ligne, champ, valeur)
    ligne.recu_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
    except IntegrityError:
        # Premier releve recu deux fois en meme temps : l'autre a cree la ligne.
        db.rollback()
        if _essai:
            raise
        return enregistrer_etat(db, etat, _essai=1)
    return ligne


def get_etat(db: Session) -> CaisseEtat | None:
    return db.get(CaisseEtat, CaisseEtat.ID_UNIQUE)


def secondes_depuis(recu_at: datetime, maintenant: datetime | None = None) -> int:
    maintenant = maintenant or datetime.now(timezone.utc).replace(tzinfo=None)
    return max(0, int((maintenant - recu_at).total_seconds()))


# ---------------------------------------------------------------------------
# Reglages et destinataires des courriels de la buvette
# ---------------------------------------------------------------------------


REGLAGE_DESTINATAIRES = "recap_destinataires"
REGLAGE_DERNIER_RECAP = "recap_dernier_envoi"

# Repli si la ligne manque (base creee sans la migration b2c8d4e6f1a3, comme la
# base de test). La migration amorce la meme liste.
DESTINATAIRES_PAR_DEFAUT = [
    "abde.rrahman.marght@gmail.com",
    "benfdila.omir@gmail.com",
    "comptabilite@lekouttab.fr",
    "ThaoDaniel75@gmail.com",
    "daaabou4@gmail.com",
]

ROLE_ADMIN_STOCK = "AdminStock"


def lire_reglage(db: Session, cle: str, defaut: Any = None) -> Any:
    ligne = db.get(BuvetteReglage, cle)
    if ligne is None or ligne.valeur is None:
        return defaut
    try:
        return json.loads(ligne.valeur)
    except ValueError:
        logger.warning("Reglage buvette %s illisible : %r", cle, ligne.valeur)
        return defaut


def ecrire_reglage(db: Session, cle: str, valeur: Any) -> None:
    ligne = db.get(BuvetteReglage, cle)
    if ligne is None:
        ligne = BuvetteReglage(cle=cle)
        db.add(ligne)
    ligne.valeur = json.dumps(valeur, ensure_ascii=False)
    ligne.updated_at = datetime.utcnow()
    db.commit()


def destinataires_recap(db: Session) -> list[str]:
    valeur = lire_reglage(db, REGLAGE_DESTINATAIRES, None)
    if not isinstance(valeur, list):
        return list(DESTINATAIRES_PAR_DEFAUT)
    return [str(v) for v in valeur if v]


def enregistrer_destinataires(db: Session, adresses: list[str]) -> list[str]:
    """Valide, nettoie, dedoublonne (sans tenir compte de la casse) et enregistre."""
    propres: list[str] = []
    vues: set[str] = set()
    invalides: list[str] = []
    for brute in adresses:
        adresse = (brute or "").strip()
        if not adresse:
            continue
        if not validate_email_str(adresse):
            invalides.append(adresse)
            continue
        if adresse.lower() in vues:
            continue
        vues.add(adresse.lower())
        propres.append(adresse)
    if invalides:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Adresse(s) e-mail invalide(s) : " + ", ".join(invalides),
            extras={"invalides": invalides},
        )
    ecrire_reglage(db, REGLAGE_DESTINATAIRES, propres)
    return propres


def comptes_admin_stock(db: Session) -> list[Admin]:
    """Comptes ACTIFS du role AdminStock (un compte en attente ne recoit rien)."""
    return list(
        db.execute(
            select(Admin)
            .where(Admin.role == ROLE_ADMIN_STOCK, Admin.validation_status == "active")
            .order_by(Admin.id.asc())
        ).scalars()
    )


def destinataires_buvette(db: Session) -> list[str]:
    """Qui recoit les courriels de la buvette (alertes de stock bas ET recap).

    Les comptes AdminStock actifs, plus la liste des reglages, dedoublonnes sans
    tenir compte de la casse. Plus jamais « tous les AdminBenevoles et Super
    Admin » : le 09/10/2026, onze personnes ont recu cinq alertes chacune.
    """
    resultat: list[str] = []
    vues: set[str] = set()
    candidats = [c.email for c in comptes_admin_stock(db)] + destinataires_recap(db)
    for adresse in candidats:
        adresse = (adresse or "").strip()
        if adresse and adresse.lower() not in vues:
            vues.add(adresse.lower())
            resultat.append(adresse)
    return resultat
