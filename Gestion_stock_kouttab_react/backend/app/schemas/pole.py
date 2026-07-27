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
    created_at: datetime | None = None


class PoleCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=120)
    ordre: int = 0


class PoleUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    ordre: int | None = None
