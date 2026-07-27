"""Invoice (factures) schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


INVOICE_STATUS = Literal["En attente", "En cours de traitement", "Validée", "Refusée"]


class InvoiceIn(BaseModel):
    commentaire: str | None = None
    date_depot: date | None = None


class InvoiceStatusUpdate(BaseModel):
    status: INVOICE_STATUS


class InvoiceFileOut(BaseModel):
    id: int
    nom_fichier: str
    taille_fichier: int | None = None
    type_fichier: str | None = None
    date_upload: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceOut(BaseModel):
    id: int
    id_user: int
    commentaire: str | None = None
    date_depot: date
    status: INVOICE_STATUS
    created_at: datetime
    user_full_name: str | None = None
    user_email: str | None = None
    files: list[InvoiceFileOut] = []

    model_config = ConfigDict(from_attributes=True)
