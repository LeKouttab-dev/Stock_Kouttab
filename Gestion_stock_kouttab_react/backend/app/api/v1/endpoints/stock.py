"""Stock endpoints (items, categories, sub-categories, modifications, stats, CSV import)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import stock as stock_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.stock import (
    CSVImportResult,
    CategoryIn,
    CategoryOut,
    CategoryRename,
    ModificationIn,
    ModificationOut,
    QuantityUpdate,
    StatsOut,
    StockItemIn,
    StockItemOut,
    StockItemUpdate,
    SubCategoryIn,
    SubCategoryOut,
    SubCategoryUpdate,
)
from app.crud import buvette as buvette_crud
from app.schemas.buvette import BuvetteProductOut
from app.services import email as email_service
from app.services import openfoodfacts as openfoodfacts_service
from app.services.csv_import import import_inventory


router = APIRouter(prefix="/stock", tags=["stock"])


_ADMIN_ROLES = ("AdminBenevoles", "Super Admin")


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


@router.get("/items", response_model=list[StockItemOut])
def list_items(
    categorie: str | None = Query(default=None),
    sous_categorie: str | None = Query(default=None),
    only_alerts: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    items = stock_crud.list_items(
        db,
        categorie=categorie,
        sous_categorie=sous_categorie,
        only_alerts=only_alerts,
    )
    return [StockItemOut.model_validate(i) for i in items]


@router.post(
    "/items",
    response_model=StockItemOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def create_item(payload: StockItemIn, db: Session = Depends(get_db)) -> Any:
    item = stock_crud.create_item(
        db,
        nom=payload.nom,
        categorie=payload.categorie,
        sous_categorie=payload.sous_categorie,
        quantite=payload.quantite,
        seuil_alerte=payload.seuil_alerte,
        emoji=payload.emoji,
        barcode=payload.barcode,
    )
    return StockItemOut.model_validate(item)


@router.patch("/items/{item_id}", response_model=StockItemOut)
def update_item(
    item_id: int,
    payload: StockItemUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Update an item.

    - AdminBenevoles / Super Admin can edit any field.
    - Other roles can only update the quantity (treated as direct admin modification),
      which is rejected here; they should use the modification request endpoint.
    """
    if current_user.role not in _ADMIN_ROLES:
        raise AppException(
            ErrorCode.ROLE_REQUIRED, detail="Reserve aux administrateurs."
        )

    payload_dict = payload.model_dump(exclude_unset=True)
    new_qty = payload_dict.pop("quantite", None)
    barcode_set = "barcode" in payload_dict
    if payload_dict:
        item = stock_crud.update_item(
            db,
            item_id,
            barcode_set=barcode_set,
            **payload_dict,
        )
    else:
        item = stock_crud.get_item(db, item_id)
        if item is None:
            raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)

    if new_qty is not None:
        item, alert_to_send = stock_crud.update_quantity_direct(
            db, item_id, new_qty, current_user.id
        )
        if alert_to_send:
            background.add_task(_send_stock_alert_safe, item.id, item.nom, item.quantite, item.seuil_alerte)

    return StockItemOut.model_validate(item)


@router.put("/items/{item_id}/quantity", response_model=StockItemOut)
def set_quantity(
    item_id: int,
    payload: QuantityUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    if current_user.role not in _ADMIN_ROLES:
        raise AppException(
            ErrorCode.ROLE_REQUIRED, detail="Reserve aux administrateurs."
        )
    item, alert_to_send = stock_crud.update_quantity_direct(
        db, item_id, payload.quantite, current_user.id
    )
    if alert_to_send:
        background.add_task(_send_stock_alert_safe, item.id, item.nom, item.quantite, item.seuil_alerte)
    return StockItemOut.model_validate(item)


@router.delete(
    "/items/{item_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> Any:
    stock_crud.delete_item(db, item_id)
    return MessageOut(message="Article supprime.")


# ---------------------------------------------------------------------------
# Barcode lookup
# ---------------------------------------------------------------------------


@router.get("/items/by-barcode/{barcode}", response_model=StockItemOut)
def get_item_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    """Return the stock item linked to ``barcode``. ``404`` if unknown."""
    item = stock_crud.get_item_by_barcode(db, barcode.strip())
    if item is None:
        raise AppException(ErrorCode.STOCK_ITEM_NOT_FOUND)
    return StockItemOut.model_validate(item)


@router.get("/lookup-barcode/{barcode}")
def lookup_barcode_endpoint(
    barcode: str,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> dict[str, Any]:
    """Unified barcode lookup used by the scanner UI.

    Search order:
    1. Local Stock items (``found_in = "stock"``).
    2. Local Buvette products (``found_in = "buvette"``).
    3. OpenFoodFacts public DB (always returned when available, regardless of
       a local hit, so the UI can offer to refresh metadata).
    """
    cleaned = barcode.strip()
    stock_item = stock_crud.get_item_by_barcode(db, cleaned)
    buvette_product = buvette_crud.get_product_by_barcode(db, cleaned)

    found_in: str | None = None
    if stock_item is not None:
        found_in = "stock"
    elif buvette_product is not None:
        found_in = "buvette"

    off = openfoodfacts_service.lookup_barcode(cleaned)

    return {
        "barcode": cleaned,
        "found_in": found_in,
        "stock_item": (
            StockItemOut.model_validate(stock_item).model_dump(mode="json")
            if stock_item is not None
            else None
        ),
        "buvette_product": (
            BuvetteProductOut.model_validate(buvette_product).model_dump(mode="json")
            if buvette_product is not None
            else None
        ),
        "openfoodfacts": off,
    }


@router.post(
    "/items/import-csv",
    response_model=CSVImportResult,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
async def import_csv(
    file: UploadFile = File(...),
    skiprows: int = Query(default=6, ge=0),
    db: Session = Depends(get_db),
) -> Any:
    content = await file.read()
    result = import_inventory(db, content=content, skiprows=skiprows)
    return CSVImportResult(**result)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return [CategoryOut.model_validate(c) for c in stock_crud.list_categories(db)]


@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def create_category(payload: CategoryIn, db: Session = Depends(get_db)) -> Any:
    cat = stock_crud.add_category(db, nom=payload.nom, is_default=payload.is_default)
    return CategoryOut.model_validate(cat)


@router.patch(
    "/categories/{name}",
    response_model=CategoryOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def rename_category(name: str, payload: CategoryRename, db: Session = Depends(get_db)) -> Any:
    cat = stock_crud.rename_category(db, old_name=name, new_name=payload.new_name)
    return CategoryOut.model_validate(cat)


@router.delete(
    "/categories/{name}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def delete_category(name: str, db: Session = Depends(get_db)) -> Any:
    stock_crud.delete_category(db, nom=name)
    return MessageOut(message="Categorie supprimee.")


# ---------------------------------------------------------------------------
# Sub-categories
# ---------------------------------------------------------------------------


@router.get("/subcategories", response_model=list[SubCategoryOut])
def list_subcategories(
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return [
        SubCategoryOut.model_validate(s)
        for s in stock_crud.list_subcategories(db, categorie=category)
    ]


@router.post(
    "/subcategories",
    response_model=SubCategoryOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def create_subcategory(payload: SubCategoryIn, db: Session = Depends(get_db)) -> Any:
    sub = stock_crud.add_subcategory(
        db,
        nom_categorie=payload.nom_categorie,
        nom_sous_categorie=payload.nom_sous_categorie,
    )
    return SubCategoryOut.model_validate(sub)


@router.patch(
    "/subcategories/{sub_id}",
    response_model=SubCategoryOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def update_subcategory(
    sub_id: int, payload: SubCategoryUpdate, db: Session = Depends(get_db)
) -> Any:
    sub = stock_crud.update_subcategory(
        db,
        sub_id,
        nom_categorie=payload.nom_categorie,
        nom_sous_categorie=payload.nom_sous_categorie,
    )
    return SubCategoryOut.model_validate(sub)


@router.delete(
    "/subcategories/{sub_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def delete_subcategory(sub_id: int, db: Session = Depends(get_db)) -> Any:
    stock_crud.delete_subcategory(db, sub_id)
    return MessageOut(message="Sous-categorie supprimee.")


# ---------------------------------------------------------------------------
# Statistics & alerts
# ---------------------------------------------------------------------------


@router.get("/statistics", response_model=StatsOut)
def get_statistics(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return StatsOut(**stock_crud.get_stock_statistics(db))


@router.get("/low-stock", response_model=list[StockItemOut])
def get_low_stock(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return [StockItemOut.model_validate(i) for i in stock_crud.get_low_stock_items(db)]


@router.post(
    "/low-stock/notify",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def notify_low_stock(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    items = stock_crud.get_low_stock_items(db)
    for item in items:
        background.add_task(
            _send_stock_alert_safe, item.id, item.nom, item.quantite, item.seuil_alerte
        )
    return MessageOut(message=f"Alertes envoyees pour {len(items)} article(s).")


# ---------------------------------------------------------------------------
# Modifications workflow
# ---------------------------------------------------------------------------


@router.get("/modifications", response_model=list[ModificationOut])
def list_modifications(
    status: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return [ModificationOut(**row) for row in stock_crud.list_modifications(db, status=status, days=days)]


@router.post("/modifications", response_model=ModificationOut, status_code=201)
def create_modification(
    payload: ModificationIn,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    if current_user.role in _ADMIN_ROLES:
        # An admin should use the direct quantity endpoint, but we still allow
        # them to file requests if they want to (e.g. for traceability).
        pass
    modif = stock_crud.create_modification_request(
        db,
        user_id=current_user.id,
        stock_id=payload.id_stock,
        requested_qty=payload.quantite_demandee,
        commentaires=payload.commentaires,
    )
    return _modif_to_out(db, modif.id)


@router.post(
    "/modifications/{modif_id}/approve",
    response_model=ModificationOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def approve_modification(
    modif_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    modif, item, alert_to_send = stock_crud.approve_modification(
        db, modif_id, approver_id=current_user.id
    )
    if alert_to_send:
        background.add_task(
            _send_stock_alert_safe, item.id, item.nom, item.quantite, item.seuil_alerte
        )
    return _modif_to_out(db, modif.id)


@router.post(
    "/modifications/{modif_id}/refuse",
    response_model=ModificationOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def refuse_modification(
    modif_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    modif = stock_crud.refuse_modification(db, modif_id, approver_id=current_user.id)
    return _modif_to_out(db, modif.id)


def _modif_to_out(db: Session, modif_id: int) -> ModificationOut:
    rows = stock_crud.list_modifications(db)
    for row in rows:
        if row["id"] == modif_id:
            return ModificationOut(**row)
    raise AppException(ErrorCode.MODIFICATION_NOT_FOUND)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _send_stock_alert_safe(
    item_id: int, item_name: str, quantity: int, threshold: int
) -> None:
    """Background-safe wrapper that opens its own DB session."""
    db = SessionLocal()
    try:
        await email_service.send_stock_alert(
            db,
            item_name=item_name,
            quantity=quantity,
            threshold=threshold,
        )
    finally:
        db.close()
