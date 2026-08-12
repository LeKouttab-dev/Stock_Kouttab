"""Tickets de justificatif : demander une piece manquante a un benevole."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.crud import ticket as ticket_crud
from app.db.models import Admin, JustificatifTicket
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.ticket import TicketClose, TicketCreate, TicketOut, TicketUpdate
from app.services import email as email_service


router = APIRouter(prefix="/tickets", tags=["tickets"])

logger = get_logger("tickets")

_ACCOUNTANT_ROLES = ("Compta", "Super Admin")


def _to_out(ticket: JustificatifTicket) -> TicketOut:
    out = TicketOut.model_validate(ticket)
    out.user_full_name = ticket.user.full_name if ticket.user else None
    return out


@router.get("/me", response_model=list[TicketOut])
def list_my_tickets(
    db: Session = Depends(get_db), current_user: Admin = Depends(get_current_user)
) -> Any:
    """Ce que la comptabilite attend de moi.

    Ouvert a tout utilisateur : c'est la contrepartie des relances par courriel,
    pour que le benevole puisse verifier ce qu'on lui demande sans fouiller sa
    boite aux lettres.
    """
    return [_to_out(t) for t in ticket_crud.list_tickets(db, user_id=current_user.id)]


@router.get(
    "",
    response_model=list[TicketOut],
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def list_tickets(
    statut: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Any:
    return [_to_out(t) for t in ticket_crud.list_tickets(db, statut=statut)]


@router.post(
    "",
    response_model=TicketOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def create_ticket(
    payload: TicketCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    ticket = ticket_crud.create_ticket(
        db,
        id_user=payload.id_user,
        libelle=payload.libelle,
        description=payload.description,
        montant_attendu=payload.montant_attendu,
        date_achat=payload.date_achat,
        fournisseur=payload.fournisseur,
        cree_par=current_user.id,
    )
    # Premier rappel immediat : attendre trois jours pour signaler une demande
    # qui vient d'etre ouverte n'aurait servi personne.
    background.add_task(_relancer_en_arriere_plan, ticket.id)
    return _to_out(ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def update_ticket(
    ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)
) -> Any:
    return _to_out(
        ticket_crud.update_ticket(
            db,
            ticket_id,
            libelle=payload.libelle,
            description=payload.description,
            montant_attendu=payload.montant_attendu,
            date_achat=payload.date_achat,
            fournisseur=payload.fournisseur,
        )
    )


@router.post(
    "/{ticket_id}/close",
    response_model=TicketOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def close_ticket(
    ticket_id: int,
    payload: TicketClose,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Clot la demande, en la rattachant eventuellement a la piece recue."""
    return _to_out(
        ticket_crud.close_ticket(
            db,
            ticket_id,
            id_facture=payload.id_facture,
            closed_by=current_user.id,
            annule=payload.annule,
        )
    )


@router.post(
    "/{ticket_id}/remind",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def remind(
    ticket_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
    """Relance sur demande, sans attendre la prochaine echeance.

    Ne consomme pas le quota automatique : c'est un geste delibere de la
    comptabilite, pas une relance programmee.
    """
    ticket = ticket_crud.get_or_404(db, ticket_id)
    if ticket.statut != JustificatifTicket.STATUT_OUVERT:
        raise AppException(
            ErrorCode.CONFLICT, detail="Ce ticket est cloture : plus rien a relancer."
        )
    if not (ticket.user and ticket.user.email):
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Ce benevole n'a pas d'adresse de messagerie enregistree.",
        )
    background.add_task(_relancer_en_arriere_plan, ticket.id, compter=False)
    return MessageOut(message="Rappel envoye.")


async def _relancer_en_arriere_plan(ticket_id: int, *, compter: bool = True) -> None:
    """Envoie un rappel hors de la requete.

    Sa propre session : celle de la requete est fermee quand la tache s'execute.
    Aucune exception ne remonte — un rappel perdu se rattrape au tour suivant du
    worker, il ne doit pas faire echouer l'ouverture du ticket.
    """
    db = SessionLocal()
    try:
        ticket = ticket_crud.get_ticket(db, ticket_id)
        if ticket is None or not (ticket.user and ticket.user.email):
            return
        await email_service.send_justificatif_reminder(
            recipient=ticket.user.email,
            prenom=ticket.user.prenom,
            libelle=ticket.libelle,
            description=ticket.description,
            montant=(
                f"{ticket.montant_attendu:.2f} EUR"
                if ticket.montant_attendu is not None
                else None
            ),
            date_achat=(
                ticket.date_achat.strftime("%d/%m/%Y") if ticket.date_achat else None
            ),
            fournisseur=ticket.fournisseur,
            rappel_numero=ticket.rappels_envoyes + 1,
            rappels_max=ticket_crud.RAPPELS_MAX,
        )
        if compter:
            ticket_crud.marquer_relance(db, ticket)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rappel du ticket #%d non envoye : %s", ticket_id, exc)
    finally:
        db.close()
