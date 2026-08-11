"""Schemas du referentiel des evenements."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    date_evenement: date | None = None
    date_fin: date | None = None
    url: str | None = None
    source: str
    is_active: bool
    helloasso_state: str | None = None
    last_synced_at: datetime | None = None


class EventCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    date_evenement: date | None = None


class EventUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    date_evenement: date | None = None
    is_active: bool | None = None


class EventSyncResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = []
