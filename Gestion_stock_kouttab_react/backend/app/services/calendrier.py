"""Le calendrier, sans l'HTTP : choix de la source, fenêtre, normalisation.

Deux entrées mènent ici — l'onglet de l'application (`endpoints/calendar.py`) et
le pont vers l'outil de gestion (`POST /auth/sso/calendrier`). Elles n'ont ni le
même contrôle d'accès ni le même public, mais **elles doivent voir exactement
les mêmes événements** : deux chemins de lecture finiraient par répondre
différemment à la même question, et personne ne saurait lequel croire.

Ce qui reste hors d'ici, à dessein : *qui* a le droit de demander. Ce n'est pas
la même règle des deux côtés — un rôle de l'application d'un côté, la confiance
accordée à l'outil de gestion de l'autre — et la mélanger au calcul rendrait
l'une des deux invisible.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.schemas.calendar import AgendaOut, EvenementOut
from app.services import calendrier_instantane
from app.services.google_calendar import (
    agendas_en_cache,
    evenements_en_cache,
    get_google_calendar_client,
)


# Fenêtre maximale servie en un appel. Un affichage mensuel en demande cinq
# semaines ; au-delà de l'année, ce sont 42 agendas multipliés par autant de
# mois, et Google facture ses quotas à la requête.
FENETRE_MAX_JOURS = 400


def sur_instantane() -> bool:
    """Vrai quand il faut servir le relevé figé plutôt que Google.

    L'ordre n'est pas négociable : dès que Google est configuré, c'est Google
    qui parle. Un instantané resté sur le disque ne doit jamais masquer la
    source vivante — il se tairait en silence à chaque horaire corrigé.
    """
    return not settings.google_calendar_configured and calendrier_instantane.disponible()


async def tous_les_agendas() -> list[dict[str, Any]]:
    """Les agendas bruts de la source active, au format `calendarList` de Google."""
    if sur_instantane():
        return calendrier_instantane.agendas()
    return await agendas_en_cache(get_google_calendar_client())


def sans_les_restreints(agendas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retire les agendas réservés (`GOOGLE_CALENDAR_RESTRICTED`)."""
    restreints = set(settings.google_calendar_restricted)
    return [a for a in agendas if a.get("id") not in restreints]


def borner_fenetre(debut: datetime, fin: datetime) -> tuple[datetime, datetime]:
    """Complète les fuseaux manquants et refuse les fenêtres absurdes ou énormes."""
    if debut.tzinfo is None:
        debut = debut.replace(tzinfo=timezone.utc)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)
    if fin <= debut:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="La fin doit suivre le debut.")
    if fin - debut > timedelta(days=FENETRE_MAX_JOURS):
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"Fenetre limitee a {FENETRE_MAX_JOURS} jours.",
        )
    return debut, fin


def en_agenda(brut: dict[str, Any], restreints: set[str]) -> AgendaOut:
    identifiant = brut.get("id", "")
    return AgendaOut(
        id=identifiant,
        nom=brut.get("summaryOverride") or brut.get("summary") or identifiant,
        description=brut.get("description"),
        couleur=brut.get("backgroundColor"),
        couleur_texte=brut.get("foregroundColor"),
        fuseau=brut.get("timeZone"),
        restreint=identifiant in restreints,
    )


def en_evenement(brut: dict[str, Any], agenda: dict[str, Any]) -> EvenementOut | None:
    debut_brut = brut.get("start") or {}
    fin_brut = brut.get("end") or {}
    # Une occurrence sans date n'est pas affichable ; elle ne devrait pas
    # arriver avec `singleEvents`, mais une liste vide vaut mieux qu'un 500.
    debut = debut_brut.get("dateTime") or debut_brut.get("date")
    fin = fin_brut.get("dateTime") or fin_brut.get("date") or debut
    if not debut:
        return None

    organisateur = (brut.get("organizer") or {}).get("displayName") or (
        brut.get("organizer") or {}
    ).get("email")

    return EvenementOut(
        id=brut.get("id", ""),
        agenda_id=agenda.get("id", ""),
        agenda_nom=agenda.get("summaryOverride") or agenda.get("summary") or "",
        # Un événement sans titre existe dans Google ; l'afficher vide donnerait
        # une pastille muette dans la grille.
        titre=brut.get("summary") or "(Sans titre)",
        debut=debut,
        fin=fin,
        journee_entiere="date" in debut_brut,
        lieu=brut.get("location"),
        description=brut.get("description"),
        organisateur=organisateur,
        couleur=agenda.get("backgroundColor"),
        lien=brut.get("htmlLink"),
        statut=brut.get("status"),
        recurrent=bool(brut.get("recurringEventId")),
    )


async def evenements_de(
    agendas_autorises: list[dict[str, Any]],
    debut: datetime,
    fin: datetime,
    demandes: list[str] | None = None,
) -> tuple[list[EvenementOut], list[str]]:
    """Les événements des agendas autorisés, triés, et les agendas en échec.

    `demandes` est croisé avec les agendas autorisés, **jamais** servi tel
    quel : sans cette intersection, passer l'identifiant d'un agenda réservé
    dans l'URL suffirait à le lire.
    """
    par_id = {a.get("id"): a for a in agendas_autorises}
    cibles = [a for a in demandes if a in par_id] if demandes else list(par_id)

    if sur_instantane():
        brut = calendrier_instantane.evenements(cibles, debut, fin)
        echecs: list[str] = []
    else:
        brut, echecs = await evenements_en_cache(
            get_google_calendar_client(),
            cibles,
            debut,
            fin,
            ttl=settings.google_calendar_cache_seconds,
        )

    evenements: list[EvenementOut] = []
    for calendar_id, items in brut.items():
        agenda = par_id[calendar_id]
        for item in items:
            evenement = en_evenement(item, agenda)
            if evenement is not None:
                evenements.append(evenement)

    evenements.sort(key=lambda e: e.debut)
    noms_en_erreur = [par_id[c].get("summary", c) for c in echecs if c in par_id]
    return evenements, noms_en_erreur


__all__ = [
    "FENETRE_MAX_JOURS",
    "borner_fenetre",
    "en_agenda",
    "en_evenement",
    "evenements_de",
    "sans_les_restreints",
    "sur_instantane",
    "tous_les_agendas",
]
