"""User (Admin) CRUD operations."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.security import (
    hash_password,
    validate_email_str,
    validate_password_strength,
    validate_username,
)
from app.db.models import Admin


# ---- Read ------------------------------------------------------------------

def get_user(db: Session, user_id: int) -> Admin | None:
    return db.get(Admin, user_id)


def get_user_by_username(db: Session, username: str) -> Admin | None:
    return db.execute(select(Admin).where(Admin.username == username)).scalar_one_or_none()


def get_user_by_login(db: Session, identifiant: str) -> Admin | None:
    """Retrouve un compte par son identifiant **ou** son adresse e-mail.

    Les benevoles retiennent leur adresse, rarement l'identifiant choisi a
    l'inscription : imposer le second etait une cause d'echec de connexion
    evitable.

    L'identifiant est essaye en premier. Une adresse ne peut pas etre confondue
    avec un identifiant — `validate_username` interdit le caractere `@` — donc
    l'ordre ne cree pas d'ambiguite.

    La comparaison d'adresse est insensible a la casse : les clients de
    messagerie capitalisent volontiers la premiere lettre.
    """
    identifiant = (identifiant or "").strip()
    if not identifiant:
        return None

    trouve = get_user_by_username(db, identifiant)
    if trouve is not None:
        return trouve

    if "@" not in identifiant:
        return None
    return db.execute(
        select(Admin).where(func.lower(Admin.email) == identifiant.lower())
    ).scalars().first()


def list_users(db: Session, exclude_id: int | None = None) -> list[Admin]:
    stmt = select(Admin).order_by(Admin.username.asc())
    if exclude_id is not None:
        stmt = stmt.where(Admin.id != exclude_id)
    return list(db.execute(stmt).scalars().all())


def list_pending_users(db: Session) -> list[Admin]:
    stmt = select(Admin).where(Admin.validation_status == "pending").order_by(Admin.created_at.asc())
    return list(db.execute(stmt).scalars().all())


def get_emails_by_roles(db: Session, roles: list[str]) -> list[str]:
    stmt = select(Admin.email).where(Admin.role.in_(roles), Admin.email.is_not(None))
    return [row for row in db.execute(stmt).scalars().all() if row]


# ---- Create / update / delete ---------------------------------------------

def _validate_user_input(
    *,
    username: str,
    password: str | None,
    email: str | None,
) -> None:
    if not validate_username(username):
        raise AppException(ErrorCode.USERNAME_INVALID)
    if email and not validate_email_str(email):
        raise AppException(ErrorCode.EMAIL_INVALID)
    if password is not None:
        ok, msg = validate_password_strength(password)
        if not ok:
            raise AppException(ErrorCode.PASSWORD_WEAK, detail=msg)


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: str = "Benevole",
    nom: str | None = None,
    prenom: str | None = None,
    email: str | None = None,
    telephone: str | None = None,
    validation_status: str = "active",
) -> Admin:
    _validate_user_input(username=username, password=password, email=email)
    user = Admin(
        username=username,
        password_hash=hash_password(password),
        role=role,
        validation_status=validation_status,
        nom=nom,
        prenom=prenom,
        email=email,
        telephone=telephone,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.USERNAME_TAKEN) from exc
    db.refresh(user)
    return user


def create_pending_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: str,
    nom: str | None = None,
    prenom: str | None = None,
    email: str | None = None,
    telephone: str | None = None,
) -> Admin:
    return create_user(
        db,
        username=username,
        password=password,
        role=role,
        nom=nom,
        prenom=prenom,
        email=email,
        telephone=telephone,
        validation_status="pending",
    )


def update_role(db: Session, user_id: int, new_role: str) -> Admin:
    user = get_user(db, user_id)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)
    user.role = new_role
    db.commit()
    db.refresh(user)
    return user


def update_validation_status(db: Session, user_id: int, new_status: str) -> Admin:
    user = get_user(db, user_id)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)
    user.validation_status = new_status
    db.commit()
    db.refresh(user)
    return user


def update_profile(
    db: Session,
    user_id: int,
    *,
    nom: str | None = None,
    prenom: str | None = None,
    email: str | None = None,
    telephone: str | None = None,
    rib: str | None = None,
) -> Admin:
    user = get_user(db, user_id)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)
    if email is not None:
        if email and not validate_email_str(email):
            raise AppException(ErrorCode.EMAIL_INVALID)
        user.email = email
    if nom is not None:
        user.nom = nom
    if prenom is not None:
        user.prenom = prenom
    if telephone is not None:
        user.telephone = telephone
    if rib is not None:
        # Le chiffrement est porte par le type de colonne (`ChampChiffre`) :
        # rien a faire ici, et rien a oublier ailleurs.
        user.rib = rib
    db.commit()
    db.refresh(user)
    return user


def update_password(db: Session, user_id: int, new_password: str) -> Admin:
    ok, msg = validate_password_strength(new_password)
    if not ok:
        raise AppException(ErrorCode.PASSWORD_WEAK, detail=msg)
    user = get_user(db, user_id)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    if not user:
        raise AppException(ErrorCode.USER_NOT_FOUND)
    try:
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.USER_HAS_DEPENDENCIES) from exc
