"""Referentiel des evenements, alimente par HelloAsso ou saisi a la main."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.logger import get_logger
from app.crud import event as event_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.event import EventCreate, EventOut, EventSyncResult, EventUpdate
from app.services.helloasso import get_helloasso_client


router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger("events")

_EVENT_ADMIN_ROLES = ("AdminBenevoles", "Super Admin")


@router.get("", response_model=list[EventOut])
def list_events(
    include_inactive: bool = Query(default=False),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    """Liste des evenements.

    Sert toujours le cache local : une indisponibilite de HelloAsso ne doit
    jamais empecher un benevole de deposer une piece.
    """
    return [
        EventOut.model_validate(e)
        for e in event_crud.list_events(
            db, include_inactive=include_inactive, search=search
        )
    ]


@router.post(
    "/sync",
    response_model=EventSyncResult,
    dependencies=[Depends(require_roles(*_EVENT_ADMIN_ROLES))],
)
def sync_events(db: Session = Depends(get_db)) -> Any:
    """Recupere les evenements publies sur HelloAsso et met a jour le referentiel."""
    client = get_helloasso_client()
    forms = client.list_organization_forms(
        settings.helloasso_org_slug, form_types=("Event",), states=("Public",)
    )
    result = event_crud.sync_events_from_helloasso(db, forms)
    return EventSyncResult(**result)


@router.post(
    "",
    response_model=EventOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_EVENT_ADMIN_ROLES))],
)
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> Any:
    return EventOut.model_validate(
        event_crud.create_manual_event(
            db,
            nom=payload.nom,
            date_evenement=payload.date_evenement,
            type_ev=payload.type_ev,
        )
    )


@router.patch(
    "/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(require_roles(*_EVENT_ADMIN_ROLES))],
)
def update_event(
    event_id: int, payload: EventUpdate, db: Session = Depends(get_db)
) -> Any:
    return EventOut.model_validate(
        event_crud.update_event(
            db,
            event_id,
            nom=payload.nom,
            date_evenement=payload.date_evenement,
            type_ev=payload.type_ev,
            is_active=payload.is_active,
        )
    )


@router.delete(
    "/{event_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_EVENT_ADMIN_ROLES))],
)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> Any:
    event_crud.delete_event(db, event_id)
    return MessageOut(message="Evenement supprime.")
