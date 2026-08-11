"""Admin invitation endpoints."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.crud import invitation as invitation_crud
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.invitation import InvitationCreatedOut, InvitationIn, InvitationOut
from app.services import email as email_service


router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.get(
    "",
    response_model=list[InvitationOut],
    dependencies=[Depends(require_roles("Super Admin"))],
)
def list_invitations(db: Session = Depends(get_db)) -> Any:
    return [InvitationOut.model_validate(i) for i in invitation_crud.list_invitations(db)]


@router.post(
    "",
    response_model=InvitationCreatedOut,
    status_code=201,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def create_invitation(
    payload: InvitationIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    invitation, token = invitation_crud.create_invitation(db, str(payload.email))
    invitation_url = (
        f"{settings.frontend_url.rstrip('/')}/admin-setup"
        f"?token={quote_plus(token)}&email={quote_plus(str(payload.email))}"
    )
    background.add_task(
        email_service.send_admin_invitation,
        email=str(payload.email),
        invitation_url=invitation_url,
        expires_at=invitation.expires_at.isoformat(),
    )
    return InvitationCreatedOut(
        id=invitation.id,
        email=invitation.email,
        expires_at=invitation.expires_at,
        used=invitation.used,
        attempts=invitation.attempts,
        created_at=invitation.created_at,
        token=token,
        invitation_url=invitation_url,
    )


@router.delete(
    "/{invitation_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def revoke_invitation(invitation_id: int, db: Session = Depends(get_db)) -> Any:
    invitation_crud.revoke(db, invitation_id)
    return MessageOut(message="Invitation revoquee.")


@router.post(
    "/cleanup",
    response_model=MessageOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def cleanup(db: Session = Depends(get_db)) -> Any:
    removed = invitation_crud.cleanup_expired(db)
    return MessageOut(message=f"{removed} invitation(s) nettoyee(s).")
