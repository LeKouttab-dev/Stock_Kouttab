"""FastAPI dependency providers."""

from __future__ import annotations

import secrets
from typing import Iterable

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.security import decode_token
from app.core.tablette import ATTRIBUT_OPERATEUR, est_compte_tablette
from app.crud.user import get_user
from app.db.models import Admin
from app.db.session import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AppException(ErrorCode.TOKEN_INVALID, detail="Token de mauvais type.")
    sub = payload.get("sub")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise AppException(ErrorCode.TOKEN_INVALID) from exc
    user = get_user(db, user_id)
    if user is None:
        raise AppException(ErrorCode.USER_NOT_FOUND, status_code=401)
    if user.validation_status == "rejected":
        raise AppException(ErrorCode.ACCOUNT_REJECTED)
    if user.validation_status != "active":
        raise AppException(ErrorCode.ACCOUNT_PENDING)
    # Session tablette : le nom de l'operateur (revendication `op`) signe les
    # actions via `core.tablette.nom_auteur`. Pose sur l'instance, jamais
    # persiste ; ignore pour tout autre compte. Toujours reecrit, pour ne rien
    # heriter d'une requete precedente si l'instance etait reutilisee.
    op = payload.get("op") if est_compte_tablette(user) else None
    setattr(user, ATTRIBUT_OPERATEUR, op if isinstance(op, str) and op else None)
    return user


def verifier_cle_caisse(
    x_caisse_key: str | None = Header(default=None, alias="X-Caisse-Key"),
) -> None:
    """Garde des routes de la tablette de caisse (en-tete `X-Caisse-Key`).

    Cle absente du `.env` : la caisse n'existe pas (404), comme le passage
    signe. Sans ce choix, une cle vide comparee a un en-tete vide ouvrirait la
    porte. Comparaison en temps constant, sur des octets : `compare_digest`
    leve sur une chaine non ASCII, qu'un appelant peut envoyer.
    """
    attendue = settings.caisse_api_key.strip()
    if not attendue:
        raise AppException(ErrorCode.NOT_FOUND)
    if not secrets.compare_digest((x_caisse_key or "").encode(), attendue.encode()):
        raise AppException(ErrorCode.TOKEN_INVALID)


# Tous les rôles SAUF BenevoleFrais, qui est confiné aux notes de frais.
# À poser sur tout router hors de ce périmètre : le menu ne protège rien,
# c'est cette liste qui fait le confinement côté serveur.
# AdminStock n'y figure pas non plus : il est confiné à la buvette
# (cf. `endpoints/buvette.py`, `_VIEW_ROLES` / `_GESTION_ROLES`).
ROLES_COMPLETS = ("Super Admin", "AdminBenevoles", "Compta", "Benevole")


def require_roles(*roles: str):
    """Factory of a FastAPI dependency that ensures the user has one of the roles."""
    role_set = set(roles)

    def _checker(current_user: Admin = Depends(get_current_user)) -> Admin:
        if current_user.role not in role_set:
            raise AppException(
                ErrorCode.ROLE_REQUIRED,
                extras={"required_roles": sorted(role_set), "current_role": current_user.role},
            )
        return current_user

    return _checker


def is_in_roles(user: Admin, roles: Iterable[str]) -> bool:
    return user.role in set(roles)
