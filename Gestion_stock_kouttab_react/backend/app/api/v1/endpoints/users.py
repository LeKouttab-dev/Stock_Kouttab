"""User management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.crud import user as user_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.user import (
    ProfileUpdate,
    UserDetailOut,
    UserOut,
    UserRoleUpdate,
    UserValidate,
)


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_roles("Super Admin"))])
def list_users(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    return [UserOut.model_validate(u) for u in user_crud.list_users(db, exclude_id=current_user.id)]


@router.get(
    "/pending",
    response_model=list[UserOut],
    dependencies=[Depends(require_roles("Super Admin"))],
)
def list_pending(db: Session = Depends(get_db)) -> Any:
    return [UserOut.model_validate(u) for u in user_crud.list_pending_users(db)]


@router.get("/me/profile", response_model=UserDetailOut)
def get_my_profile(current_user: Admin = Depends(get_current_user)) -> Any:
    return UserDetailOut.model_validate(current_user)


@router.patch("/me/profile", response_model=UserDetailOut)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    user = user_crud.update_profile(
        db,
        current_user.id,
        nom=payload.nom,
        prenom=payload.prenom,
        email=str(payload.email) if payload.email else None,
        telephone=payload.telephone,
        rib=payload.rib,
    )
    return UserDetailOut.model_validate(user)


@router.patch(
    "/{user_id}/validate",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def validate_user(user_id: int, payload: UserValidate, db: Session = Depends(get_db)) -> Any:
    if payload.validation_status == "rejected":
        # Reject = delete (legacy behaviour).
        user_crud.delete_user(db, user_id)
        return UserOut(
            id=user_id,
            username="",
            role="Benevole",
            validation_status="rejected",
        )
    user = user_crud.update_validation_status(db, user_id, payload.validation_status)
    return UserOut.model_validate(user)


@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def update_role(user_id: int, payload: UserRoleUpdate, db: Session = Depends(get_db)) -> Any:
    user = user_crud.update_role(db, user_id, payload.role)
    return UserOut.model_validate(user)


@router.delete(
    "/{user_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Any:
    user_crud.delete_user(db, user_id)
    return MessageOut(message="Utilisateur supprime.")
