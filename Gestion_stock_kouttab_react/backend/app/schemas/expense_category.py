"""Schemas du referentiel des categories de depense."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    is_default: bool
    is_active: bool
    ordre: int
    created_at: datetime | None = None


class ExpenseCategoryCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    ordre: int = 0


class ExpenseCategoryUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    ordre: int | None = None
