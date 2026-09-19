"""Lecture des agendas Google de l'association (compte de service, LECTURE SEULE).

Pourquoi un compte de service et non des adresses iCal secretes : l'association
tient une quarantaine d'agendas, un par cours, et en cree de nouveaux a chaque
rentree. Une adresse secrete par agenda aurait impose une recopie manuelle a
chaque creation ; le compte de service voit ce que voit le compte Workspace
qu'il impersonne, et les nouveaux agendas apparaissent d'eux-memes.

Pourquoi pas la bibliotheque ``google-auth`` : elle tire ``requests``, alors que
tout le projet parle HTTP avec ``httpx``. Le flux JWT-bearer d'un compte de
service tient en une signature RS256 et un POST, et ``python-jose`` +
``cryptography`` sont deja la pour les JWT de l'application.

Le jeton demande le SEUL scope ``calendar.readonly`` : la delegation a l'echelle
du domaine donne acces a tout ce que voit le compte impersonne, l'ecriture
comprise si on l'accorde. L'application ne fait que lire, le scope le dit.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import httpx
from jose import jwt

from app.core.config import Settings, settings as default_settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger


logger = get_logger("google_calendar")

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_BASE = "https://www.googleapis.com/calendar/v3"
_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
_TIMEOUT = 20.0
# On renouvelle le jeton un peu avant l'expiration reelle : une requete partie
# a la seconde pres reviendrait en 401.
_TOKEN_LEEWAY_SECONDS = 60
# Google plafonne a 2500 evenements par page.
_PAGE_SIZE = 2500
# Nombre d'agendas interroges en parallele. Au-dela, Google rend des 403
# « rateLimitExceeded » : la lenteur d'un affichage vaut mieux qu'une page
# a moitie vide.
_CONCURRENCE = 8


class GoogleCalendarClient:
    """Client minimal de l'API Google Calendar v3, en lecture seule.

    Le jeton est mis en cache en memoire pour la duree de vie du processus ;
    il vaut une heure, et chaque affichage de l'onglet declenche autant
    d'appels qu'il y a d'agendas.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ credentials

    def _compte_de_service(self) -> dict[str, Any]:
        """Charge la cle du compte de service (JSON brut, base64, ou fichier)."""
        brut = self._settings.google_service_account_json.strip()
        if not brut and self._settings.google_service_account_file.strip():
            chemin = Path(self._settings.google_service_account_file.strip())
            try:
                brut = chemin.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error("Cle du compte de service illisible (%s) : %s", chemin, exc)
                raise AppException(ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED) from exc

        if not brut or not self._settings.google_calendar_subject.strip():
            raise AppException(ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED)

        # Le JSON d'un compte de service contient des sauts de ligne dans la
        # cle privee : colle tel quel dans un .env, il casse le fichier. La
        # variante base64 est donc acceptee, et c'est celle qu'on documente.
        if not brut.lstrip().startswith("{"):
            try:
                brut = base64.b64decode(brut, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
                logger.error("GOOGLE_SERVICE_ACCOUNT_JSON n'est ni du JSON ni du base64.")
                raise AppException(ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED) from exc

        try:
            infos = json.loads(brut)
        except ValueError as exc:
            logger.error("Cle du compte de service invalide (JSON illisible).")
            raise AppException(ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED) from exc

        if not infos.get("client_email") or not infos.get("private_key"):
            logger.error("Cle du compte de service incomplete (client_email/private_key).")
            raise AppException(ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED)
        return infos

    async def _jeton(self) -> str:
        async with self._lock:
            maintenant = time.monotonic()
            if self._token and maintenant < self._token_expires_at:
                return self._token

            infos = self._compte_de_service()
            emis_a = int(time.time())
            assertion = jwt.encode(
                {
                    "iss": infos["client_email"],
                    "scope": _SCOPE,
                    "aud": _TOKEN_URL,
                    "iat": emis_a,
                    "exp": emis_a + 3600,
                    # Delegation a l'echelle du domaine : le compte de service
                    # agit AU NOM de ce compte Workspace. Sans `sub`, il n'a
                    # que ses propres agendas, c'est-a-dire aucun.
                    "sub": self._settings.google_calendar_subject.strip(),
                },
                infos["private_key"],
                algorithm="RS256",
                headers={"kid": infos["private_key_id"]} if infos.get("private_key_id") else None,
            )

            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    reponse = await client.post(
                        _TOKEN_URL,
                        data={
                            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                            "assertion": assertion,
                        },
                    )
            except httpx.HTTPError as exc:
                logger.exception("Jeton Google inaccessible : %s", exc)
                raise AppException(
                    ErrorCode.GOOGLE_CALENDAR_AUTH_FAILED, extras={"reason": str(exc)}
                ) from exc

            if reponse.status_code >= 400:
                # Le corps porte le vrai diagnostic (`unauthorized_client` =
                # delegation non accordee dans la console d'administration).
                logger.error(
                    "Jeton Google refuse (status=%s body=%s)",
                    reponse.status_code,
                    reponse.text[:500],
                )
                raise AppException(
                    ErrorCode.GOOGLE_CALENDAR_AUTH_FAILED,
                    extras={"upstream_status": reponse.status_code},
                )

            charge = reponse.json()
            jeton = charge.get("access_token")
            if not jeton:
                raise AppException(ErrorCode.GOOGLE_CALENDAR_AUTH_FAILED)
            duree = int(charge.get("expires_in", 3600))
            self._token = jeton
            self._token_expires_at = time.monotonic() + max(duree - _TOKEN_LEEWAY_SECONDS, 0)
            logger.info("Jeton Google Agenda obtenu (expires_in=%ss).", duree)
            return jeton

    # ------------------------------------------------------------------ appels

    async def _get(
        self, client: httpx.AsyncClient, chemin: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        jeton = await self._jeton()
        try:
            reponse = await client.get(
                f"{_API_BASE}{chemin}",
                params=params,
                headers={"Authorization": f"Bearer {jeton}"},
            )
        except httpx.HTTPError as exc:
            logger.warning("Appel Google Agenda echoue (%s) : %s", chemin, exc)
            raise AppException(
                ErrorCode.GOOGLE_CALENDAR_API_ERROR, extras={"reason": str(exc)}
            ) from exc

        if reponse.status_code >= 400:
            logger.warning(
                "Google Agenda a refuse %s (status=%s body=%s)",
                chemin,
                reponse.status_code,
                reponse.text[:300],
            )
            raise AppException(
                ErrorCode.GOOGLE_CALENDAR_API_ERROR,
                extras={"upstream_status": reponse.status_code},
            )
        return reponse.json()

    async def lister_agendas(self) -> list[dict[str, Any]]:
        """Tous les agendas visibles par le compte impersonne."""
        agendas: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            page: str | None = None
            while True:
                params: dict[str, Any] = {"maxResults": 250, "showHidden": True}
                if page:
                    params["pageToken"] = page
                charge = await self._get(client, "/users/me/calendarList", params)
                agendas.extend(charge.get("items", []))
                page = charge.get("nextPageToken")
                if not page:
                    break
        return agendas

    async def lister_evenements(
        self, calendar_id: str, debut: datetime, fin: datetime
    ) -> list[dict[str, Any]]:
        """Evenements d'un agenda sur une fenetre, recurrences developpees."""
        evenements: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            page: str | None = None
            while True:
                params: dict[str, Any] = {
                    # `singleEvents` developpe les recurrences en occurrences
                    # datees : sans lui, un cours hebdomadaire n'arriverait
                    # qu'une fois, avec sa regle RRULE a interpreter nous-memes.
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": _PAGE_SIZE,
                    "timeMin": _iso(debut),
                    "timeMax": _iso(fin),
                }
                if page:
                    params["pageToken"] = page
                # L'identifiant d'un agenda est une adresse (« ...@group.calendar.
                # google.com ») : sans encodage, le « @ » et les « . » sortiraient
                # du segment de chemin.
                charge = await self._get(
                    client, f"/calendars/{quote(calendar_id, safe='')}/events", params
                )
                evenements.extend(charge.get("items", []))
                page = charge.get("nextPageToken")
                if not page:
                    break
        return evenements


def _iso(moment: datetime) -> str:
    """Horodatage RFC 3339 accepte par Google (jamais de date naive)."""
    if moment.tzinfo is None:
        raise ValueError("timeMin/timeMax doivent porter un fuseau.")
    return moment.isoformat()


_client: GoogleCalendarClient | None = None


def get_google_calendar_client(settings: Settings | None = None) -> GoogleCalendarClient:
    """Client partage par le processus (le jeton se garde une heure)."""
    global _client
    if settings is not None:
        return GoogleCalendarClient(settings)
    if _client is None:
        _client = GoogleCalendarClient(default_settings)
    return _client


# --------------------------------------------------------------------- cache

class _Cache:
    """Cache memoire a duree de vie, par cle.

    42 agendas font 42 appels HTTP par fenetre affichee. Sans cache, un
    utilisateur qui feuillette les mois epuiserait le quota Google et
    attendrait quelques secondes a chaque clic.
    """

    def __init__(self) -> None:
        self._valeurs: dict[Any, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def obtenir(self, cle: Any, ttl: int) -> Any | None:
        async with self._lock:
            entree = self._valeurs.get(cle)
            if entree is None:
                return None
            pose_a, valeur = entree
            if time.monotonic() - pose_a > ttl:
                self._valeurs.pop(cle, None)
                return None
            return valeur

    async def poser(self, cle: Any, valeur: Any) -> None:
        async with self._lock:
            # Garde-fou memoire : la fenetre glisse au fil des mois consultes,
            # les vieilles cles ne seraient jamais relues.
            if len(self._valeurs) > 500:
                self._valeurs.clear()
            self._valeurs[cle] = (time.monotonic(), valeur)

    async def vider(self) -> None:
        async with self._lock:
            self._valeurs.clear()


_cache = _Cache()


async def agendas_en_cache(client: GoogleCalendarClient, ttl: int = 600) -> list[dict[str, Any]]:
    cache = await _cache.obtenir("agendas", ttl)
    if cache is not None:
        return cache
    agendas = await client.lister_agendas()
    await _cache.poser("agendas", agendas)
    return agendas


async def evenements_en_cache(
    client: GoogleCalendarClient,
    calendar_ids: Iterable[str],
    debut: datetime,
    fin: datetime,
    ttl: int,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Evenements de plusieurs agendas, en parallele.

    Rend aussi la liste des agendas qui ont echoue : un agenda supprime ou
    devenu inaccessible ne doit pas vider la page des quarante autres.
    """
    resultats: dict[str, list[dict[str, Any]]] = {}
    echecs: list[str] = []
    semaphore = asyncio.Semaphore(_CONCURRENCE)

    async def _un(calendar_id: str) -> None:
        cle = (calendar_id, debut.isoformat(), fin.isoformat())
        cache = await _cache.obtenir(cle, ttl)
        if cache is not None:
            resultats[calendar_id] = cache
            return
        async with semaphore:
            try:
                evenements = await client.lister_evenements(calendar_id, debut, fin)
            except AppException as exc:
                logger.warning("Agenda %s illisible : %s", calendar_id, exc)
                echecs.append(calendar_id)
                return
        await _cache.poser(cle, evenements)
        resultats[calendar_id] = evenements

    await asyncio.gather(*(_un(c) for c in calendar_ids))
    return resultats, echecs


async def vider_cache() -> None:
    await _cache.vider()


__all__ = [
    "GoogleCalendarClient",
    "agendas_en_cache",
    "evenements_en_cache",
    "get_google_calendar_client",
    "vider_cache",
]
