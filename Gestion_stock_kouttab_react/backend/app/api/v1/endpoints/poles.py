"""Referentiel des poles de rattachement comptable."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.crud import pole as pole_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.pole import PoleCreate, PoleOut, PoleUpdate


router = APIRouter(prefix="/poles", tags=["poles"])

# Constante isolee : le client a demande une gestion reservee au Super Admin,
# mais la comptabilite est la premiere concernee par ce referentiel. Ouvrir la
# gestion a « Compta » ne demanderait que de modifier cette ligne.
_POLE_ADMIN_ROLES = ("Super Admin",)


@router.get("", response_model=list[PoleOut])
def list_poles(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    return [PoleOut.model_validate(p) for p in pole_crud.list_poles(
        db, include_inactive=include_inactive
    )]


@router.post(
    "",
    response_model=PoleOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_POLE_ADMIN_ROLES))],
)
def create_pole(payload: PoleCreate, db: Session = Depends(get_db)) -> Any:
    return PoleOut.model_validate(
        pole_crud.create_pole(
            db,
            nom=payload.nom,
            ordre=payload.ordre,
            requiert_evenement=payload.requiert_evenement,
            type_evenement=payload.type_evenement,
        )
    )


@router.patch(
    "/{pole_id}",
    response_model=PoleOut,
    dependencies=[Depends(require_roles(*_POLE_ADMIN_ROLES))],
)
def update_pole(
    pole_id: int, payload: PoleUpdate, db: Session = Depends(get_db)
) -> Any:
    return PoleOut.model_validate(
        pole_crud.update_pole(
            db,
            pole_id,
            nom=payload.nom,
            is_active=payload.is_active,
            ordre=payload.ordre,
            requiert_evenement=payload.requiert_evenement,
            type_evenement=payload.type_evenement,
        )
    )


@router.delete(
    "/{pole_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_POLE_ADMIN_ROLES))],
)
def delete_pole(pole_id: int, db: Session = Depends(get_db)) -> Any:
    pole_crud.delete_pole(db, pole_id)
    return MessageOut(message="Pole supprime.")
