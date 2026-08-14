"""Tickets de justificatif : demander une piece, relancer, clore.

Le cycle est volontairement court : ouvert -> clos (ou annule). Ce qui compte
n'est pas le statut mais la relance — c'est elle qui fait revenir la piece.

**Cadence arretee avec le client : tous les 3 jours, 5 fois au maximum.** Passe
ce compte, le ticket reste ouvert mais cesse d'ecrire : une demande oubliee ne
doit pas harceler quelqu'un indefiniment, et un rappel qu'on recoit dix fois
n'est plus un rappel.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Invoice, JustificatifTicket


logger = get_logger("ticket")


# Cadence des relances, arretee avec le client.
DELAI_ENTRE_RAPPELS = timedelta(days=3)
RAPPELS_MAX = 5


def _maintenant() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def get_ticket(db: Session, ticket_id: int) -> JustificatifTicket | None:
    return db.execute(
        select(JustificatifTicket)
        .options(selectinload(JustificatifTicket.user))
        .where(JustificatifTicket.id == ticket_id)
    ).scalar_one_or_none()


def get_or_404(db: Session, ticket_id: int) -> JustificatifTicket:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise AppException(ErrorCode.NOT_FOUND, detail="Ticket introuvable.")
    return ticket


def list_tickets(
    db: Session, *, user_id: int | None = None, statut: str | None = None
) -> list[JustificatifTicket]:
    stmt = (
        select(JustificatifTicket)
        .options(selectinload(JustificatifTicket.user))
        # Les tickets ouverts d'abord : ce sont eux qui demandent une action.
        .order_by(
            (JustificatifTicket.statut != JustificatifTicket.STATUT_OUVERT),
            JustificatifTicket.created_at.desc(),
        )
    )
    if user_id is not None:
        stmt = stmt.where(JustificatifTicket.id_user == user_id)
    if statut is not None:
        stmt = stmt.where(JustificatifTicket.statut == statut)
    return list(db.execute(stmt).scalars().all())


def count_open(db: Session, *, user_id: int | None = None) -> int:
    stmt = select(func.count()).select_from(JustificatifTicket).where(
        JustificatifTicket.statut == JustificatifTicket.STATUT_OUVERT
    )
    if user_id is not None:
        stmt = stmt.where(JustificatifTicket.id_user == user_id)
    return int(db.execute(stmt).scalar_one())


# ---------------------------------------------------------------------------
# Ecriture
# ---------------------------------------------------------------------------


def create_ticket(
    db: Session,
    *,
    id_user: int,
    libelle: str,
    description: str | None = None,
    montant_attendu: Decimal | None = None,
    date_achat: date_type | None = None,
    fournisseur: str | None = None,
    cree_par: int | None = None,
) -> JustificatifTicket:
    """Ouvre une demande de justificatif.

    Seul le libelle est exige : le reste vient si on l'a. Un ticket qu'on ne
    peut pas ouvrir faute de connaitre le montant exact ne serait jamais ouvert.
    """
    nettoye = (libelle or "").strip()
    if not nettoye:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Indiquez ce qui est demande au benevole.",
        )

    ticket = JustificatifTicket(
        id_user=id_user,
        libelle=nettoye,
        description=(description or None),
        montant_attendu=montant_attendu,
        date_achat=date_achat,
        fournisseur=(fournisseur or None),
        statut=JustificatifTicket.STATUT_OUVERT,
        cree_par=cree_par,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    logger.info("Ticket #%d ouvert pour l'utilisateur %d.", ticket.id, id_user)
    return ticket


def update_ticket(
    db: Session,
    ticket_id: int,
    *,
    libelle: str | None = None,
    description: str | None = None,
    montant_attendu: Decimal | None = None,
    date_achat: date_type | None = None,
    fournisseur: str | None = None,
) -> JustificatifTicket:
    ticket = get_or_404(db, ticket_id)
    if ticket.statut != JustificatifTicket.STATUT_OUVERT:
        raise AppException(
            ErrorCode.CONFLICT,
            detail="Ce ticket est cloture : il n'y a plus rien a y demander.",
        )
    if libelle is not None:
        nettoye = libelle.strip()
        if not nettoye:
            raise AppException(
                ErrorCode.VALIDATION_ERROR, detail="Le libelle ne peut pas etre vide."
            )
        ticket.libelle = nettoye
    if description is not None:
        ticket.description = description or None
    if montant_attendu is not None:
        ticket.montant_attendu = montant_attendu
    if date_achat is not None:
        ticket.date_achat = date_achat
    if fournisseur is not None:
        ticket.fournisseur = fournisseur or None
    db.commit()
    db.refresh(ticket)
    return ticket


def close_ticket(
    db: Session,
    ticket_id: int,
    *,
    id_facture: int | None = None,
    closed_by: int | None = None,
    annule: bool = False,
) -> JustificatifTicket:
    """Clot un ticket : il est **supprime**, pas archive.

    Le rattachement a la piece recue reste manuel : deviner qu'une facture
    deposee correspond a un ticket fermerait la demande a tort des que le
    benevole depose autre chose, et les relances cesseraient alors que la piece
    attendue manque toujours.

    **Pourquoi supprimer plutot que ranger**, contrairement aux notes et aux
    factures : un ticket n'est pas une piece comptable, c'est une relance. Une
    fois la facture recue — ou la demande abandonnee —, il ne documente plus
    rien : la piece, elle, est au dossier. Les tickets clos s'accumulaient dans
    l'ecran de la comptabilite sans que personne ne les relise jamais.

    Le cout d'une fermeture par erreur est faible : rouvrir une demande, c'est
    en creer une nouvelle. Sans commune mesure avec l'effacement d'un
    justificatif.

    L'objet est renvoye **detache** de la session, pour que l'appelant puisse
    encore le serialiser dans sa reponse.
    """
    ticket = get_or_404(db, ticket_id)
    if ticket.statut != JustificatifTicket.STATUT_OUVERT:
        raise AppException(ErrorCode.CONFLICT, detail="Ce ticket est deja cloture.")

    if id_facture is not None:
        facture = db.get(Invoice, id_facture)
        if facture is None:
            raise AppException(ErrorCode.INVOICE_NOT_FOUND)
        if facture.id_user != ticket.id_user:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                detail="Cette facture a ete deposee par un autre benevole.",
            )
        ticket.id_facture = facture.id

    ticket.statut = (
        JustificatifTicket.STATUT_ANNULE if annule else JustificatifTicket.STATUT_CLOS
    )
    ticket.closed_at = _maintenant()
    ticket.closed_by = closed_by

    # Instantane pris AVANT la suppression : l'endpoint doit encore pouvoir
    # repondre au client ce qu'il vient de fermer.
    db.flush()
    db.expunge(ticket)

    db.delete(db.get(JustificatifTicket, ticket_id))
    db.commit()
    logger.info(
        "Ticket #%d %s puis supprime (libelle=%r).",
        ticket_id,
        ticket.statut,
        ticket.libelle,
    )
    return ticket


# ---------------------------------------------------------------------------
# Relances
# ---------------------------------------------------------------------------


def doit_relancer(ticket: JustificatifTicket, *, maintenant: datetime | None = None) -> bool:
    """Ce ticket merite-t-il un rappel maintenant ?

    Trois conditions : il est ouvert, le quota n'est pas epuise, et le dernier
    rappel remonte a plus de trois jours.

    **Un ticket jamais relance l'est immediatement.** L'ouverture envoie deja un
    premier rappel, mais cet envoi peut echouer (SMTP indisponible) : sans ce
    rattrapage, le worker attendrait trois jours avant de reessayer, et une
    demande ouverte un vendredi soir resterait muette tout le week-end. Le
    double envoi n'est pas a craindre : le premier rappel enregistre son passage,
    ce qui suffit a decaler le suivant.
    """
    if ticket.statut != JustificatifTicket.STATUT_OUVERT:
        return False
    if ticket.rappels_envoyes >= RAPPELS_MAX:
        return False
    if ticket.dernier_rappel_at is None:
        return True
    return (maintenant or _maintenant()) - ticket.dernier_rappel_at >= DELAI_ENTRE_RAPPELS


def tickets_a_relancer(
    db: Session, *, maintenant: datetime | None = None
) -> list[JustificatifTicket]:
    """Tickets dus pour une relance, destinataire charge."""
    ouverts = list(
        db.execute(
            select(JustificatifTicket)
            .options(selectinload(JustificatifTicket.user))
            .where(JustificatifTicket.statut == JustificatifTicket.STATUT_OUVERT)
            .where(JustificatifTicket.rappels_envoyes < RAPPELS_MAX)
        )
        .scalars()
        .all()
    )
    return [t for t in ouverts if doit_relancer(t, maintenant=maintenant)]


def marquer_relance(
    db: Session, ticket: JustificatifTicket, *, maintenant: datetime | None = None
) -> None:
    """Enregistre qu'un rappel vient de partir."""
    ticket.rappels_envoyes += 1
    ticket.dernier_rappel_at = maintenant or _maintenant()
    db.commit()


__all__ = [
    "DELAI_ENTRE_RAPPELS",
    "RAPPELS_MAX",
    "close_ticket",
    "count_open",
    "create_ticket",
    "doit_relancer",
    "get_or_404",
    "get_ticket",
    "list_tickets",
    "marquer_relance",
    "tickets_a_relancer",
    "update_ticket",
]
