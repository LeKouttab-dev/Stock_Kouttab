"""Schemas des fils de discussion."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DESTINATAIRE = Literal["compta", "admin"]
STATUT = Literal["ouverte", "en_cours", "traitee"]


class ConversationCreate(BaseModel):
    # Le destinataire est un mot-cle, pas une adresse : le serveur seul sait a
    # qui il correspond (cf. `crud/conversation.py`).
    destinataire: DESTINATAIRE
    sujet: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=10, max_length=5000)


class MessageCreate(BaseModel):
    # Plus court qu'a l'ouverture : une reponse peut tenir en « C'est fait. »,
    # alors qu'une question posee en trois mots ne se traite pas.
    corps: str = Field(min_length=1, max_length=5000)


class StatutUpdate(BaseModel):
    statut: STATUT


class TransfertIn(BaseModel):
    destinataire: DESTINATAIRE


class MessageOut(BaseModel):
    id: int
    auteur_nom: str
    de_l_equipe: bool
    est_moi: bool
    corps: str
    created_at: datetime | None = None


class ConversationOut(BaseModel):
    id: int
    id_user: int
    demandeur: str | None = None
    destinataire: str
    sujet: str
    statut: str
    attente_equipe: bool
    non_lu_demandeur: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    nombre_messages: int
    dernier_message: str | None = None
    dernier_message_at: datetime | None = None
    # Pastille calculee pour le demandeur de la requete, et pour lui seul.
    a_signaler: bool
    messages: list[MessageOut] = []
