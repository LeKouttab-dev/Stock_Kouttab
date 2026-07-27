"""Authentication endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    is_legacy_hash,
    validate_password_strength,
    validate_username,
    verify_password,
    verify_password_legacy,
)
from app.crud import invitation as invitation_crud
from app.crud import user as user_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import (
    AccessTokenOut,
    AdminSetupIn,
    InvitationValidateOut,
    LoginIn,
    MessageOut,
    RefreshIn,
    SignupIn,
    TokenOut,
)
from app.schemas.user import UserOut


router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth")


# Lockout: in-memory dictionary of {username_lower: (failed_count, locked_until)}.
# TODO: persist in DB or Redis once we move beyond MVP.
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_WINDOW_SECONDS = 15 * 60
_login_attempts: dict[str, tuple[int, datetime | None]] = {}


def _is_locked(username: str) -> tuple[bool, int]:
    rec = _login_attempts.get(username.lower())
    if not rec:
        return False, 0
    count, locked_until = rec
    if locked_until and datetime.now(timezone.utc) < locked_until:
        remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds())
        return True, remaining
    if locked_until and datetime.now(timezone.utc) >= locked_until:
        # Reset
        _login_attempts.pop(username.lower(), None)
    return False, 0


def _record_failure(username: str) -> None:
    key = username.lower()
    count, _ = _login_attempts.get(key, (0, None))
    count += 1
    locked_until = None
    if count >= _LOCKOUT_THRESHOLD:
        locked_until = datetime.now(timezone.utc).replace(microsecond=0)
        from datetime import timedelta

        locked_until = locked_until + timedelta(seconds=_LOCKOUT_WINDOW_SECONDS)
    _login_attempts[key] = (count, locked_until)


def _record_success(username: str) -> None:
    _login_attempts.pop(username.lower(), None)


def _to_user_out(user: Admin) -> UserOut:
    return UserOut.model_validate(user)


def _build_token_payload(user: Admin, password_must_change: bool) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=_to_user_out(user),
        password_must_change=password_must_change,
    )


# ---- Signup ----------------------------------------------------------------


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(payload: SignupIn, db: Session = Depends(get_db)) -> Any:
    if not validate_username(payload.username):
        raise AppException(ErrorCode.USERNAME_INVALID)
    ok, msg = validate_password_strength(payload.password)
    if not ok:
        raise AppException(ErrorCode.PASSWORD_WEAK, detail=msg)
    if payload.confirm_password is not None and payload.confirm_password != payload.password:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Les mots de passe ne correspondent pas.",
        )
    user = user_crud.create_pending_user(
        db,
        username=payload.username,
        password=payload.password,
        role=payload.role,
        nom=payload.nom,
        prenom=payload.prenom,
        email=str(payload.email) if payload.email else None,
        telephone=payload.telephone,
    )
    return _to_user_out(user)


# ---- Login -----------------------------------------------------------------


@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """Login endpoint accepting OAuth2-style form data."""
    username = (form_data.username or "").strip()
    password = form_data.password or ""
    return _do_login(db, username=username, password=password)


@router.post("/login/json", response_model=TokenOut)
def login_json(payload: LoginIn, db: Session = Depends(get_db)) -> Any:
    """Alternative JSON login endpoint."""
    return _do_login(db, username=payload.username, password=payload.password)


def _do_login(db: Session, *, username: str, password: str) -> TokenOut:
    if not username or not password:
        raise AppException(ErrorCode.INVALID_CREDENTIALS, detail="Identifiants requis.")
    locked, remaining = _is_locked(username)
    if locked:
        minutes = max(1, remaining // 60)
        raise AppException(
            ErrorCode.ACCOUNT_LOCKED,
            detail=(
                f"Trop de tentatives. Veuillez reessayer dans environ {minutes} minute(s)."
            ),
            extras={"retry_after_seconds": remaining},
        )

    user = user_crud.get_user_by_username(db, username)
    if user is None:
        _record_failure(username)
        raise AppException(ErrorCode.INVALID_CREDENTIALS)

    password_must_change = False
    if is_legacy_hash(user.password_hash):
        if not verify_password_legacy(password, user.password_hash):
            _record_failure(username)
            raise AppException(ErrorCode.INVALID_CREDENTIALS)
        password_must_change = True
    else:
        if not verify_password(password, user.password_hash):
            _record_failure(username)
            raise AppException(ErrorCode.INVALID_CREDENTIALS)

    if user.validation_status == "rejected":
        raise AppException(ErrorCode.ACCOUNT_REJECTED)
    if user.validation_status != "active":
        raise AppException(ErrorCode.ACCOUNT_PENDING)

    _record_success(username)
    logger.info("Login OK pour %s (role=%s)", username, user.role)
    return _build_token_payload(user, password_must_change)


# ---- Refresh ---------------------------------------------------------------


@router.post("/refresh", response_model=AccessTokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> Any:
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise AppException(
            ErrorCode.REFRESH_TOKEN_INVALID, detail="Token de mauvais type."
        )
    try:
        user_id = int(decoded.get("sub"))
    except (TypeError, ValueError) as exc:
        raise AppException(ErrorCode.REFRESH_TOKEN_INVALID) from exc
    user = user_crud.get_user(db, user_id)
    if not user or user.validation_status != "active":
        raise AppException(
            ErrorCode.REFRESH_TOKEN_INVALID,
            detail="Utilisateur introuvable ou inactif.",
        )
    return AccessTokenOut(access_token=create_access_token(user.id, user.role))


# ---- Logout (stateless no-op) ---------------------------------------------


@router.post("/logout", response_model=MessageOut)
def logout(_: Admin = Depends(get_current_user)) -> Any:
    # JWT is stateless: clients must drop their tokens locally.
    return MessageOut(message="Deconnecte.")


# ---- Me --------------------------------------------------------------------


@router.get("/me", response_model=UserOut)
def me(current_user: Admin = Depends(get_current_user)) -> Any:
    return _to_user_out(current_user)


# ---- Invitations -----------------------------------------------------------


@router.get("/validate-invitation", response_model=InvitationValidateOut)
def validate_invitation(
    token: str = Query(..., min_length=10),
    email: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
) -> Any:
    ok, message, _ = invitation_crud.validate_token(db, token, email)
    return InvitationValidateOut(valid=ok, message=message, email=email if ok else None)


@router.post("/admin-setup", response_model=TokenOut, status_code=201)
def admin_setup(payload: AdminSetupIn, db: Session = Depends(get_db)) -> Any:
    ok, message, invitation = invitation_crud.validate_token(
        db, payload.token, str(payload.email)
    )
    if not ok or invitation is None:
        if invitation is not None:
            invitation_crud.increment_attempts(db, invitation)
        # Map the invitation_crud message to the right code.
        lowered = message.lower()
        if "expir" in lowered:
            code = ErrorCode.INVITATION_EXPIRED
        elif "deja" in lowered or "deja utilis" in lowered or "utilise" in lowered:
            code = ErrorCode.INVITATION_USED
        elif "tentative" in lowered:
            code = ErrorCode.INVITATION_TOO_MANY_ATTEMPTS
        else:
            code = ErrorCode.INVITATION_INVALID
        raise AppException(code, detail=message)

    if not validate_username(payload.username):
        raise AppException(ErrorCode.USERNAME_INVALID)
    pw_ok, pw_msg = validate_password_strength(payload.password)
    if not pw_ok:
        raise AppException(ErrorCode.PASSWORD_WEAK, detail=pw_msg)

    user = user_crud.create_user(
        db,
        username=payload.username,
        password=payload.password,
        role="Super Admin",
        nom=payload.nom,
        prenom=payload.prenom,
        email=str(payload.email),
        validation_status="active",
    )
    invitation_crud.mark_used(db, invitation)
    logger.info("Super Admin '%s' cree via invitation pour %s", user.username, payload.email)
    return _build_token_payload(user, password_must_change=False)
