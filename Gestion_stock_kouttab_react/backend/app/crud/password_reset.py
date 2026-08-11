"""Reinitialisation de mot de passe par lien a usage unique.

Le compte n'est jamais modifie a la demande : seul un jeton est emis. Tant que
le lien n'est pas ouvert, l'utilisateur garde son mot de passe — une demande
faite par erreur, ou par un tiers, ne verrouille personne dehors.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.core.security import hash_password, validate_password_strength
from app.db.models import Admin, PasswordReset


logger = get_logger("crud.password_reset")


# Une heure : assez pour relever ses courriels, trop court pour qu'un lien
# oublie dans une boite partagee reste exploitable longtemps.
DUREE_VALIDITE = timedelta(hours=1)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_reset_token(db: Session, user: Admin, *, ip: str | None = None) -> str:
    """Emet un jeton et invalide les precedents du meme compte.

    Invalider les anciens evite qu'une suite de demandes laisse plusieurs liens
    actifs en meme temps : seul le dernier courriel recu fonctionne, ce qui est
    aussi ce que l'utilisateur attend.
    """
    maintenant = datetime.utcnow()
    db.execute(
        PasswordReset.__table__.update()
        .where(
            PasswordReset.id_user == user.id,
            PasswordReset.used_at.is_(None),
        )
        .values(used_at=maintenant)
    )

    token = secrets.token_urlsafe(32)
    db.add(
        PasswordReset(
            id_user=user.id,
            token_hash=hash_reset_token(token),
            expires_at=maintenant + DUREE_VALIDITE,
            requested_ip=ip,
        )
    )
    db.commit()
    logger.info("Jeton de reinitialisation emis pour le compte %s.", user.id)
    return token


def _get_valid_reset(db: Session, token: str) -> PasswordReset:
    ligne = db.execute(
        select(PasswordReset).where(PasswordReset.token_hash == hash_reset_token(token))
    ).scalar_one_or_none()

    # Un jeton inconnu, deja consomme ou expire renvoient tous la meme erreur :
    # distinguer les cas renseignerait un attaquant sur ce qu'il a trouve.
    if ligne is None or ligne.used_at is not None or ligne.expires_at < datetime.utcnow():
        raise AppException(
            ErrorCode.INVITATION_INVALID,
            detail="Ce lien de reinitialisation est invalide ou a expire.",
        )
    return ligne


def token_is_valid(db: Session, token: str) -> bool:
    """Pre-verification, pour que l'ecran n'affiche pas un formulaire inutile."""
    try:
        _get_valid_reset(db, token)
        return True
    except AppException:
        return False


def reset_password(db: Session, token: str, nouveau_mot_de_passe: str) -> Admin:
    ligne = _get_valid_reset(db, token)

    ok, message = validate_password_strength(nouveau_mot_de_passe)
    if not ok:
        raise AppException(ErrorCode.PASSWORD_WEAK, detail=message)

    utilisateur = db.get(Admin, ligne.id_user)
    if utilisateur is None:
        raise AppException(ErrorCode.USER_NOT_FOUND)

    utilisateur.password_hash = hash_password(nouveau_mot_de_passe)
    ligne.used_at = datetime.utcnow()
    db.commit()
    db.refresh(utilisateur)
    logger.info("Mot de passe reinitialise pour le compte %s.", utilisateur.id)
    return utilisateur


def purge_expired(db: Session) -> int:
    """Supprime les jetons expires. Appele par le worker de la file d'envoi."""
    resultat = db.execute(
        PasswordReset.__table__.delete().where(PasswordReset.expires_at < datetime.utcnow())
    )
    db.commit()
    return resultat.rowcount or 0
