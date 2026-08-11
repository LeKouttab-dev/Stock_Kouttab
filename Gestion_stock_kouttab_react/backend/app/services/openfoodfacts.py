"""OpenFoodFacts public API client (best-effort barcode lookup).

OpenFoodFacts is a free, anonymous, community-maintained product database. It
is used here as a *nice-to-have* when scanning a barcode in the buvette/stock
UI: if the product is known, we pre-fill the form (name, brand, image). If
the API is down or the product is unknown, the user can always type the
information manually — so this service must **never** raise to the caller.

A small in-memory TTL cache (1 hour) keeps repeated scans cheap and avoids
hammering OpenFoodFacts when several teammates scan the same item in a row.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from app.core.logger import get_logger


logger = get_logger("openfoodfacts")


_BASE_URL = "https://world.openfoodfacts.org/api/v2/product"
_FIELDS = (
    "product_name,product_name_fr,brands,image_front_small_url,"
    "image_url,quantity,categories_tags"
)
_TIMEOUT_SECONDS = 5.0
_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
_USER_AGENT = "KouttabStock/1.0 (https://stock.lekouttab.fr)"


# ---------------------------------------------------------------------------
# Tiny TTL cache (process-wide). Bounded by use-case (barcodes are short).
# ---------------------------------------------------------------------------


class _TTLCache:
    """Naive thread-safe TTL cache."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, dict[str, Any] | None]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[bool, dict[str, Any] | None]:
        """Return ``(hit, value)``. ``hit`` is False when expired/missing."""
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False, None
            expires_at, value = entry
            if expires_at < now:
                self._data.pop(key, None)
                return False, None
            return True, value

    def set(self, key: str, value: dict[str, Any] | None) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = _TTLCache(_CACHE_TTL_SECONDS)


def reset_cache() -> None:
    """Clear the in-memory cache (used in tests)."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _normalise_product(raw_product: dict[str, Any] | None) -> dict[str, Any] | None:
    """Map the raw OpenFoodFacts ``product`` object to our local shape."""
    if not raw_product:
        return None

    name_fr = raw_product.get("product_name_fr")
    name = name_fr or raw_product.get("product_name") or None
    image_url = (
        raw_product.get("image_front_small_url")
        or raw_product.get("image_url")
        or None
    )
    categories_raw = raw_product.get("categories_tags") or []
    if not isinstance(categories_raw, list):
        categories_raw = []
    categories = [c for c in categories_raw if isinstance(c, str)]
    return {
        "name": name,
        "brand": raw_product.get("brands") or None,
        "image_url": image_url,
        "quantity": raw_product.get("quantity") or None,
        "categories": categories,
    }


def lookup_barcode(barcode: str) -> dict[str, Any] | None:
    """Fetch product information from OpenFoodFacts for the given barcode.

    Returns ``{name, brand, image_url, quantity, categories}`` if the barcode
    is known by OpenFoodFacts, or ``None`` when it is unknown / the service
    is unreachable. **Never raises** — failures are logged and treated as a
    miss so the caller can still let the user create the product manually.
    """
    if not barcode:
        return None
    key = barcode.strip()
    if not key:
        return None

    hit, cached = _cache.get(key)
    if hit:
        return cached

    url = f"{_BASE_URL}/{key}.json"
    params = {"fields": _FIELDS}
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        logger.info("OpenFoodFacts lookup failed (network) for %s: %s", key, exc)
        # Do NOT cache failures — we want to retry next time.
        return None

    if response.status_code >= 400:
        logger.info(
            "OpenFoodFacts returned %s for %s — treating as miss.",
            response.status_code,
            key,
        )
        # 404 is a legitimate miss → cache it so we don't keep asking.
        if response.status_code == 404:
            _cache.set(key, None)
        return None

    try:
        payload = response.json()
    except ValueError as exc:
        logger.info("OpenFoodFacts non-JSON response for %s: %s", key, exc)
        return None

    status = payload.get("status")
    # OpenFoodFacts uses status: 1 = found, 0 = not found.
    if status == 0 or status == "0":
        _cache.set(key, None)
        return None

    normalised = _normalise_product(payload.get("product"))
    if normalised is None or not normalised.get("name"):
        # No usable info → still cache the miss to avoid spamming the API.
        _cache.set(key, None)
        return None

    _cache.set(key, normalised)
    return normalised


__all__ = ["lookup_barcode", "reset_cache"]
