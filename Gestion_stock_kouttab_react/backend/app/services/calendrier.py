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

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.schemas.calendar import AgendaOut, EvenementOut
from app.services import calendrier_instantane, calendrier_salles
from app.services.calendrier_salles import ReglageAgenda
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


def _rang_categorie(categorie: str) -> int:
    """Les categories connues dans leur ordre, les saisies ensuite, « Autres » a la fin."""
    ordre = calendrier_salles.ORDRE_CATEGORIES
    if categorie == "Autres":
        return len(ordre) + 1
    return ordre.index(categorie) if categorie in ordre else len(ordre)


def en_agenda(
    brut: dict[str, Any],
    restreints: set[str],
    reglages: Mapping[str, ReglageAgenda] | None = None,
) -> AgendaOut:
    identifiant = brut.get("id", "")
    nom = brut.get("summaryOverride") or brut.get("summary") or identifiant
    reglage = (reglages or {}).get(identifiant) or ReglageAgenda()
    categorie_calculee, sous_categorie_calculee = calendrier_salles.categorie_de(nom)
    categorie = reglage.categorie or categorie_calculee
    return AgendaOut(
        id=identifiant,
        nom=nom,
        description=brut.get("description"),
        couleur=brut.get("backgroundColor"),
        couleur_texte=brut.get("foregroundColor"),
        fuseau=brut.get("timeZone"),
        restreint=identifiant in restreints,
        # Le libelle saisi l'emporte sur la regle : c'est tout son objet.
        nom_court=reglage.nom_court or calendrier_salles.nom_court(nom),
        enseignant=calendrier_salles.enseignant_de(nom),
        salle_par_defaut=reglage.salle,
        # Saisi dans les reglages, sinon deduit du nom. La sous-categorie
        # saisie ne vaut qu'avec sa categorie : seule, elle rangerait l'agenda
        # sous une branche qui n'est pas la sienne.
        categorie=categorie,
        categorie_rang=_rang_categorie(categorie),
        sous_categorie=(
            reglage.sous_categorie
            if reglage.categorie or reglage.sous_categorie
            else sous_categorie_calculee
        ),
    )


def en_evenement(
    brut: dict[str, Any],
    agenda: dict[str, Any],
    reglages: Mapping[str, ReglageAgenda] | None = None,
) -> EvenementOut | None:
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

    agenda_id = agenda.get("id", "")
    agenda_nom = agenda.get("summaryOverride") or agenda.get("summary") or ""
    reglage = (reglages or {}).get(agenda_id) or ReglageAgenda()

    # L'ordre decide de ce que l'ecran affiche comme certain. Une salle
    # reservee dans Google est un fait ; la salle habituelle de l'agenda est
    # une habitude ; la salle par defaut n'est rien de plus qu'une place dans
    # la grille. On sert les trois, en disant toujours laquelle c'est.
    salle = calendrier_salles.salle_reservee(brut)
    salle_source = "google" if salle else None
    # Une valeur stockee hors referentiel (l'ancienne colonne « autre ») ne
    # doit pas creer de colonne fantome : elle vaut absence de reglage.
    if salle is None and reglage.salle in calendrier_salles.SALLES:
        salle, salle_source = reglage.salle, "correspondance"
    if salle is None:
        salle, salle_source = calendrier_salles.SALLE_PAR_DEFAUT, "defaut"

    return EvenementOut(
        id=brut.get("id", ""),
        agenda_id=agenda_id,
        agenda_nom=agenda_nom,
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
        salle=salle,
        salle_source=salle_source,
        salle_libelle=calendrier_salles.SALLES.get(salle) if salle else None,
        numero=calendrier_salles.numero_de(brut),
        enseignant=calendrier_salles.enseignant_de(agenda_nom),
        nom_court=reglage.nom_court or calendrier_salles.nom_court(agenda_nom),
    )


async def evenements_de(
    agendas_autorises: list[dict[str, Any]],
    debut: datetime,
    fin: datetime,
    demandes: list[str] | None = None,
    reglages: Mapping[str, ReglageAgenda] | None = None,
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
            evenement = en_evenement(item, agenda, reglages)
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
