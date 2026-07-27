"""Misc helper utilities."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def mask_rib(rib: str | None) -> str | None:
    """Return a masked RIB suitable for logs/UI when full access is not granted."""
    if not rib:
        return rib
    cleaned = rib.replace(" ", "")
    if len(cleaned) <= 4:
        return "*" * len(cleaned)
    return "*" * (len(cleaned) - 4) + cleaned[-4:]
