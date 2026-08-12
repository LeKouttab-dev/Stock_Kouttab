"""Schemas des remboursements groupes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.reimbursement_options import (
    APPROBATEUR_PAR_DEFAUT,
    ETABLISSEMENT_PAR_DEFAUT,
    MOYEN_PAR_DEFAUT,
)


class ReimbursementCreate(BaseModel):
    """Demande de remboursement groupe.

    Seules les notes sont obligatoires : le reste porte les valeurs arretees
    avec le client, que le comptable n'a a modifier qu'en cas d'exception.
    """

    expense_ids: list[int] = Field(min_length=1)
    date_remboursement: date | None = None
    moyen: str = MOYEN_PAR_DEFAUT
    etablissement: str = ETABLISSEMENT_PAR_DEFAUT
    approuve_par: str = Field(default=APPROBATEUR_PAR_DEFAUT, max_length=120)
    commentaire: str | None = None


class ReimbursementExpenseOut(BaseModel):
    """Note soldee, telle qu'elle apparait sur le justificatif."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date_depense: date
    montant: Decimal
    fournisseur: str | None = None
    nature_charge: str | None = None
    evenement: str | None = None
    categorie: str | None = None


class ReimbursementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_user: int
    date_remboursement: date
    moyen: str
    etablissement: str
    approuve_par: str
    montant_total: Decimal
    commentaire: str | None = None
    created_at: datetime | None = None
    # Presence des documents, sans exposer leur chemin sur le serveur.
    a_pdf: bool = False
    a_xlsx: bool = False
    user_full_name: str | None = None
    expenses: list[ReimbursementExpenseOut] = []


class VolunteerExpensesOut(BaseModel):
    """Fiche d'un benevole dans l'ecran comptable."""

    id_user: int
    nom_complet: str | None = None
    email: str | None = None
    nb_notes: int
    nb_a_rembourser: int
    total_du: Decimal


class ReimbursementOptionsOut(BaseModel):
    """Listes proposees au formulaire, et valeurs pre-remplies."""

    moyens: list[str]
    etablissements: list[str]
    moyen_defaut: str
    etablissement_defaut: str
    approbateur_defaut: str
