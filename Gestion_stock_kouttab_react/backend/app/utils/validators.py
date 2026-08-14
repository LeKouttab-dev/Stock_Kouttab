"""Lightweight value validators reusable across the API layer.

These helpers raise :class:`AppException` with a precise :class:`ErrorCode` so the
frontend can react with a localised, contextual message.
"""

from __future__ import annotations

import re

from app.core.errors import ErrorCode
from app.core.exceptions import AppException


_BARCODE_RE = re.compile(r"\d{8,14}")

# Longueur alignee sur `Stock.image_url` / `BuvetteProducts.image_url`.
_IMAGE_URL_MAX = 500


def validate_barcode(barcode: str | None) -> str | None:
    """Normalise and validate a product barcode.

    Returns ``None`` when the input is ``None`` or empty (barcode is optional).
    Raises :class:`AppException` (``BARCODE_INVALID``) when the value does not
    match the expected pattern (``8`` to ``14`` digits — covers EAN-8, UPC-A,
    EAN-13 and ITF-14).
    """
    if barcode is None:
        return None
    cleaned = barcode.strip()
    if not cleaned:
        return None
    if not _BARCODE_RE.fullmatch(cleaned):
        raise AppException(ErrorCode.BARCODE_INVALID)
    return cleaned


def validate_image_url(url: str | None) -> str | None:
    """Normalise et controle l'adresse d'une photo de produit.

    Rend ``None`` pour une valeur vide : la photo est facultative, l'emoji sert
    de repli.

    **Seul `https://` est accepte.** L'adresse est rendue telle quelle dans un
    `<img src>` : `data:` y ferait passer une image entiere par ce champ de 500
    caracteres, et `http://` afficherait un avertissement de contenu mixte sur
    un site servi en HTTPS — la photo ne s'afficherait pas, sans explication.

    Aucun domaine n'est impose. Les photos viennent d'OpenFoodFacts
    aujourd'hui, de HelloAsso pour la buvette, et rien ne dit qu'une troisieme
    source ne s'ajoutera pas.
    """
    if url is None:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    if not cleaned.lower().startswith("https://"):
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="L'adresse de la photo doit commencer par https://.",
        )
    if len(cleaned) > _IMAGE_URL_MAX:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"L'adresse de la photo depasse {_IMAGE_URL_MAX} caracteres.",
        )
    return cleaned


__all__ = ["validate_barcode", "validate_image_url"]
