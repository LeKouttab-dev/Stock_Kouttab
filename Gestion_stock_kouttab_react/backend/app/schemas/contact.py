"""Schemas de l'espace de contact."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ContactIn(BaseModel):
    # Le destinataire est un mot-cle, pas une adresse : le serveur seul sait a
    # qui il correspond (cf. `endpoints/contact.py`).
    destinataire: Literal["compta", "admin"]
    sujet: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=10, max_length=5000)
