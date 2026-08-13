"""Espace de contact : des fils de discussion, et non un formulaire d'envoi.

Le formulaire mettait un courriel en file et n'en gardait rien. La reponse
partait de la boite du comptable, hors de l'application : impossible de dire
quelles questions restaient sans reponse, ni de retrouver six mois plus tard ce
qui avait ete repondu.

Le courriel subsiste, mais il **previent** seulement — il ne porte plus la
conversation. Il continue de passer par `outbox.enqueue` : la file gere deja les
pannes SMTP, et surtout le fil, lui, est deja enregistre. Un serveur de
messagerie en panne ne fait plus perdre la question, il retarde une notification.

Deux choses ne changent pas :

- **L'auteur n'est jamais saisi.** Le serveur reprend l'identite du compte
  connecte. Un champ « votre nom » se remplit de n'importe quoi.
- **Le destinataire est un mot-cle, pas une adresse.** Accepter une adresse
  ferait de cet endpoint un relais de courriel ouvert.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.crud import conversation as conversation_crud
from app.crud import user as user_crud
from app.db.models import Admin, Conversation
from app.db.session import get_db
from app.schemas.contact import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    StatutUpdate,
    TransfertIn,
)
from app.services import outbox
from app.services.email_layout import composer


router = APIRouter(prefix="/conversations", tags=["contact"])

LIBELLES = {
    Conversation.DEST_COMPTA: "la comptabilite",
    Conversation.DEST_ADMIN: "l'administration",
}


def _adresses_equipe(db: Session, cible: str) -> list[str]:
    """Adresses resolues **cote serveur**, jamais recues du client."""
    if cible == Conversation.DEST_COMPTA:
        return list(settings.compta_emails)
    return user_crud.get_emails_by_roles(db, ["Super Admin"])


def _prevenir(
    db: Session,
    conversation: Conversation,
    *,
    corps: str,
    vers_equipe: bool,
    declencheur: int,
) -> None:
    """Notifie l'autre partie qu'il se passe quelque chose sur le fil.

    Le contenu du message est repris dans le courriel : obliger a se connecter
    pour savoir de quoi il retourne ferait manquer les demandes urgentes.
    """
    if vers_equipe:
        destinataires = _adresses_equipe(db, conversation.destinataire)
        prenom = None
        introduction = (
            f"{conversation.user.full_name or conversation.user.username} "
            f"vous ecrit depuis l'application.\n\n{corps}"
        )
        conclusion = "Repondez depuis l'espace « Nous contacter » de l'application."
    else:
        destinataires = [conversation.user.email] if conversation.user.email else []
        prenom = conversation.user.prenom
        introduction = f"Vous avez une reponse a votre question.\n\n{corps}"
        conclusion = "Retrouvez le fil dans l'espace « Nous contacter » de l'application."

    outbox.enqueue(
        db,
        kind="conversation",
        entity_type="conversation",
        entity_id=conversation.id,
        recipients=destinataires,
        subject=f"[Contact] {conversation.sujet}",
        body=composer(
            prenom=prenom,
            introduction=introduction,
            blocs=[
                ("Sujet", conversation.sujet),
                ("Demandeur", conversation.user.full_name if conversation.user else None),
                ("Statut", conversation.statut),
            ],
            conclusion=conclusion,
        ),
        triggered_by=declencheur,
    )


@router.post("", response_model=ConversationOut)
def ouvrir_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    conversation = conversation_crud.creer(
        db,
        auteur=current_user,
        destinataire=payload.destinataire,
        sujet=payload.sujet,
        message=payload.message,
    )
    _prevenir(
        db,
        conversation,
        corps=payload.message,
        vers_equipe=True,
        declencheur=current_user.id,
    )
    return conversation_crud.serialiser(conversation, pour=current_user)


@router.get("", response_model=list[ConversationOut])
def mes_conversations(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    return [
        conversation_crud.serialiser(c, pour=current_user)
        for c in conversation_crud.lister_les_miennes(db, current_user.id)
    ]


@router.get("/equipe", response_model=list[ConversationOut])
def conversations_de_l_equipe(
    statut: str | None = None,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Boite de l'equipe, filtree par ce que le role couvre.

    Un role sans portee recoit une liste vide plutot qu'un refus : c'est le meme
    parti que les compteurs de notification — l'interface n'a pas a distinguer
    « rien a traiter » de « pas concerne ».
    """
    return [
        conversation_crud.serialiser(c, pour=current_user)
        for c in conversation_crud.lister_pour_equipe(db, user=current_user, statut=statut)
    ]


@router.get("/{conversation_id}", response_model=ConversationOut)
def lire_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    conversation = conversation_crud.get_conversation(db, conversation_id, user=current_user)
    conversation_crud.marquer_lu(db, conversation, user=current_user)
    return conversation_crud.serialiser(conversation, pour=current_user)


@router.post("/{conversation_id}/messages", response_model=ConversationOut)
def repondre(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    conversation = conversation_crud.repondre(
        db, conversation_id, auteur=current_user, corps=payload.corps
    )
    _prevenir(
        db,
        conversation,
        corps=payload.corps,
        vers_equipe=conversation.id_user == current_user.id,
        declencheur=current_user.id,
    )
    return conversation_crud.serialiser(conversation, pour=current_user)


@router.patch("/{conversation_id}/statut", response_model=ConversationOut)
def changer_statut(
    conversation_id: int,
    payload: StatutUpdate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    conversation = conversation_crud.changer_statut(
        db, conversation_id, user=current_user, statut=payload.statut
    )
    return conversation_crud.serialiser(conversation, pour=current_user)


@router.patch("/{conversation_id}/destinataire", response_model=ConversationOut)
def transferer(
    conversation_id: int,
    payload: TransfertIn,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    conversation = conversation_crud.transferer(
        db, conversation_id, user=current_user, destinataire=payload.destinataire
    )
    return conversation_crud.serialiser(conversation, pour=current_user)

