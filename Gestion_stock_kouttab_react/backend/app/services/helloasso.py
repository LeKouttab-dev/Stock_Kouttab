"""HelloAsso API V5 client (OAuth2 + token refresh + shop / webhook helpers)."""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.core.config import Settings, settings as default_settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger


logger = get_logger("helloasso")


_TOKEN_PATH = "/oauth2/token"
_DEFAULT_TIMEOUT = 15.0
# We refresh slightly before the real expiry to avoid race conditions.
_TOKEN_LEEWAY_SECONDS = 60


class HelloAssoClient:
    """Lightweight synchronous client for HelloAsso API V5.

    The client caches its access/refresh tokens in memory and refreshes them
    automatically. It is meant to be used as a singleton (per process)
    via :func:`get_helloasso_client`.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ token

    def _request_token(self, grant_type: str, **extra: str) -> dict[str, Any]:
        """POST /oauth2/token with the given grant type."""
        client_id = self._settings.helloasso_client_id
        client_secret = self._settings.helloasso_client_secret
        if not client_id or not client_secret:
            logger.error("HelloAsso credentials missing (client_id/client_secret).")
            raise AppException(ErrorCode.HELLOASSO_NOT_CONFIGURED)

        data: dict[str, str] = {
            "grant_type": grant_type,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        data.update(extra)

        url = f"{self._settings.helloasso_api_base.rstrip('/')}{_TOKEN_PATH}"
        try:
            with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                response = client.post(
                    url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as exc:
            logger.exception("HelloAsso token request failed: %s", exc)
            raise AppException(
                ErrorCode.HELLOASSO_AUTH_FAILED,
                extras={"reason": str(exc)},
            ) from exc

        if response.status_code >= 400:
            logger.warning(
                "HelloAsso token request rejected (status=%s body=%s)",
                response.status_code,
                response.text[:500],
            )
            raise AppException(
                ErrorCode.HELLOASSO_AUTH_FAILED,
                extras={"upstream_status": response.status_code},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            logger.exception("HelloAsso token response is not JSON: %s", exc)
            raise AppException(
                ErrorCode.HELLOASSO_AUTH_FAILED,
                detail="Reponse HelloAsso invalide (token non JSON).",
            ) from exc
        return payload

    def _store_token(self, payload: dict[str, Any]) -> str:
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_in = int(payload.get("expires_in", 1799))
        if not access_token:
            logger.error("HelloAsso token payload missing access_token: %s", payload)
            raise AppException(
                ErrorCode.HELLOASSO_AUTH_FAILED,
                detail="Reponse HelloAsso sans access_token.",
            )
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token
        self._expires_at = time.monotonic() + max(expires_in - _TOKEN_LEEWAY_SECONDS, 0)
        logger.info(
            "HelloAsso token acquired/refreshed (expires_in=%ss).", expires_in
        )
        return access_token

    def _ensure_token(self) -> str:
        with self._lock:
            now = time.monotonic()
            if self._access_token and now < self._expires_at:
                return self._access_token
            if self._refresh_token:
                try:
                    payload = self._request_token(
                        "refresh_token", refresh_token=self._refresh_token
                    )
                    return self._store_token(payload)
                except AppException as exc:
                    logger.warning(
                        "HelloAsso refresh failed (%s) — falling back to client_credentials.",
                        exc.message,
                    )
            payload = self._request_token("client_credentials")
            return self._store_token(payload)

    def invalidate_token(self) -> None:
        """Force the next call to acquire a fresh token."""
        with self._lock:
            self._access_token = None
            self._refresh_token = None
            self._expires_at = 0.0

    # ----------------------------------------------------------------- HTTP

    def _full_url(self, path: str) -> str:
        base = self._settings.helloasso_api_base.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}"

    def _headers(self, *, with_auth: bool = True) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if with_auth:
            token = self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        with_auth: bool = True,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        url = self._full_url(path)
        try:
            with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(with_auth=with_auth),
                    json=json,
                    params=params,
                )
        except httpx.HTTPError as exc:
            logger.exception("HelloAsso %s %s failed: %s", method, path, exc)
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                extras={"method": method, "path": path, "reason": str(exc)},
            ) from exc

        if response.status_code == 401 and with_auth and retry_on_401:
            logger.info("HelloAsso responded 401 on %s %s — invalidating token and retrying.", method, path)
            self.invalidate_token()
            return self._request(
                method,
                path,
                with_auth=with_auth,
                json=json,
                params=params,
                retry_on_401=False,
            )
        return response

    def _get(self, path: str, *, with_auth: bool = True) -> dict[str, Any]:
        response = self._request("GET", path, with_auth=with_auth)
        if response.status_code >= 400:
            logger.warning(
                "HelloAsso GET %s failed (status=%s body=%s)",
                path,
                response.status_code,
                response.text[:500],
            )
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                extras={"method": "GET", "path": path, "upstream_status": response.status_code},
            )
        try:
            return response.json()
        except ValueError as exc:
            logger.exception("HelloAsso GET %s returned non-JSON: %s", path, exc)
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                detail=f"Reponse HelloAsso non JSON pour GET {path}.",
            ) from exc

    def _put(self, path: str, *, json: dict[str, Any]) -> dict[str, Any]:
        response = self._request("PUT", path, json=json)
        if response.status_code >= 400:
            logger.warning(
                "HelloAsso PUT %s failed (status=%s body=%s)",
                path,
                response.status_code,
                response.text[:500],
            )
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                extras={"method": "PUT", "path": path, "upstream_status": response.status_code},
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def _delete(self, path: str) -> None:
        response = self._request("DELETE", path)
        if response.status_code >= 400 and response.status_code != 404:
            logger.warning(
                "HelloAsso DELETE %s failed (status=%s body=%s)",
                path,
                response.status_code,
                response.text[:500],
            )
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                extras={"method": "DELETE", "path": path, "upstream_status": response.status_code},
            )

    # ---------------------------------------------------------------- shop

    def list_shop_tiers(self, org_slug: str, form_slug: str) -> list[dict[str, Any]]:
        """Return the tiers (items) of a Shop form.

        HelloAsso V5 requires a Bearer token even on the "/public" endpoint.
        We try /public first (less restrictive privileges) and fall back to
        the regular endpoint. Both can fail with 403 if the OAuth client
        lacks the required privileges in the HelloAsso admin panel.
        """
        public_path = f"/v5/organizations/{org_slug}/forms/Shop/{form_slug}/public"
        private_path = f"/v5/organizations/{org_slug}/forms/Shop/{form_slug}"

        # Try /public first (with auth — HelloAsso V5 requires it).
        response = self._request("GET", public_path, with_auth=True)
        if response.status_code < 400:
            try:
                payload = response.json()
                tiers = payload.get("tiers") or []
                logger.info(
                    "HelloAsso shop tiers (public) fetched: org=%s form=%s count=%d",
                    org_slug,
                    form_slug,
                    len(tiers),
                )
                return tiers
            except ValueError:
                logger.info("HelloAsso /public returned invalid JSON — trying private endpoint.")
        else:
            logger.info(
                "HelloAsso public shop endpoint returned %s — trying private endpoint.",
                response.status_code,
            )

        # Fallback to the private endpoint.
        response = self._request("GET", private_path, with_auth=True)
        if response.status_code == 403:
            body_excerpt = response.text[:200]
            logger.warning(
                "HelloAsso 403 on %s — likely missing OAuth privileges (body=%s)",
                private_path,
                body_excerpt,
            )
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                detail=(
                    "HelloAsso a refuse l'acces (403). Le client OAuth n'a pas les privileges "
                    "suffisants pour lire cette boutique. Va dans ton admin HelloAsso "
                    "(Mon compte > API > tes applications) et active au minimum "
                    "'AccessPublicData' et 'AccessTransactions' sur ton client. Sinon, contacte "
                    "support@helloasso.org pour qu'ils ajoutent ces privileges. "
                    f"Org: {org_slug}, form: {form_slug}."
                ),
                extras={"upstream_status": 403, "org": org_slug, "form": form_slug},
            )
        if response.status_code >= 400:
            logger.warning(
                "HelloAsso GET %s failed (status=%s body=%s)",
                private_path,
                response.status_code,
                response.text[:300],
            )
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                detail=(
                    f"HelloAsso a renvoye {response.status_code} sur la boutique "
                    f"'{form_slug}'. Verifie que le slug est correct et que la boutique est publiee."
                ),
                extras={"upstream_status": response.status_code, "form": form_slug},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                detail=f"HelloAsso a renvoye un contenu invalide pour la boutique '{form_slug}'.",
            ) from exc

        tiers = payload.get("tiers") or []
        logger.info(
            "HelloAsso shop tiers (private) fetched: org=%s form=%s count=%d",
            org_slug,
            form_slug,
            len(tiers),
        )
        return tiers

    # ---------------------------------------------------------------- forms

    def list_organization_forms(
        self,
        org_slug: str,
        *,
        form_types: Sequence[str] = ("Event",),
        states: Sequence[str] = ("Public",),
        page_size: int = 100,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Liste les formulaires d'une organisation (evenements par defaut).

        Sert a proposer au deposant une liste d'evenements fidele aux noms
        publies sur HelloAsso, plutot qu'une saisie libre approximative.

        Privilege OAuth requis : ``AccessPublicData``. Un 403 signifie que le
        client OAuth n'a pas ce privilege — meme diagnostic que pour la boutique.

        La pagination est bornee par ``max_pages`` : une organisation ne devrait
        pas avoir mille formulaires, et une reponse inattendue ne doit pas faire
        boucler le serveur.
        """
        path = f"/v5/organizations/{org_slug}/forms"
        collected: list[dict[str, Any]] = []

        for page_index in range(1, max_pages + 1):
            params: dict[str, Any] = {
                "pageIndex": page_index,
                "pageSize": page_size,
            }
            if form_types:
                params["formTypes"] = list(form_types)
            if states:
                params["states"] = list(states)

            response = self._request("GET", path, params=params)
            if response.status_code == 403:
                logger.warning(
                    "HelloAsso 403 sur %s — privileges OAuth insuffisants.", path
                )
                raise AppException(
                    ErrorCode.HELLOASSO_API_ERROR,
                    detail=(
                        "HelloAsso a refuse l'acces (403). Activez le privilege "
                        "'AccessPublicData' sur votre client OAuth "
                        "(admin HelloAsso > Mon compte > API)."
                    ),
                    extras={"upstream_status": 403, "org": org_slug},
                )
            if response.status_code >= 400:
                logger.warning(
                    "HelloAsso GET %s failed (status=%s body=%s)",
                    path,
                    response.status_code,
                    response.text[:300],
                )
                raise AppException(
                    ErrorCode.HELLOASSO_API_ERROR,
                    detail=(
                        f"HelloAsso a renvoye {response.status_code} lors de la "
                        "recuperation des evenements."
                    ),
                    extras={"upstream_status": response.status_code},
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise AppException(
                    ErrorCode.HELLOASSO_API_ERROR,
                    detail="Reponse HelloAsso invalide (formulaires non JSON).",
                ) from exc

            data = payload.get("data") or []
            if page_index == 1:
                # Le schema de reponse n'est pas documente : on trace le premier
                # element brut pour pouvoir ajuster le mapping sans deviner.
                logger.info(
                    "HelloAsso forms — premier element brut : %s",
                    str(data[0])[:500] if data else "(aucun)",
                )
            collected.extend(data)

            pagination = payload.get("pagination") or {}
            total_pages = pagination.get("totalPages")
            if not data or not total_pages or page_index >= int(total_pages):
                break

        logger.info(
            "HelloAsso forms recuperes : org=%s types=%s count=%d",
            org_slug,
            list(form_types),
            len(collected),
        )
        return collected

    # ---------------------------------------------------------------- hooks

    def register_webhook(self, org_slug: str, url: str) -> dict[str, Any]:
        path = f"/v5/organizations/{org_slug}/notifications"
        logger.info("HelloAsso webhook configure: org=%s url=%s", org_slug, url)
        return self._put(path, json={"url": url})

    def get_webhook(self, org_slug: str) -> dict[str, Any] | None:
        path = f"/v5/organizations/{org_slug}/notifications"
        response = self._request("GET", path)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            logger.warning(
                "HelloAsso GET %s failed (status=%s body=%s)",
                path,
                response.status_code,
                response.text[:500],
            )
            raise AppException(
                ErrorCode.HELLOASSO_API_ERROR,
                extras={"method": "GET", "path": path, "upstream_status": response.status_code},
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def delete_webhook(self, org_slug: str) -> None:
        path = f"/v5/organizations/{org_slug}/notifications"
        logger.info("HelloAsso webhook delete: org=%s", org_slug)
        self._delete(path)


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


_helloasso_singleton: HelloAssoClient | None = None
_singleton_lock = threading.Lock()


def get_helloasso_client(settings: Settings | None = None) -> HelloAssoClient:
    """Return a process-wide :class:`HelloAssoClient`."""
    global _helloasso_singleton
    with _singleton_lock:
        if _helloasso_singleton is None:
            _helloasso_singleton = HelloAssoClient(settings or default_settings)
        return _helloasso_singleton


def reset_helloasso_client() -> None:
    """Reset the singleton (used in tests)."""
    global _helloasso_singleton
    with _singleton_lock:
        _helloasso_singleton = None
