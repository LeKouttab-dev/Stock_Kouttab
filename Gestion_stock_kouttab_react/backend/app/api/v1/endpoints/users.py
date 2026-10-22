"""User management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.core.rate_limit import limiter
from app.core.tablette import ROLE_TABLETTE, est_compte_tablette
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
from app.services import email_layout, liens, outbox
from app.services import rib as rib_service
from app.services.files import lire_en_memoire


logger = get_logger("users")

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
    )
    return UserDetailOut.model_validate(user)


# --- RIB : transmis au tresorier, jamais conserve ---------------------------
#
# Cf. `services/rib.py`. Le benevole donne son IBAN et son releve en un seul
# geste ; les deux partent par courriel au tresorier, et la base ne garde que
# la date de transmission et la fin de l'IBAN. Plus rien a telecharger ici :
# il n'y a plus rien a servir.


@router.post("/me/rib", response_model=UserDetailOut)
@limiter.limit("10/hour")
async def transmettre_mon_rib(
    request: Request,
    background_tasks: BackgroundTasks,
    iban: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    # Destination verifiee d'abord : inutile de lire un releve bancaire qu'on
    # ne saura envoyer nulle part.
    rib_service.destinataire()
    iban_net = rib_service.normaliser_iban(iban)
    if not rib_service.iban_valide(iban_net):
        raise AppException(ErrorCode.IBAN_INVALIDE)
    # Converti en PDF quel qu'ait ete le format depose, et sans passer par le
    # disque : refuser la photo bloquerait ceux qui n'ont que leur telephone.
    depot = await lire_en_memoire(file, "rib", convertir_en_pdf=True)
    await rib_service.envoyer_au_tresorier(current_user, iban=iban_net, pdf=depot["contenu"])
    rib_service.marquer_transmis(current_user, iban_net)
    db.commit()
    db.refresh(current_user)
    logger.info("RIB transmis au tresorier (compte %s)", current_user.id)
    background_tasks.add_task(rib_service.confirmer_au_benevole, current_user)
    return UserDetailOut.model_validate(current_user)


@router.patch(
    "/{user_id}/validate",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def validate_user(
    user_id: int,
    payload: UserValidate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    if payload.validation_status == "rejected":
        # Reject = delete (legacy behaviour).
        user_crud.delete_user(db, user_id)
        return UserOut(
            id=user_id,
            username="",
            role="Benevole",
            validation_status="rejected",
        )
    # Le statut d'avant : accepter deux fois le meme compte ne doit pas lui
    # renvoyer une deuxieme fois « votre compte vient d'etre valide ».
    avant = user_crud.get_user(db, user_id)
    deja_actif = avant is not None and avant.validation_status == "active"

    user = user_crud.update_validation_status(db, user_id, payload.validation_status)

    if not deja_actif:
        _annoncer_l_acces(db, user, background, valide_par=current_user.id)
    return UserOut.model_validate(user)


def _annoncer_l_acces(
    db: Session, user: Admin, background: BackgroundTasks, *, valide_par: int
) -> None:
    """Previent le demandeur que son compte est ouvert.

    Rien ne partait : la demande d'inscription prevenait les Super Admins, leur
    reponse ne prevenait personne. Le demandeur restait devant un ecran de
    connexion qui refusait son mot de passe — le compte n'etait plus `pending`,
    mais il n'avait aucun moyen de l'apprendre autrement qu'en reessayant au
    hasard. C'est arrive a un benevole valide le 2026-09-07.

    Par la file, et non en envoi tolerant : c'est le seul message que recoit le
    demandeur, et un SMTP coupe le ferait disparaitre sans laisser de trace. La
    ligne apparait alors dans Administration > Envois, et se relance.
    """
    if not user.email:
        logger.info(
            "Compte %s valide sans courriel d'annonce : aucune adresse au dossier.",
            user.username,
        )
        return

    envoi = outbox.enqueue(
        db,
        kind="compte_valide",
        entity_type="user",
        entity_id=user.id,
        recipients=[user.email],
        subject="Votre compte Le Kouttâb est actif",
        body=email_layout.composer(
            prenom=user.prenom,
            introduction=(
                "Votre demande de compte a ete acceptee : vous pouvez des "
                "maintenant vous connecter avec l'identifiant et le mot de passe "
                "choisis lors de votre inscription."
            ),
            blocs=[("Identifiant", user.username), ("Role", user.role)],
            # Le lien depend du COMPTE : un BenevoleFrais n'a pas de mot de passe
            # stock, l'ecran de connexion serait une impasse (cf. services/liens).
            conclusion=liens.avec_lien(
                "Si le mot de passe ne vous revient pas, utilisez « Mot de passe "
                "oublie » depuis l'ecran de connexion.",
                liens.lien_espace(user.role, "login"),
            ),
        ),
        triggered_by=valide_par,
    )
    background.add_task(outbox.try_send_now, envoi.id)


@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
def update_role(user_id: int, payload: UserRoleUpdate, db: Session = Depends(get_db)) -> Any:
    # Le compte partage de la tablette s'ouvre sans mot de passe (cle de la
    # caisse + un nom) : il doit rester confine a la buvette.
    if est_compte_tablette(user_crud.get_user(db, user_id)) and payload.role != ROLE_TABLETTE:
        raise AppException(
            ErrorCode.FORBIDDEN,
            detail="Le compte de la tablette reste « AdminStock » (buvette seule).",
        )
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
