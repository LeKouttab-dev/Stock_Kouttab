"""Fils de discussion entre les benevoles et l'equipe.

Toute la mecanique du fil vit ici, et pas dans l'endpoint : ouvrir un fil et y
repondre partagent les memes regles d'etat, et les separer les ferait diverger
au premier ajout.

**Qui voit quoi.** Un fil se lit par son auteur et par l'equipe dont il releve.
La comptabilite ne lit pas les questions adressees a l'administration : ce sont
des demandes de compte, de role, parfois des differends — les acheminer ailleurs
etait justement le probleme que ce module resout, l'ouvrir a tous serait pire.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.db.models import Admin, Conversation, ConversationMessage


# Ce que chaque role peut lire dans la boite de l'equipe. Le Super Admin voit
# les deux : il est le recours quand une question a ete mal adressee.
PORTEE = {
    "Compta": (Conversation.DEST_COMPTA,),
    "Super Admin": (Conversation.DEST_COMPTA, Conversation.DEST_ADMIN),
}

STATUTS = (
    Conversation.STATUT_OUVERTE,
    Conversation.STATUT_EN_COURS,
    Conversation.STATUT_TRAITEE,
)


def portee_de(user: Admin) -> tuple[str, ...]:
    return PORTEE.get(user.role, ())


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def peut_lire(conversation: Conversation, user: Admin) -> bool:
    if conversation.id_user == user.id:
        return True
    return conversation.destinataire in portee_de(user)


def _charger(db: Session, conversation_id: int) -> Conversation:
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.user))
        .where(Conversation.id == conversation_id)
    )
    conversation = db.execute(stmt).scalar_one_or_none()
    if conversation is None:
        raise AppException(ErrorCode.NOT_FOUND, detail="Conversation introuvable.")
    return conversation


def get_conversation(db: Session, conversation_id: int, *, user: Admin) -> Conversation:
    conversation = _charger(db, conversation_id)
    if not peut_lire(conversation, user):
        raise AppException(ErrorCode.FORBIDDEN)
    return conversation


def creer(
    db: Session,
    *,
    auteur: Admin,
    destinataire: str,
    sujet: str,
    message: str,
) -> Conversation:
    if destinataire not in (Conversation.DEST_COMPTA, Conversation.DEST_ADMIN):
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Destinataire inconnu.")

    conversation = Conversation(
        id_user=auteur.id,
        destinataire=destinataire,
        sujet=sujet.strip(),
        statut=Conversation.STATUT_OUVERTE,
        attente_equipe=True,
        non_lu_demandeur=False,
    )
    db.add(conversation)
    db.flush()
    _ajouter_message(db, conversation, auteur=auteur, corps=message, de_l_equipe=False)
    db.commit()
    return _charger(db, conversation.id)


def repondre(db: Session, conversation_id: int, *, auteur: Admin, corps: str) -> Conversation:
    conversation = get_conversation(db, conversation_id, user=auteur)
    de_l_equipe = conversation.id_user != auteur.id

    _ajouter_message(db, conversation, auteur=auteur, corps=corps, de_l_equipe=de_l_equipe)

    if de_l_equipe:
        # Une reponse de l'equipe fait sortir le fil de la pile a traiter, et
        # allume la pastille du demandeur.
        conversation.attente_equipe = False
        conversation.non_lu_demandeur = True
        if conversation.statut == Conversation.STATUT_OUVERTE:
            conversation.statut = Conversation.STATUT_EN_COURS
    else:
        conversation.attente_equipe = True
        conversation.non_lu_demandeur = False
        # Relancer sur un fil clos le rouvre. Sans cela, une precision demandee
        # apres coup ne serait jamais lue : le fil est range, plus personne ne
        # le regarde.
        if conversation.statut == Conversation.STATUT_TRAITEE:
            conversation.statut = Conversation.STATUT_EN_COURS
            conversation.closed_at = None
            conversation.closed_by = None

    db.commit()
    return _charger(db, conversation.id)


def _ajouter_message(
    db: Session,
    conversation: Conversation,
    *,
    auteur: Admin,
    corps: str,
    de_l_equipe: bool,
) -> ConversationMessage:
    texte = corps.strip()
    if not texte:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Message vide.")
    message = ConversationMessage(
        id_conversation=conversation.id,
        id_auteur=auteur.id,
        auteur_nom=auteur.full_name or auteur.username,
        de_l_equipe=de_l_equipe,
        corps=texte,
    )
    db.add(message)
    return message


def marquer_lu(db: Session, conversation: Conversation, *, user: Admin) -> None:
    """Ouvrir le fil eteint sa pastille, pour ce cote-la seulement."""
    if conversation.id_user == user.id and conversation.non_lu_demandeur:
        conversation.non_lu_demandeur = False
        db.commit()


def changer_statut(
    db: Session, conversation_id: int, *, user: Admin, statut: str
) -> Conversation:
    """Reserve a l'equipe : c'est elle qui traite, elle qui clot."""
    if statut not in STATUTS:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Statut inconnu.")
    conversation = _charger(db, conversation_id)
    if conversation.destinataire not in portee_de(user):
        raise AppException(ErrorCode.FORBIDDEN)

    conversation.statut = statut
    if statut == Conversation.STATUT_TRAITEE:
        conversation.closed_at = _maintenant()
        conversation.closed_by = user.id
        conversation.attente_equipe = False
        # Le demandeur doit apprendre que sa question est close, sans quoi il
        # attendrait une reponse qui ne viendra plus.
        conversation.non_lu_demandeur = True
    else:
        conversation.closed_at = None
        conversation.closed_by = None
    db.commit()
    return _charger(db, conversation.id)


def transferer(db: Session, conversation_id: int, *, user: Admin, destinataire: str) -> Conversation:
    """Reoriente un fil mal adresse — le Super Admin seul, qui voit les deux.

    Une question de remboursement partie a l'administration restait sinon sans
    reponse : c'est exactement ce que ce module devait supprimer.
    """
    if destinataire not in (Conversation.DEST_COMPTA, Conversation.DEST_ADMIN):
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Destinataire inconnu.")
    conversation = _charger(db, conversation_id)
    if conversation.destinataire not in portee_de(user):
        raise AppException(ErrorCode.FORBIDDEN)
    conversation.destinataire = destinataire
    conversation.attente_equipe = True
    db.commit()
    return _charger(db, conversation.id)


def lister_les_miennes(db: Session, user_id: int) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.user))
        .where(Conversation.id_user == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def lister_pour_equipe(
    db: Session, *, user: Admin, statut: str | None = None
) -> list[Conversation]:
    portee = portee_de(user)
    if not portee:
        return []
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.user))
        .where(Conversation.destinataire.in_(portee))
        .order_by(Conversation.updated_at.desc())
    )
    if statut:
        stmt = stmt.where(Conversation.statut == statut)
    return list(db.execute(stmt).scalars().all())


def serialiser(conversation: Conversation, *, pour: Admin) -> dict[str, Any]:
    messages = sorted(conversation.messages, key=lambda m: m.id)
    dernier = messages[-1] if messages else None
    return {
        "id": conversation.id,
        "id_user": conversation.id_user,
        "demandeur": conversation.user.full_name if conversation.user else None,
        "destinataire": conversation.destinataire,
        "sujet": conversation.sujet,
        "statut": conversation.statut,
        "attente_equipe": conversation.attente_equipe,
        "non_lu_demandeur": conversation.non_lu_demandeur,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "nombre_messages": len(messages),
        "dernier_message": dernier.corps if dernier else None,
        "dernier_message_at": dernier.created_at if dernier else None,
        # `pour` decide de la pastille : l'equipe regarde ce qui attend une
        # reponse, le demandeur ce qu'il n'a pas encore lu.
        "a_signaler": (
            conversation.non_lu_demandeur
            if conversation.id_user == pour.id
            else conversation.attente_equipe and conversation.statut != Conversation.STATUT_TRAITEE
        ),
        "messages": [
            {
                "id": m.id,
                "auteur_nom": m.auteur_nom,
                "de_l_equipe": m.de_l_equipe,
                "est_moi": m.id_auteur == pour.id,
                "corps": m.corps,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }
