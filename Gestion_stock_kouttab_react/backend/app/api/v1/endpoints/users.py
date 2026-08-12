"""User management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import user as user_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.user import (
    ProfileUpdate,
    UserDetailOut,
    UserOut,
    UserRoleUpdate,
    UserValidate,
)
from app.services.files import lire_en_memoire


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_roles("Super Admin"))])
def list_users(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    return [UserOut.model_validate(u) for u in user_crud.list_users(db, exclude_id=current_user.id)]


@router.get(
    "/annuaire",
    response_model=list[UserOut],
    dependencies=[Depends(require_roles("Compta", "Super Admin"))],
)
def list_annuaire(db: Session = Depends(get_db)) -> Any:
    """Benevoles inscrits, **en lecture seule**.

    La comptabilite a besoin de savoir qui est inscrit et sous quel role : elle
    rembourse ces personnes et leur reclame des pieces. Elle n'a pas a gerer les
    comptes pour autant — `GET /users` porte les actions (roles, suppression) et
    reste ferme au Super Admin.

    `UserOut` n'expose pas le RIB, contrairement a `UserDetailOut` : cet ecran
    est un annuaire, pas un fichier de coordonnees bancaires.
    """
    return [UserOut.model_validate(u) for u in user_crud.list_users(db)]


@router.get(
    "/pending",
    response_model=list[UserOut],
    dependencies=[Depends(require_roles("Super Admin"))],
)
def list_pending(db: Session = Depends(get_db)) -> Any:
    return [UserOut.model_validate(u) for u in user_crud.list_pending_users(db)]


@router.get("/me/profile", response_model=UserDetailOut)
def get_my_profile(current_user: Admin = Depends(get_current_user)) -> Any:
    return UserDetailOut.model_validate(current_user)


@router.patch("/me/profile", response_model=UserDetailOut)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    user = user_crud.update_profile(
        db,
        current_user.id,
        nom=payload.nom,
        prenom=payload.prenom,
        email=str(payload.email) if payload.email else None,
        telephone=payload.telephone,
        rib=payload.rib,
    )
    return UserDetailOut.model_validate(user)


# --- Releve d'identite bancaire en document ---------------------------------
#
# L'IBAN saisi dans le profil sert au virement, ce document sert de preuve : la
# comptabilite le reclamait par messages prives faute de pouvoir le recuperer
# ici. Acces identique a celui du RIB (CLAUDE.md §5) : le proprietaire, la
# Compta, le Super Admin. Personne d'autre, c'est une donnee bancaire.


def _peut_voir_le_rib(demandeur: Admin, proprietaire_id: int) -> bool:
    return demandeur.role in ("Compta", "Super Admin") or demandeur.id == proprietaire_id


def _servir_rib(user: Admin) -> Response:
    if not user.rib_document:
        raise AppException(ErrorCode.NOT_FOUND, detail="Aucun RIB depose.")
    nom = (user.rib_document_nom or "rib.pdf").replace('"', "")
    return Response(
        content=user.rib_document,
        media_type=user.rib_document_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


@router.post("/me/rib-document", response_model=UserDetailOut)
async def upload_my_rib_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    depot = await lire_en_memoire(file, "rib")
    current_user.rib_document = depot["contenu"]
    current_user.rib_document_nom = str(depot["filename"])[:255]
    current_user.rib_document_type = str(depot["mime"])[:100]
    db.commit()
    db.refresh(current_user)
    return UserDetailOut.model_validate(current_user)


@router.get("/me/rib-document")
def download_my_rib_document(current_user: Admin = Depends(get_current_user)) -> Response:
    return _servir_rib(current_user)


@router.delete("/me/rib-document", response_model=MessageOut)
def delete_my_rib_document(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    current_user.rib_document = None
    current_user.rib_document_nom = None
    current_user.rib_document_type = None
    db.commit()
    return MessageOut(message="RIB supprime.")


@router.get("/{user_id}/rib-document")
def download_rib_document(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Response:
    """Telechargement par la comptabilite, au moment de payer.

    Le controle porte sur le role **et** sur la propriete : un benevole qui
    devine l'identifiant d'un collegue ne doit pas recuperer ses coordonnees
    bancaires. C'est exactement la regle de `_can_see_rib` cote notes de frais.
    """
    if not _peut_voir_le_rib(current_user, user_id):
        raise AppException(ErrorCode.FORBIDDEN)
    user = user_crud.get_user(db, user_id)
    if user is None:
        raise AppException(ErrorCode.NOT_FOUND, detail="Utilisateur introuvable.")
    return _servir_rib(user)


@router.patch(
    "/{user_id}/validate",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def validate_user(user_id: int, payload: UserValidate, db: Session = Depends(get_db)) -> Any:
    if payload.validation_status == "rejected":
        # Reject = delete (legacy behaviour).
        user_crud.delete_user(db, user_id)
        return UserOut(
            id=user_id,
            username="",
            role="Benevole",
            validation_status="rejected",
        )
    user = user_crud.update_validation_status(db, user_id, payload.validation_status)
    return UserOut.model_validate(user)


@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def update_role(user_id: int, payload: UserRoleUpdate, db: Session = Depends(get_db)) -> Any:
    user = user_crud.update_role(db, user_id, payload.role)
    return UserOut.model_validate(user)


@router.delete(
    "/{user_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Any:
    user_crud.delete_user(db, user_id)
    return MessageOut(message="Utilisateur supprime.")
