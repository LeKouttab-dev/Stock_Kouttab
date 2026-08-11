"""Authentication endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.core.rate_limit import limiter
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
from app.crud import auth_security
from app.crud import invitation as invitation_crud
from app.crud import user as user_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import (
    AdminSetupIn,
    InvitationValidateOut,
    LoginIn,
    LogoutIn,
    MessageOut,
    RefreshIn,
    SignupIn,
    TokenOut,
)
from app.schemas.user import UserOut
from app.services import email as email_service


router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth")


def _client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    return get_remote_address(request) or "unknown"


def _to_user_out(user: Admin) -> UserOut:
    return UserOut.model_validate(user)


def _build_token_payload(
    db: Session, user: Admin, password_must_change: bool
) -> TokenOut:
    refresh, jti, expires_at = create_refresh_token(user.id)
    auth_security.store_refresh_token(
        db, user_id=user.id, jti=jti, expires_at=expires_at
    )
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        refresh_token=refresh,
        user=_to_user_out(user),
        password_must_change=password_must_change,
    )


# ---- Signup ----------------------------------------------------------------


@router.post("/signup", response_model=UserOut, status_code=201)
@limiter.limit("3/hour")
def signup(
    request: Request,
    payload: SignupIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Any:
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
        role="Benevole",  # jamais choisi par le demandeur — cf. SignupIn
        nom=payload.nom,
        prenom=payload.prenom,
        email=str(payload.email) if payload.email else None,
        telephone=payload.telephone,
    )
    # Les Super Admins sont prevenus : une demande d'inscription restait sinon
    # invisible jusqu'a ce que l'un d'eux ouvre l'ecran d'administration.
    background.add_task(
        _notify_account_request_safe,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
    )
    return _to_user_out(user)


async def _notify_account_request_safe(
    *, username: str, full_name: str | None, email: str | None
) -> None:
    """Envoi de confiance : une notification ratee ne doit pas perdre la demande.

    La tache de fond ouvre sa propre session : celle de la requete est refermee
    des la reponse envoyee.
    """
    try:
        with SessionLocal() as db:
            await email_service.send_new_account_request(
                db, username=username, full_name=full_name or username, email=email
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notification de demande de compte non envoyee : %s", exc)


# ---- Login -----------------------------------------------------------------


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/15minutes")
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """Login endpoint accepting OAuth2-style form data."""
    username = (form_data.username or "").strip()
    password = form_data.password or ""
    return _do_login(db, username=username, password=password, request=request)


@router.post("/login/json", response_model=TokenOut)
@limiter.limit("10/15minutes")
def login_json(
    request: Request, payload: LoginIn, db: Session = Depends(get_db)
) -> Any:
    """Alternative JSON login endpoint."""
    return _do_login(
        db, username=payload.username, password=payload.password, request=request
    )


def _do_login(
    db: Session, *, username: str, password: str, request: Request | None = None
) -> TokenOut:
    if not username or not password:
        raise AppException(ErrorCode.INVALID_CREDENTIALS, detail="Identifiants requis.")
    ip = _client_ip(request)
    locked, remaining = auth_security.is_locked(db, username, ip)
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
        auth_security.record_failure(db, username, ip)
        raise AppException(ErrorCode.INVALID_CREDENTIALS)

    password_must_change = False
    if is_legacy_hash(user.password_hash):
        if not verify_password_legacy(password, user.password_hash):
            auth_security.record_failure(db, username, ip)
            raise AppException(ErrorCode.INVALID_CREDENTIALS)
        password_must_change = True
    else:
        if not verify_password(password, user.password_hash):
            auth_security.record_failure(db, username, ip)
            raise AppException(ErrorCode.INVALID_CREDENTIALS)

    if user.validation_status == "rejected":
        raise AppException(ErrorCode.ACCOUNT_REJECTED)
    if user.validation_status != "active":
        raise AppException(ErrorCode.ACCOUNT_PENDING)

    auth_security.record_success(db, username, ip)
    logger.info("Login OK pour %s (role=%s)", username, user.role)
    return _build_token_payload(db, user, password_must_change)


# ---- Refresh ---------------------------------------------------------------


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> Any:
    """Echange un refresh token contre un couple neuf (rotation).

    L'ancien token est consomme : le rejouer revoque toutes les sessions du
    compte (cf. ``auth_security.consume_refresh_token``).
    """
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise AppException(
            ErrorCode.REFRESH_TOKEN_INVALID, detail="Token de mauvais type."
        )
    try:
        user_id = int(decoded.get("sub"))
    except (TypeError, ValueError) as exc:
        raise AppException(ErrorCode.REFRESH_TOKEN_INVALID) from exc

    jti = decoded.get("jti")
    if not jti:
        # Token emis avant l'introduction de la rotation : on le refuse pour
        # forcer une reconnexion propre plutot que de laisser un trou.
        raise AppException(
            ErrorCode.REFRESH_TOKEN_INVALID,
            detail="Session obsolete, merci de vous reconnecter.",
        )

    user = user_crud.get_user(db, user_id)
    if not user or user.validation_status != "active":
        raise AppException(
            ErrorCode.REFRESH_TOKEN_INVALID,
            detail="Utilisateur introuvable ou inactif.",
        )
    if not auth_security.consume_refresh_token(db, jti, user_id=user_id):
        raise AppException(
            ErrorCode.REFRESH_TOKEN_INVALID,
            detail="Session expiree ou revoquee, merci de vous reconnecter.",
        )
    return _build_token_payload(db, user, password_must_change=False)


# ---- Logout ----------------------------------------------------------------


@router.post("/logout", response_model=MessageOut)
def logout(
    payload: LogoutIn | None = None,
    current_user: Admin = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Revoque le refresh token fourni, ou toutes les sessions a defaut."""
    if payload is not None and payload.refresh_token:
        try:
            decoded = decode_token(payload.refresh_token)
        except AppException:
            decoded = {}
        jti = decoded.get("jti")
        if jti and int(decoded.get("sub", -1)) == current_user.id:
            auth_security.revoke_refresh_token(db, jti)
            return MessageOut(message="Deconnecte.")
    auth_security.revoke_all_for_user(db, current_user.id)
    return MessageOut(message="Deconnecte.")


# ---- Me --------------------------------------------------------------------


@router.get("/me", response_model=UserOut)
def me(current_user: Admin = Depends(get_current_user)) -> Any:
    return _to_user_out(current_user)


# ---- Invitations -----------------------------------------------------------


@router.get("/validate-invitation", response_model=InvitationValidateOut)
@limiter.limit("10/hour")
def validate_invitation(
    request: Request,
    token: str = Query(..., min_length=10),
    email: str = Query(..., min_length=5),
    db: Session = Depends(get_db),
) -> Any:
    ok, message, _ = invitation_crud.validate_token(db, token, email)
    return InvitationValidateOut(valid=ok, message=message, email=email if ok else None)


@router.post("/admin-setup", response_model=TokenOut, status_code=201)
@limiter.limit("5/hour")
def admin_setup(
    request: Request, payload: AdminSetupIn, db: Session = Depends(get_db)
) -> Any:
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
    return _build_token_payload(db, user, password_must_change=False)
