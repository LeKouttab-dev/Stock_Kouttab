"""Expense (notes de frais) schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EXPENSE_STATUS = Literal["En attente", "Approuvée", "Refusée", "Remboursée"]


class ExpenseBase(BaseModel):
    date_depense: date
    rattachement: str | None = None
    fournisseur: str | None = None
    nature_charge: str | None = None
    montant: Decimal = Field(ge=0)
    commentaires: str | None = None
    remboursement_deja_emis: Decimal = Field(default=Decimal("0"), ge=0)
    remise: Decimal = Field(default=Decimal("0"), ge=0)


class ExpenseIn(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    date_depense: date | None = None
    rattachement: str | None = None
    fournisseur: str | None = None
    nature_charge: str | None = None
    montant: Decimal | None = None
    commentaires: str | None = None
    remboursement_deja_emis: Decimal | None = None
    remise: Decimal | None = None


class ExpenseValidate(BaseModel):
    status: EXPENSE_STATUS
    commentaires_compta: str | None = None


class ExpenseFileOut(BaseModel):
    id: int
    nom_fichier: str
    taille_fichier: int | None = None
    type_fichier: str | None = None
    date_upload: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseOut(ExpenseBase):
    id: int
    id_user: int
    status: EXPENSE_STATUS
    commentaires_compta: str | None = None
    date_soumission: datetime
    user_full_name: str | None = None
    user_email: str | None = None
    user_rib: str | None = None
    files: list[ExpenseFileOut] = []

    model_config = ConfigDict(from_attributes=True)
