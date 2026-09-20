"""Onglet Calendrier : les agendas Google de l'association, en lecture seule.

Rien n'est stocke en base. Google reste la source de verite — l'equipe continue
de saisir ses cours et ses reservations dans Google Agenda, l'application les
montre. Dupliquer les evenements chez nous aurait cree deux verites a tenir.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_roles
from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Admin
from app.schemas.calendar import (
    AgendaOut,
    CalendrierOut,
    EtatCalendrierOut,
    EvenementOut,
)
from app.services import calendrier_instantane
from app.services.google_calendar import (
    agendas_en_cache,
    evenements_en_cache,
    get_google_calendar_client,
    vider_cache,
)


router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = get_logger("calendar")

# L'emploi du temps de l'institut n'est pas une page de consultation ouverte :
# il porte les creneaux de chaque enseignant et les reservations de salles.
# Meme cercle que la buvette — ceux qui organisent, et la comptabilite.
# Doit refleter `ACTIONS.CALENDAR_VIEW` dans `frontend/src/lib/auth.ts`.
_ROLES_LECTURE = ("Super Admin", "AdminBenevoles", "Compta")
_LECTURE = require_roles(*_ROLES_LECTURE)
# Fenetre maximale servie en un appel. Un affichage mensuel en demande cinq
# semaines ; au-dela de l'annee, ce sont 42 agendas multiplies par autant de
# mois, et Google facture ses quotas a la requete.
_FENETRE_MAX_JOURS = 400


def _sur_instantane() -> bool:
    """Vrai quand l'onglet doit servir le relevé figé plutôt que Google.

    L'ordre n'est pas négociable : dès que Google est configuré, c'est Google
    qui parle. Un instantané resté sur le disque ne doit jamais masquer la
    source vivante — il se tairait en silence à chaque horaire corrigé.
    """
    return not settings.google_calendar_configured and calendrier_instantane.disponible()


async def _tous_les_agendas() -> list[dict[str, Any]]:
    if _sur_instantane():
        return calendrier_instantane.agendas()
    return await agendas_en_cache(get_google_calendar_client())


def _agendas_visibles(agendas: list[dict[str, Any]], user: Admin) -> list[dict[str, Any]]:
    """Retire les agendas reserves, sauf pour le Super Admin.

    Le filtrage est fait ICI, pas dans l'interface : masquer une ligne dans un
    menu ne protege rien, l'appel HTTP reste a la portee de n'importe qui.
    """
    if user.role == "Super Admin":
        return agendas
    restreints = set(settings.google_calendar_restricted)
    return [a for a in agendas if a.get("id") not in restreints]


def _en_agenda(brut: dict[str, Any], restreints: set[str]) -> AgendaOut:
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


def _en_evenement(brut: dict[str, Any], agenda: dict[str, Any]) -> EvenementOut | None:
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
        # Un evenement sans titre existe dans Google ; l'afficher vide donnerait
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


@router.get("/agendas", response_model=list[AgendaOut])
async def lister_agendas(user: Admin = Depends(_LECTURE)) -> Any:
    """Les agendas consultables par le compte connecte."""
    agendas = _agendas_visibles(await _tous_les_agendas(), user)
    restreints = set(settings.google_calendar_restricted)
    return sorted(
        (_en_agenda(a, restreints) for a in agendas),
        key=lambda a: a.nom.lower(),
    )


@router.get("", response_model=CalendrierOut)
async def lister_evenements(
    debut: datetime = Query(description="Borne basse, ISO 8601 avec fuseau."),
    fin: datetime = Query(description="Borne haute, ISO 8601 avec fuseau."),
    agendas: list[str] | None = Query(
        default=None,
        description="Identifiants d'agendas. Absent = tous ceux auxquels le compte a droit.",
    ),
    user: Admin = Depends(_LECTURE),
) -> Any:
    """Tous les evenements de la fenetre demandee, tous agendas confondus."""
    if debut.tzinfo is None:
        debut = debut.replace(tzinfo=timezone.utc)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)
    if fin <= debut:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="La fin doit suivre le debut."
        )
    if fin - debut > timedelta(days=_FENETRE_MAX_JOURS):
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"Fenetre limitee a {_FENETRE_MAX_JOURS} jours.",
        )

    autorises = _agendas_visibles(await _tous_les_agendas(), user)
    par_id = {a.get("id"): a for a in autorises}

    if agendas:
        # L'intersection, jamais la liste demandee : sans cela, passer
        # l'identifiant d'un agenda restreint dans l'URL suffirait a le lire.
        demandes = [a for a in agendas if a in par_id]
    else:
        demandes = list(par_id)

    if _sur_instantane():
        brut = calendrier_instantane.evenements(demandes, debut, fin)
        echecs: list[str] = []
    else:
        brut, echecs = await evenements_en_cache(
            get_google_calendar_client(),
            demandes,
            debut,
            fin,
            ttl=settings.google_calendar_cache_seconds,
        )

    evenements: list[EvenementOut] = []
    for calendar_id, items in brut.items():
        agenda = par_id[calendar_id]
        for item in items:
            evenement = _en_evenement(item, agenda)
            if evenement is not None:
                evenements.append(evenement)

    evenements.sort(key=lambda e: e.debut)
    noms_en_erreur = [
        par_id[c].get("summary", c) for c in echecs if c in par_id
    ]
    return CalendrierOut(
        evenements=evenements,
        agendas_en_erreur=noms_en_erreur,
        # L'écran DOIT pouvoir le dire : un planning figé qui se présente comme
        # le direct ferait manquer un cours déplacé.
        instantane=_sur_instantane(),
        genere_le=calendrier_instantane.genere_le() if _sur_instantane() else None,
    )


@router.get(
    "/etat",
    response_model=EtatCalendrierOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
async def etat_calendrier() -> Any:
    """Diagnostic de l'integration.

    « Aucun evenement » et « mal configure » se ressemblent a l'ecran. Sans ce
    signal, il faudrait fouiller les journaux du conteneur pour distinguer les
    deux — le meme constat que pour la sante du circuit d'envoi.
    """
    if not settings.google_calendar_configured:
        return EtatCalendrierOut(
            configure=False,
            instantane=_sur_instantane(),
            genere_le=calendrier_instantane.genere_le() if _sur_instantane() else None,
            nombre_agendas=len(calendrier_instantane.agendas()) or None
            if _sur_instantane()
            else None,
        )
    client = get_google_calendar_client()
    try:
        agendas = await agendas_en_cache(client)
    except AppException as exc:
        return EtatCalendrierOut(
            configure=True,
            compte_impersonne=settings.google_calendar_subject,
            erreur=str(exc.code.value),
        )
    return EtatCalendrierOut(
        configure=True,
        compte_impersonne=settings.google_calendar_subject,
        nombre_agendas=len(agendas),
        agendas_restreints=settings.google_calendar_restricted,
    )


@router.post(
    "/rafraichir",
    response_model=EtatCalendrierOut,
    dependencies=[Depends(require_roles("Super Admin", "AdminBenevoles"))],
)
async def rafraichir() -> Any:
    """Vide le cache memoire.

    Le cache tient quelques minutes : c'est ce qui evite 42 appels par clic.
    Mais quand on vient de corriger un horaire dans Google, attendre sans
    comprendre pourquoi l'ecran ment est plus couteux que le rechargement.
    """
    await vider_cache()
    return await etat_calendrier()
