"""Schemas des tickets de justificatif."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    """Ouverture d'une demande.

    Seuls le benevole et le libelle sont exiges : un ticket qu'on ne pourrait
    pas ouvrir faute de connaitre le montant exact ne serait jamais ouvert.
    """

    id_user: int
    libelle: str = Field(min_length=1, max_length=255)
    description: str | None = None
    montant_attendu: Decimal | None = None
    date_achat: date | None = None
    fournisseur: str | None = Field(default=None, max_length=255)


class TicketUpdate(BaseModel):
    libelle: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    montant_attendu: Decimal | None = None
    date_achat: date | None = None
    fournisseur: str | None = Field(default=None, max_length=255)


class TicketClose(BaseModel):
    """Cloture, avec rattachement facultatif a la piece recue."""

    id_facture: int | None = None
    # Annuler plutot que clore : la demande n'avait pas lieu d'etre, et la
    # distinction se lit dans l'historique.
    annule: bool = False


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_user: int
    libelle: str
    description: str | None = None
    montant_attendu: Decimal | None = None
    date_achat: date | None = None
    fournisseur: str | None = None
    statut: str
    id_facture: int | None = None
    rappels_envoyes: int
    dernier_rappel_at: datetime | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None
    user_full_name: str | None = None


class TicketRecipientOut(BaseModel):
    """Destinataire possible d'une demande, reduit au strict necessaire.

    Volontairement pauvre : ce menu deroulant a besoin d'un identifiant et d'un
    nom. Ni adresse, ni role, ni telephone — la comptabilite nomme un benevole,
    elle ne consulte pas l'annuaire.
    """

    id: int
    nom_complet: str
