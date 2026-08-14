"""Stock, categories, sub-categories, modifications and statistics CRUD."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.db.models import Admin, Category, Stock, StockModification, SubCategory
from app.utils.validators import validate_barcode, validate_image_url


# ---- Items -----------------------------------------------------------------

def list_items(
    db: Session,
    *,
    categorie: str | None = None,
    sous_categorie: str | None = None,
    only_alerts: bool = False,
) -> list[Stock]:
    stmt = select(Stock)
    if categorie:
        stmt = stmt.where(Stock.categorie == categorie)
    if sous_categorie:
        stmt = stmt.where(Stock.sous_categorie == sous_categorie)
    if only_alerts:
        stmt = stmt.where(Stock.quantite < Stock.seuil_alerte)
    stmt = stmt.order_by(Stock.categorie.asc(), Stock.nom.asc())
    return list(db.execute(stmt).scalars().all())


def get_item(db: Session, stock_id: int) -> Stock | None:
    return db.get(Stock, stock_id)


def get_item_by_name(db: Session, name: str) -> Stock | None:
    return db.execute(select(Stock).where(Stock.nom == name)).scalar_one_or_none()


def get_item_by_barcode(db: Session, barcode: str) -> Stock | None:
    """Return the stock item whose barcode matches, or ``None``."""
    if not barcode:
        return None
    return db.execute(
        select(Stock).where(Stock.barcode == barcode)
    ).scalar_one_or_none()


def _handle_stock_integrity_error(
    db: Session, exc: IntegrityError, *, attempted_barcode: str | None
) -> None:
    """Translate a SQLAlchemy IntegrityError into a precise AppException.

    Distinguishes the barcode UNIQUE conflict from the legacy ``nom`` UNIQUE
    conflict so the frontend can display a contextual message.
    """
    db.rollback()
    if attempted_barcode:
        existing = get_item_by_barcode(db, attempted_barcode)
        if existing is not None:
            raise AppException(
                ErrorCode.BARCODE_DUPLICATE,
                detail=(
                    "Ce code-barres est deja associe a un autre article : "
                    f"{existing.nom}."
                ),
                extras={"existing_item_id": existing.id, "existing_item_name": existing.nom},
            ) from exc
    raise AppException(ErrorCode.STOCK_ITEM_DUPLICATE) from exc


def create_item(
    db: Session,
    *,
    nom: str,
    categorie: str,
    sous_categorie: str | None,
    quantite: int,
    seuil_alerte: int,
    emoji: str | None = "📦",
    image_url: str | None = None,
    barcode: str | None = None,
) -> Stock:
    barcode_clean = validate_barcode(barcode)
    item = Stock(
        nom=nom.strip(),
        categorie=categorie.strip(),
        sous_categorie=sous_categorie.strip() if sous_categorie else None,
        quantite=quantite,
        seuil_alerte=seuil_alerte,
        emoji=emoji or "📦",
        image_url=validate_image_url(image_url),
        barcode=barcode_clean,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        _handle_stock_integrity_error(db, exc, attempted_barcode=barcode_clean)
    db.refresh(item)
    return item


def update_item(
    db: Session,
    stock_id: int,
    *,
    nom: str | None = None,
    categorie: str | None = None,
    sous_categorie: str | None = None,
    quantite: int | None = None,
    seuil_alerte: int | None = None,
    emoji: str | None = None,
    image_url: str | None = None,
    image_url_set: bool = False,
    barcode: str | None = None,
    barcode_set: bool = False,
) -> Stock:
    """Update a stock item.

    The ``barcode_set`` flag distinguishes "no change" from "set to None / new
    value" since ``None`` is a legitimate value for a barcode (clearing it).
    Callers built from a ``model_dump(exclude_unset=True)`` should pass
    ``barcode_set=True`` when ``barcode`` is among the updated fields.

    ``image_url_set`` joue le meme role pour la photo : sans lui, on ne pourrait
    que la remplacer, jamais la retirer — une photo erronee resterait collee a
    l'article.
    """
    item = get_item(db, stock_id)
    if not item:
        raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)
    if nom is not None:
        item.nom = nom.strip()
    if categorie is not None:
        item.categorie = categorie.strip()
    if sous_categorie is not None:
        item.sous_categorie = sous_categorie.strip() if sous_categorie else None
    if quantite is not None:
        item.quantite = quantite
    if seuil_alerte is not None:
        item.seuil_alerte = seuil_alerte
    if emoji is not None:
        item.emoji = emoji
    if image_url_set:
        item.image_url = validate_image_url(image_url)

    barcode_clean: str | None = None
    if barcode_set:
        barcode_clean = validate_barcode(barcode)
        item.barcode = barcode_clean
    try:
        db.commit()
    except IntegrityError as exc:
        _handle_stock_integrity_error(db, exc, attempted_barcode=barcode_clean)
    db.refresh(item)
    _reset_alert_if_above(db, item)
    return item


def delete_item(db: Session, stock_id: int) -> None:
    item = get_item(db, stock_id)
    if not item:
        raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)
    db.delete(item)
    db.commit()


def _reset_alert_if_above(db: Session, item: Stock) -> None:
    """Reset alert flag when quantity goes back above threshold."""
    if item.quantite >= item.seuil_alerte and item.alert_sent:
        item.alert_sent = False
        db.commit()
        db.refresh(item)


def update_quantity_direct(
    db: Session,
    stock_id: int,
    new_quantity: int,
    user_id: int,
) -> tuple[Stock, bool]:
    """Directly update a stock quantity (admin) and log the modification.

    Returns ``(item, alert_to_send)`` where ``alert_to_send`` is True when the
    caller should fire an email alert (low stock, not yet notified).
    """
    item = get_item(db, stock_id)
    if not item:
        raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)

    old_quantity = item.quantite
    item.quantite = new_quantity

    alert_to_send = False
    if new_quantity < item.seuil_alerte and not item.alert_sent:
        alert_to_send = True
        item.alert_sent = True
    elif new_quantity >= item.seuil_alerte and item.alert_sent:
        # Reset the alert flag so a future drop will re-trigger an email.
        item.alert_sent = False

    modification = StockModification(
        id_user=user_id,
        id_stock=stock_id,
        quantite_actuelle=old_quantity,
        quantite_demandee=new_quantity,
        status="Approuvée",
        approuve_par=user_id,
        date_approbation=datetime.now(timezone.utc),
        commentaires="Modification directe par admin.",
    )
    db.add(modification)
    db.commit()
    db.refresh(item)
    return item, alert_to_send


def get_low_stock_items(db: Session) -> list[Stock]:
    stmt = (
        select(Stock)
        .where(Stock.quantite < Stock.seuil_alerte)
        .order_by(Stock.quantite.asc())
    )
    return list(db.execute(stmt).scalars().all())


# ---- Categories ------------------------------------------------------------

def list_categories(db: Session) -> list[Category]:
    return list(db.execute(select(Category).order_by(Category.nom.asc())).scalars().all())


def add_category(db: Session, *, nom: str, is_default: bool = False) -> Category:
    cat = Category(nom=nom.strip(), is_default=is_default)
    db.add(cat)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.CATEGORY_DUPLICATE) from exc
    db.refresh(cat)
    return cat


def rename_category(db: Session, *, old_name: str, new_name: str) -> Category:
    cat = db.execute(select(Category).where(Category.nom == old_name)).scalar_one_or_none()
    if not cat:
        raise AppException(ErrorCode.CATEGORY_NOT_FOUND)
    new_clean = new_name.strip()
    if not new_clean:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Nouveau nom de categorie invalide."
        )
    # Update related rows
    db.execute(
        Stock.__table__.update()
        .where(Stock.categorie == old_name)
        .values(categorie=new_clean)
    )
    db.execute(
        SubCategory.__table__.update()
        .where(SubCategory.nom_categorie == old_name)
        .values(nom_categorie=new_clean)
    )
    cat.nom = new_clean
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.CATEGORY_DUPLICATE) from exc
    db.refresh(cat)
    return cat


def delete_category(db: Session, *, nom: str) -> None:
    cat = db.execute(select(Category).where(Category.nom == nom)).scalar_one_or_none()
    if not cat:
        raise AppException(ErrorCode.CATEGORY_NOT_FOUND)
    nb_items = db.execute(
        select(func.count()).select_from(Stock).where(Stock.categorie == nom)
    ).scalar_one()
    if nb_items:
        raise AppException(
            ErrorCode.CATEGORY_HAS_ITEMS,
            detail=(
                f"Impossible de supprimer : {nb_items} article(s) utilisent cette categorie."
            ),
            extras={"items_count": int(nb_items)},
        )
    # Remove sub-categories
    db.execute(
        SubCategory.__table__.delete().where(SubCategory.nom_categorie == nom)
    )
    db.delete(cat)
    db.commit()


# ---- Sub-categories --------------------------------------------------------

def list_subcategories(db: Session, *, categorie: str | None = None) -> list[SubCategory]:
    stmt = select(SubCategory).order_by(
        SubCategory.nom_categorie.asc(), SubCategory.nom_sous_categorie.asc()
    )
    if categorie:
        stmt = stmt.where(SubCategory.nom_categorie == categorie)
    return list(db.execute(stmt).scalars().all())


def add_subcategory(db: Session, *, nom_categorie: str, nom_sous_categorie: str) -> SubCategory:
    sub = SubCategory(
        nom_categorie=nom_categorie.strip(),
        nom_sous_categorie=nom_sous_categorie.strip(),
    )
    db.add(sub)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.SUBCATEGORY_DUPLICATE) from exc
    db.refresh(sub)
    return sub


def update_subcategory(
    db: Session,
    sub_id: int,
    *,
    nom_categorie: str | None = None,
    nom_sous_categorie: str | None = None,
) -> SubCategory:
    sub = db.get(SubCategory, sub_id)
    if not sub:
        raise AppException(ErrorCode.SUBCATEGORY_NOT_FOUND)
    old_cat = sub.nom_categorie
    old_sub = sub.nom_sous_categorie
    if nom_categorie is not None:
        sub.nom_categorie = nom_categorie.strip()
    if nom_sous_categorie is not None:
        sub.nom_sous_categorie = nom_sous_categorie.strip()
    # Cascade rename to Stock entries
    db.execute(
        Stock.__table__.update()
        .where(Stock.categorie == old_cat, Stock.sous_categorie == old_sub)
        .values(
            categorie=sub.nom_categorie,
            sous_categorie=sub.nom_sous_categorie,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.SUBCATEGORY_DUPLICATE) from exc
    db.refresh(sub)
    return sub


def delete_subcategory(db: Session, sub_id: int) -> None:
    sub = db.get(SubCategory, sub_id)
    if not sub:
        raise AppException(ErrorCode.SUBCATEGORY_NOT_FOUND)
    nb_items = db.execute(
        select(func.count())
        .select_from(Stock)
        .where(
            Stock.categorie == sub.nom_categorie,
            Stock.sous_categorie == sub.nom_sous_categorie,
        )
    ).scalar_one()
    if nb_items:
        raise AppException(
            ErrorCode.SUBCATEGORY_HAS_ITEMS,
            detail=(
                f"Impossible de supprimer : {nb_items} article(s) "
                "utilisent cette sous-categorie."
            ),
            extras={"items_count": int(nb_items)},
        )
    db.delete(sub)
    db.commit()


# ---- Modifications (workflow) ---------------------------------------------

def create_modification_request(
    db: Session,
    *,
    user_id: int,
    stock_id: int,
    requested_qty: int,
    commentaires: str | None = None,
) -> StockModification:
    item = get_item(db, stock_id)
    if not item:
        raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)
    if requested_qty < 0:
        raise AppException(ErrorCode.INVALID_QUANTITY)
    modif = StockModification(
        id_user=user_id,
        id_stock=stock_id,
        quantite_actuelle=item.quantite,
        quantite_demandee=requested_qty,
        status="En attente",
        commentaires=commentaires,
    )
    db.add(modif)
    db.commit()
    db.refresh(modif)
    return modif


def list_modifications(
    db: Session,
    *,
    status: str | None = None,
    days: int | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            StockModification,
            Admin.username,
            Admin.nom.label("user_nom"),
            Admin.prenom.label("user_prenom"),
            Stock.nom.label("stock_nom"),
            Stock.categorie.label("stock_categorie"),
        )
        .join(Admin, Admin.id == StockModification.id_user)
        .join(Stock, Stock.id == StockModification.id_stock)
        .order_by(StockModification.date_demande.desc())
    )
    if status:
        stmt = stmt.where(StockModification.status == status)
    if days is not None and days > 0:
        threshold = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(StockModification.date_demande >= threshold)

    rows = db.execute(stmt).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        modif: StockModification = row[0]
        full_name = " ".join([p for p in [row.user_prenom, row.user_nom] if p]) or row.username
        out.append(
            {
                "id": modif.id,
                "id_user": modif.id_user,
                "id_stock": modif.id_stock,
                "quantite_actuelle": modif.quantite_actuelle,
                "quantite_demandee": modif.quantite_demandee,
                "date_demande": modif.date_demande,
                "status": modif.status,
                "approuve_par": modif.approuve_par,
                "date_approbation": modif.date_approbation,
                "commentaires": modif.commentaires,
                "user_username": row.username,
                "user_full_name": full_name,
                "stock_nom": row.stock_nom,
                "stock_categorie": row.stock_categorie,
            }
        )
    return out


def approve_modification(
    db: Session,
    modif_id: int,
    *,
    approver_id: int,
) -> tuple[StockModification, Stock, bool]:
    modif = db.get(StockModification, modif_id)
    if not modif:
        raise AppException(ErrorCode.MODIFICATION_NOT_FOUND)
    if modif.status != "En attente":
        raise AppException(ErrorCode.MODIFICATION_NOT_PENDING)
    item = get_item(db, modif.id_stock)
    if not item:
        raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)

    item.quantite = modif.quantite_demandee
    alert_to_send = False
    if item.quantite < item.seuil_alerte and not item.alert_sent:
        alert_to_send = True
        item.alert_sent = True
    elif item.quantite >= item.seuil_alerte and item.alert_sent:
        item.alert_sent = False

    modif.status = "Approuvée"
    modif.approuve_par = approver_id
    modif.date_approbation = datetime.now(timezone.utc)
    db.commit()
    db.refresh(modif)
    db.refresh(item)
    return modif, item, alert_to_send


def refuse_modification(db: Session, modif_id: int, *, approver_id: int) -> StockModification:
    modif = db.get(StockModification, modif_id)
    if not modif:
        raise AppException(ErrorCode.MODIFICATION_NOT_FOUND)
    if modif.status != "En attente":
        raise AppException(ErrorCode.MODIFICATION_NOT_PENDING)
    modif.status = "Refusée"
    modif.approuve_par = approver_id
    modif.date_approbation = datetime.now(timezone.utc)
    db.commit()
    db.refresh(modif)
    return modif


# ---- Statistics ------------------------------------------------------------

def get_stock_statistics(db: Session) -> dict[str, Any]:
    total_articles = db.execute(select(func.count()).select_from(Stock)).scalar_one() or 0
    total_quantite = db.execute(select(func.coalesce(func.sum(Stock.quantite), 0))).scalar_one() or 0
    alertes_stock = db.execute(
        select(func.count()).select_from(Stock).where(Stock.quantite < Stock.seuil_alerte)
    ).scalar_one() or 0
    stock_epuise = db.execute(
        select(func.count()).select_from(Stock).where(Stock.quantite == 0)
    ).scalar_one() or 0

    last_modifs_rows = db.execute(
        select(
            StockModification.date_demande,
            Admin.nom,
            Admin.prenom,
            Stock.nom.label("stock_nom"),
            Stock.categorie.label("stock_categorie"),
            StockModification.status,
            StockModification.quantite_demandee,
        )
        .join(Admin, Admin.id == StockModification.id_user)
        .join(Stock, Stock.id == StockModification.id_stock)
        .order_by(StockModification.date_demande.desc())
        .limit(10)
    ).all()

    dernieres_modifs = [
        {
            "date": row.date_demande,
            "user_full_name": " ".join([p for p in [row.prenom, row.nom] if p]) or "—",
            "stock_nom": row.stock_nom,
            "categorie": row.stock_categorie,
            "status": row.status,
            "quantite_demandee": row.quantite_demandee,
        }
        for row in last_modifs_rows
    ]

    cat_rows = db.execute(
        select(
            Stock.categorie,
            func.count().label("count"),
            func.coalesce(func.sum(Stock.quantite), 0).label("total"),
        )
        .group_by(Stock.categorie)
        .order_by(func.count().desc())
    ).all()
    stats_par_categorie = [
        {"categorie": r.categorie, "count": int(r.count), "total": int(r.total)} for r in cat_rows
    ]

    sub_rows = db.execute(
        select(
            Stock.sous_categorie,
            func.count().label("count"),
            func.coalesce(func.sum(Stock.quantite), 0).label("total"),
        )
        .where(
            Stock.categorie == "Nourriture",
            Stock.sous_categorie.is_not(None),
            Stock.sous_categorie != "",
        )
        .group_by(Stock.sous_categorie)
        .order_by(func.count().desc())
    ).all()
    stats_nourriture_sous_categories = [
        {
            "sous_categorie": r.sous_categorie,
            "count": int(r.count),
            "total": int(r.total),
        }
        for r in sub_rows
    ]

    return {
        "total_articles": int(total_articles),
        "total_quantite": int(total_quantite),
        "alertes_stock": int(alertes_stock),
        "stock_epuise": int(stock_epuise),
        "dernieres_modifs": dernieres_modifs,
        "stats_par_categorie": stats_par_categorie,
        "stats_nourriture_sous_categories": stats_nourriture_sous_categories,
    }
