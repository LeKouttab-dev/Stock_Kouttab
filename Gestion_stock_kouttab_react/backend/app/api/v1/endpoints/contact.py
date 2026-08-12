"""Espace de contact : poser une question depuis l'application.

Les benevoles ecrivaient par messages prives, a qui ils trouvaient. Une question
sur un remboursement partait a l'administration, une demande de compte a la
comptabilite, et beaucoup restaient sans reponse faute d'avoir atterri au bon
endroit.

Deux choix portent tout le module :

- **L'auteur n'est jamais saisi.** Le serveur reprend l'identite du compte
  connecte. Un champ « votre nom » se remplit de n'importe quoi, et une question
  signee d'un nom invente ne se traite pas.
- **L'envoi passe par la file** (`outbox.enqueue`) plutot que par un envoi
  direct : elle gere deja les echecs SMTP et les reprises. Une question posee ne
  doit pas se perdre parce que le serveur de messagerie hoquetait, et le
  demandeur, lui, a vu son message partir.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import user as user_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.auth import MessageOut
from app.schemas.contact import ContactIn
from app.services import outbox
from app.services.email_layout import composer


router = APIRouter(prefix="/contact", tags=["contact"])

# Le libelle affiche au demandeur, pour que l'accuse de reception dise a qui le
# message est parti.
LIBELLES = {"compta": "la comptabilite", "admin": "l'administration"}


def _destinataires(db: Session, cible: str) -> list[str]:
    """Adresses resolues **cote serveur**.

    Le formulaire n'envoie qu'un mot-cle : laisser le client choisir une adresse
    ferait de cet endpoint un relais de courriel ouvert, utilisable pour ecrire a
    n'importe qui au nom de l'institut.
    """
    if cible == "compta":
        return list(settings.compta_emails)
    return user_crud.get_emails_by_roles(db, ["Super Admin"])


@router.post("", response_model=MessageOut)
def envoyer_message(
    payload: ContactIn,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    cible = payload.destinataire
    if cible not in LIBELLES:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Destinataire inconnu.")

    auteur = current_user.full_name or current_user.username
    corps = composer(
        introduction=(
            f"{auteur} vous ecrit depuis l'application.\n\n"
            f"Objet : {payload.sujet}\n\n{payload.message}"
        ),
        blocs=[
            ("Demandeur", auteur),
            ("Identifiant", current_user.username),
            ("Role", current_user.role),
            # Sans elle, repondre suppose de retrouver la personne dans
            # l'annuaire : la question resterait en attente.
            ("Adresse", current_user.email),
            ("Telephone", current_user.telephone),
        ],
        conclusion="Repondez directement a cette adresse.",
    )

    outbox.enqueue(
        db,
        kind="contact",
        entity_type="contact",
        entity_id=current_user.id,
        recipients=_destinataires(db, cible),
        subject=f"[Contact] {payload.sujet}",
        body=corps,
        triggered_by=current_user.id,
    )
    return MessageOut(message=f"Message transmis a {LIBELLES[cible]}.")
