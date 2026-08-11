"""Admin invitation CRUD + token lifecycle."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.security import hash_invitation_token, validate_email_str
from app.db.models import AdminInvitation


TOKEN_TTL_HOURS = 24
MAX_VALIDATION_ATTEMPTS = 3


def list_invitations(db: Session) -> list[AdminInvitation]:
    return list(db.execute(select(AdminInvitation).order_by(AdminInvitation.created_at.desc())).scalars().all())


def get_invitation(db: Session, invitation_id: int) -> AdminInvitation | None:
    return db.get(AdminInvitation, invitation_id)


def get_by_email(db: Session, email: str) -> AdminInvitation | None:
    return db.execute(
        select(AdminInvitation).where(AdminInvitation.email == email)
    ).scalar_one_or_none()


def create_invitation(db: Session, email: str) -> tuple[AdminInvitation, str]:
    """Generate a new admin invitation. Returns (db row, plaintext token)."""
    if not validate_email_str(email):
        raise AppException(ErrorCode.EMAIL_INVALID)

    token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

    existing = get_by_email(db, email)
    if existing:
        existing.token_hash = token_hash
        existing.expires_at = expires_at
        existing.used = False
        existing.attempts = 0
    else:
        existing = AdminInvitation(
            email=email,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False,
            attempts=0,
        )
        db.add(existing)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail="Conflit lors de la creation de l'invitation."
        ) from exc
    db.refresh(existing)
    return existing, token


def validate_token(db: Session, token: str, email: str) -> tuple[bool, str, AdminInvitation | None]:
    if not token or not email:
        return False, "Token ou email manquant.", None
    token_hash = hash_invitation_token(token)
    inv = db.execute(
        select(AdminInvitation).where(
            AdminInvitation.email == email,
            AdminInvitation.token_hash == token_hash,
        )
    ).scalar_one_or_none()
    if not inv:
        return False, "Lien d'invitation invalide.", None
    if inv.used:
        return False, "Lien d'invitation deja utilise.", inv
    expires_at = inv.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        return False, "Lien d'invitation expire.", inv
    if inv.attempts >= MAX_VALIDATION_ATTEMPTS:
        return False, "Trop de tentatives pour ce lien.", inv
    return True, "Invitation valide.", inv


def increment_attempts(db: Session, invitation: AdminInvitation) -> None:
    invitation.attempts += 1
    db.commit()


def mark_used(db: Session, invitation: AdminInvitation) -> None:
    invitation.used = True
    db.commit()


def revoke(db: Session, invitation_id: int) -> None:
    inv = get_invitation(db, invitation_id)
    if not inv:
        raise AppException(ErrorCode.INVITATION_NOT_FOUND)
    db.delete(inv)
    db.commit()


def cleanup_expired(db: Session) -> int:
    """Delete used or expired invitations. Returns the number removed."""
    rows = db.execute(
        select(AdminInvitation).where(
            (AdminInvitation.used.is_(True))
            | (AdminInvitation.expires_at < datetime.now(timezone.utc))
        )
    ).scalars().all()
    count = 0
    for row in rows:
        db.delete(row)
        count += 1
    if count:
        db.commit()
    return count
