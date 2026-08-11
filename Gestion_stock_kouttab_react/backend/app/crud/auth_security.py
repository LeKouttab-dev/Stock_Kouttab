"""Lockout de connexion et cycle de vie des refresh tokens (persistes en base).

Ces deux mecanismes vivaient auparavant en memoire de process (ou pas du tout) :
- le lockout etait un ``dict`` perdu a chaque redemarrage Passenger et non
  partage entre workers ;
- les refresh tokens n'etaient jamais enregistres, donc ni revocables ni
  rotatifs, et ``/auth/logout`` ne faisait rien.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.security import hash_jti
from app.db.models import LoginAttempt, RefreshToken


logger = get_logger("auth_security")

LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
# Au-dela, un compteur d'echecs isole n'a plus de sens : on repart de zero.
ATTEMPT_TTL = timedelta(hours=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """MySQL et SQLite rendent des datetimes naifs — on les relit comme UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _normalise(username: str, ip_address: str | None) -> tuple[str, str]:
    return (username or "").strip().lower()[:50], (ip_address or "unknown")[:45]


# ---- Lockout ----------------------------------------------------------------


def _get_attempt(db: Session, username: str, ip_address: str) -> LoginAttempt | None:
    return db.execute(
        select(LoginAttempt).where(
            LoginAttempt.username == username,
            LoginAttempt.ip_address == ip_address,
        )
    ).scalar_one_or_none()


def is_locked(db: Session, username: str, ip_address: str | None) -> tuple[bool, int]:
    """Retourne ``(verrouille, secondes_restantes)``."""
    user_key, ip_key = _normalise(username, ip_address)
    attempt = _get_attempt(db, user_key, ip_key)
    if attempt is None:
        return False, 0
    locked_until = _as_utc(attempt.locked_until)
    if locked_until is None:
        return False, 0
    now = _now()
    if now < locked_until:
        return True, int((locked_until - now).total_seconds())
    # Verrou expire : on repart proprement.
    db.delete(attempt)
    db.commit()
    return False, 0


def record_failure(db: Session, username: str, ip_address: str | None) -> None:
    user_key, ip_key = _normalise(username, ip_address)
    attempt = _get_attempt(db, user_key, ip_key)
    now = _now()
    if attempt is None:
        attempt = LoginAttempt(username=user_key, ip_address=ip_key, failed_count=1)
        db.add(attempt)
        try:
            db.commit()
        except IntegrityError:
            # Course entre deux workers sur la meme cle : on relit et on incremente.
            db.rollback()
            attempt = _get_attempt(db, user_key, ip_key)
            if attempt is None:
                return
        else:
            return

    last = _as_utc(attempt.last_attempt_at)
    if last is not None and now - last > ATTEMPT_TTL:
        attempt.failed_count = 0
    attempt.failed_count += 1
    if attempt.failed_count >= LOCKOUT_THRESHOLD:
        attempt.locked_until = now + LOCKOUT_WINDOW
        logger.warning(
            "Compte '%s' verrouille %d min depuis %s (%d echecs).",
            user_key,
            int(LOCKOUT_WINDOW.total_seconds() // 60),
            ip_key,
            attempt.failed_count,
        )
    attempt.last_attempt_at = now
    db.commit()


def record_success(db: Session, username: str, ip_address: str | None) -> None:
    user_key, ip_key = _normalise(username, ip_address)
    attempt = _get_attempt(db, user_key, ip_key)
    if attempt is not None:
        db.delete(attempt)
        db.commit()


def purge_stale_attempts(db: Session) -> int:
    """Supprime les compteurs inactifs. Appele par le cron de maintenance."""
    cutoff = _now() - ATTEMPT_TTL
    result = db.execute(delete(LoginAttempt).where(LoginAttempt.last_attempt_at < cutoff))
    db.commit()
    return result.rowcount or 0


# ---- Refresh tokens ---------------------------------------------------------


def store_refresh_token(
    db: Session, *, user_id: int, jti: str, expires_at: datetime
) -> RefreshToken:
    token = RefreshToken(
        jti_hash=hash_jti(jti),
        id_user=user_id,
        expires_at=expires_at.replace(tzinfo=None) if expires_at.tzinfo else expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def consume_refresh_token(db: Session, jti: str, *, user_id: int) -> bool:
    """Marque un refresh token comme utilise. ``False`` s'il est inutilisable.

    Detection de rejeu : si le token a deja ete tourne, c'est qu'il circule en
    double — on revoque alors toute la famille du compte plutot que de laisser
    coexister la session legitime et celle du voleur.
    """
    row = db.execute(
        select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(jti))
    ).scalar_one_or_none()
    if row is None or row.id_user != user_id:
        return False
    if row.revoked_at is not None:
        return False
    if row.rotated_at is not None:
        logger.warning(
            "Refresh token rejoue pour l'utilisateur %d — revocation de toutes ses sessions.",
            user_id,
        )
        revoke_all_for_user(db, user_id)
        return False
    expires_at = _as_utc(row.expires_at)
    if expires_at is not None and _now() > expires_at:
        return False
    row.rotated_at = _now().replace(tzinfo=None)
    db.commit()
    return True


def revoke_refresh_token(db: Session, jti: str) -> bool:
    row = db.execute(
        select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(jti))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = _now().replace(tzinfo=None)
    db.commit()
    return True


def revoke_all_for_user(db: Session, user_id: int) -> int:
    rows = (
        db.execute(
            select(RefreshToken).where(
                RefreshToken.id_user == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    now = _now().replace(tzinfo=None)
    for row in rows:
        row.revoked_at = now
    db.commit()
    return len(rows)


def purge_expired_tokens(db: Session) -> int:
    """Supprime les tokens expires. Appele par le cron de maintenance."""
    cutoff = _now().replace(tzinfo=None)
    result = db.execute(delete(RefreshToken).where(RefreshToken.expires_at < cutoff))
    db.commit()
    return result.rowcount or 0
