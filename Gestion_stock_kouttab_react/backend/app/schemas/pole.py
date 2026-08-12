"""Schemas du referentiel des poles."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    is_default: bool
    is_active: bool
    ordre: int
    # Dit au formulaire de depot ce qu'il doit demander sous ce pole : un
    # evenement, ou une categorie. Le front s'y fie pour afficher l'un ou
    # l'autre — il n'a aucune liste de poles en dur.
    requiert_evenement: bool = False
    # Famille d'evenements proposee sous ce pole (« T », « G », « J »).
    type_evenement: str | None = None
    created_at: datetime | None = None


class PoleCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    ordre: int = 0
    requiert_evenement: bool = False
    type_evenement: str | None = Field(default=None, max_length=10)


class PoleUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    ordre: int | None = None
    requiert_evenement: bool | None = None
    type_evenement: str | None = Field(default=None, max_length=10)
