"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Iterable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.security import decode_token
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
    return user


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
