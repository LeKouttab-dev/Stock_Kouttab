"""Schemas du scan de justificatifs."""

from __future__ import annotations

from pydantic import BaseModel


class ScanCorner(BaseModel):
    """Un coin du document, en pixels de la photo d'origine."""

    x: float
    y: float


class ScanDetectOut(BaseModel):
    """Cadrage propose par la detection automatique.

    ``detected`` a ``false`` n'est pas une erreur : la photo est exploitable
    telle quelle, et le deposant place les coins lui-meme.
    """

    detected: bool
    corners: list[ScanCorner] | None = None
