"""File d'attente persistante des envois vers le service comptable.

Motif « transactional outbox ». L'intention d'envoyer est ecrite en base au
moment du depot ; l'envoi SMTP lui-meme est tente immediatement, puis repris par
un cron en cas d'echec.

Ce que cela resout concretement : avant, l'envoi partait dans un
``BackgroundTask`` dont l'exception etait avalee. Un SMTP indisponible, un
redemarrage Passenger au mauvais moment ou un mot de passe expire produisaient
le meme resultat — l'utilisateur voyait « Facture envoyee », le comptable ne
recevait rien, et personne ne l'apprenait avant la cloture comptable.

Aucun Celery ni Redis : l'hebergement mutualise O2Switch ne les propose pas.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.db.models import OutboundEmail
from app.db.session import SessionLocal
from app.services import email as email_service


logger = get_logger("outbox")


# Backoff : 5, 10, 20, 40, 80 minutes, puis abandon.
BASE_RETRY_DELAY = timedelta(minutes=5)
MAX_RETRY_DELAY = timedelta(hours=6)
# Au-dela, un envoi « sending » vient d'un process tue : on le recupere.
STALE_LOCK_AFTER = timedelta(minutes=15)

STATUS_PENDING = "pending"
STATUS_SENDING = "sending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_ABANDONED = "abandoned"

RESUMABLE = (STATUS_PENDING, STATUS_FAILED)


def _now() -> datetime:
    """Datetime naif UTC, aligne sur les colonnes DateTime du schema."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---- Ecriture ---------------------------------------------------------------


def enqueue(
    db: Session,
    *,
    kind: str,
    entity_type: str,
    entity_id: int,
    recipients: list[str],
    subject: str,
    body: str,
    attachments: list[Path] | None = None,
    triggered_by: int | None = None,
) -> OutboundEmail:
    """Enregistre un envoi a effectuer.

    Sans destinataire configure (``COMPTA_EMAIL`` vide), la ligne est tout de
    meme creee en ``pending`` : le cron l'enverra des que la variable sera
    renseignee, et rien de ce qui a ete depose entre-temps n'est perdu.
    """
    row = OutboundEmail(
        kind=kind,
        entity_type=entity_type,
        entity_id=entity_id,
        recipients=json.dumps(recipients, ensure_ascii=False),
        subject=subject[:255],
        body=body,
        attachments=json.dumps([str(p) for p in (attachments or [])], ensure_ascii=False),
        status=STATUS_PENDING,
        triggered_by=triggered_by,
    )
    if not recipients:
        row.last_error = (
            "COMPTA_EMAIL non configure — envoi conserve en attente, "
            "il partira des que l'adresse sera renseignee."
        )
        logger.warning(
            "Envoi comptable %s#%d mis en attente : aucun destinataire configure.",
            entity_type,
            entity_id,
        )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---- Verrou et transitions --------------------------------------------------


def _acquire(db: Session, email_id: int) -> bool:
    """Verrou optimiste. ``False`` si un autre process a deja pris la ligne.

    Deux executions du cron peuvent se chevaucher si l'une traine : sans ce
    verrou, le comptable recevrait la meme piece en double.
    """
    result = db.execute(
        update(OutboundEmail)
        .where(
            OutboundEmail.id == email_id,
            OutboundEmail.status.in_(RESUMABLE),
        )
        .values(status=STATUS_SENDING, locked_at=_now())
    )
    db.commit()
    return (result.rowcount or 0) == 1


def mark_sent(db: Session, row: OutboundEmail) -> None:
    row.status = STATUS_SENT
    row.sent_at = _now()
    row.locked_at = None
    row.next_retry_at = None
    row.last_error = None
    db.commit()


def mark_failed(db: Session, row: OutboundEmail, error: str) -> None:
    row.attempts += 1
    row.last_error = error[:2000]
    row.locked_at = None
    if row.attempts >= row.max_attempts:
        row.status = STATUS_ABANDONED
        row.next_retry_at = None
        logger.error(
            "Envoi comptable %s#%d abandonne apres %d tentatives : %s",
            row.entity_type,
            row.entity_id,
            row.attempts,
            error[:200],
        )
    else:
        row.status = STATUS_FAILED
        delay = min(BASE_RETRY_DELAY * (2 ** (row.attempts - 1)), MAX_RETRY_DELAY)
        row.next_retry_at = _now() + delay
        logger.warning(
            "Envoi comptable %s#%d en echec (tentative %d/%d), nouvelle tentative dans %s.",
            row.entity_type,
            row.entity_id,
            row.attempts,
            row.max_attempts,
            delay,
        )
    db.commit()


def reset_stale_locks(db: Session) -> int:
    """Repasse en attente les envois bloques en ``sending`` (process tue)."""
    cutoff = _now() - STALE_LOCK_AFTER
    result = db.execute(
        update(OutboundEmail)
        .where(
            OutboundEmail.status == STATUS_SENDING,
            OutboundEmail.locked_at.isnot(None),
            OutboundEmail.locked_at < cutoff,
        )
        .values(status=STATUS_PENDING, locked_at=None)
    )
    db.commit()
    count = result.rowcount or 0
    if count:
        logger.info("%d envoi(s) bloque(s) remis en file.", count)
    return count


def compter(db: Session, statut: str) -> int:
    """Nombre d'envois dans un statut donne, sans rapatrier les corps."""
    return int(
        db.execute(
            select(func.count()).select_from(OutboundEmail).where(OutboundEmail.status == statut)
        ).scalar_one()
    )


# ---- Envoi ------------------------------------------------------------------


async def _deliver(db: Session, row: OutboundEmail) -> bool:
    recipients = json.loads(row.recipients or "[]")

    if not recipients:
        # La liste a ete figee a la mise en file, alors que COMPTA_EMAIL n'etait
        # pas encore renseigne. On la recalcule ici, sinon la ligne resterait en
        # attente pour toujours — la promesse faite au moment de la mise en file
        # (« il partira des que l'adresse sera renseignee ») ne serait jamais
        # tenue, meme apres correction de la configuration.
        recipients = list(settings.compta_emails)
        if recipients:
            row.recipients = json.dumps(recipients, ensure_ascii=False)
            row.last_error = None
            logger.info(
                "Envoi #%s : destinataires recharges depuis COMPTA_EMAIL (%s).",
                row.id,
                ", ".join(recipients),
            )

    if not recipients:
        # Toujours rien : l'adresse n'est pas configuree. Ce n'est pas un echec,
        # et on ne consomme pas de tentative — sinon la ligne serait abandonnee
        # avant meme que le client ait renseigne COMPTA_EMAIL.
        row.status = STATUS_PENDING
        row.locked_at = None
        db.commit()
        return False

    attachments = [Path(p) for p in json.loads(row.attachments or "[]")]
    missing = [p for p in attachments if not p.exists()]
    if missing:
        mark_failed(db, row, f"Piece(s) jointe(s) introuvable(s) : {missing}")
        return False

    try:
        await email_service._send_raw(
            row.subject, row.body or "", recipients, attachments=attachments
        )
    except Exception as exc:  # noqa: BLE001
        mark_failed(db, row, str(exc))
        return False

    mark_sent(db, row)
    return True


async def try_send_now(email_id: int) -> bool:
    """Tente l'envoi immediatement, dans sa propre session.

    Ouvre une ``SessionLocal`` dediee : appelee depuis un ``BackgroundTask``,
    la session de la requete est deja fermee.
    """
    db = SessionLocal()
    try:
        if not _acquire(db, email_id):
            return False
        row = db.get(OutboundEmail, email_id)
        if row is None:
            return False
        return await _deliver(db, row)
    finally:
        db.close()


async def process_pending(*, limit: int = 20) -> dict[str, int]:
    """Traite la file. Appelee par le cron cPanel."""
    db = SessionLocal()
    stats = {"sent": 0, "failed": 0, "skipped": 0}
    try:
        reset_stale_locks(db)
        now = _now()
        rows = (
            db.execute(
                select(OutboundEmail.id)
                .where(
                    OutboundEmail.status.in_(RESUMABLE),
                    (OutboundEmail.next_retry_at.is_(None))
                    | (OutboundEmail.next_retry_at <= now),
                )
                .order_by(OutboundEmail.id)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        for email_id in rows:
            if not _acquire(db, email_id):
                stats["skipped"] += 1
                continue
            row = db.get(OutboundEmail, email_id)
            if row is None:
                stats["skipped"] += 1
                continue
            if await _deliver(db, row):
                stats["sent"] += 1
            else:
                stats["failed"] += 1
    finally:
        db.close()
    return stats


# ---- Consultation -----------------------------------------------------------


def list_emails(
    db: Session, *, status: str | None = None, limit: int = 100
) -> list[OutboundEmail]:
    stmt = select(OutboundEmail).order_by(OutboundEmail.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(OutboundEmail.status == status)
    return list(db.execute(stmt).scalars().all())


def latest_for_entity(
    db: Session, entity_type: str, entity_id: int
) -> OutboundEmail | None:
    return db.execute(
        select(OutboundEmail)
        .where(
            OutboundEmail.entity_type == entity_type,
            OutboundEmail.entity_id == entity_id,
        )
        .order_by(OutboundEmail.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def reset_for_retry(db: Session, row: OutboundEmail, *, triggered_by: int | None) -> None:
    """Relance manuelle depuis l'interface comptable."""
    row.status = STATUS_PENDING
    row.attempts = 0
    row.next_retry_at = None
    row.locked_at = None
    row.last_error = None
    row.triggered_by = triggered_by
    db.commit()
