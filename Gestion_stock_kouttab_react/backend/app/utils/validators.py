"""Lightweight value validators reusable across the API layer.

These helpers raise :class:`AppException` with a precise :class:`ErrorCode` so the
frontend can react with a localised, contextual message.
"""

from __future__ import annotations

import re

from app.core.errors import ErrorCode
from app.core.exceptions import AppException


_BARCODE_RE = re.compile(r"\d{8,14}")


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


__all__ = ["validate_barcode"]
