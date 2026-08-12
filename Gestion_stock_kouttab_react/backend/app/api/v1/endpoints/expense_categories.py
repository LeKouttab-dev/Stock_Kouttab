"""Referentiel des categories de depense (hors evenement)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.crud import expense_category as category_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.expense_category import (
    ExpenseCategoryCreate,
    ExpenseCategoryOut,
    ExpenseCategoryUpdate,
)


router = APIRouter(prefix="/expense-categories", tags=["expense-categories"])

# Meme choix que pour les poles : la gestion reste au Super Admin, et ouvrir a
# « Compta » ne demanderait que de modifier cette ligne.
_CATEGORY_ADMIN_ROLES = ("Super Admin",)


@router.get("", response_model=list[ExpenseCategoryOut])
def list_categories(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return [
        ExpenseCategoryOut.model_validate(c)
        for c in category_crud.list_categories(db, include_inactive=include_inactive)
    ]


@router.post(
    "",
    response_model=ExpenseCategoryOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_CATEGORY_ADMIN_ROLES))],
)
def create_category(
    payload: ExpenseCategoryCreate, db: Session = Depends(get_db)
) -> Any:
    return ExpenseCategoryOut.model_validate(
        category_crud.create_category(db, nom=payload.nom, ordre=payload.ordre)
    )


@router.patch(
    "/{category_id}",
    response_model=ExpenseCategoryOut,
    dependencies=[Depends(require_roles(*_CATEGORY_ADMIN_ROLES))],
)
def update_category(
    category_id: int, payload: ExpenseCategoryUpdate, db: Session = Depends(get_db)
) -> Any:
    return ExpenseCategoryOut.model_validate(
        category_crud.update_category(
            db,
            category_id,
            nom=payload.nom,
            is_active=payload.is_active,
            ordre=payload.ordre,
        )
    )


@router.delete(
    "/{category_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_CATEGORY_ADMIN_ROLES))],
)
def delete_category(category_id: int, db: Session = Depends(get_db)) -> Any:
    category_crud.delete_category(db, category_id)
    return MessageOut(message="Categorie supprimee.")
