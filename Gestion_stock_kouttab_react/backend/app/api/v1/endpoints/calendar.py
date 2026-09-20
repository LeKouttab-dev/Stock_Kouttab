"""Onglet Calendrier : les agendas Google de l'association, en lecture seule.

Rien n'est stocke en base. Google reste la source de verite — l'equipe continue
de saisir ses cours et ses reservations dans Google Agenda, l'application les
montre. Dupliquer les evenements chez nous aurait cree deux verites a tenir.

Le calcul (source, fenetre, normalisation) vit dans `services/calendrier.py` :
l'outil de gestion lit les memes evenements par un autre chemin
(`POST /auth/sso/calendrier`), et deux calculs finiraient par diverger.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_roles
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Admin
from app.schemas.calendar import (
    AgendaOut,
    CalendrierOut,
    EtatCalendrierOut,
)
from app.services import calendrier, calendrier_instantane
from app.services.google_calendar import vider_cache


router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = get_logger("calendar")

# L'emploi du temps de l'institut n'est pas une page de consultation ouverte :
# il porte les creneaux de chaque enseignant et les reservations de salles.
# Meme cercle que la buvette — ceux qui organisent, et la comptabilite.
# Doit refleter `ACTIONS.CALENDAR_VIEW` dans `frontend/src/lib/auth.ts`.
_ROLES_LECTURE = ("Super Admin", "AdminBenevoles", "Compta")
_LECTURE = require_roles(*_ROLES_LECTURE)


def _agendas_visibles(agendas: list[dict[str, Any]], user: Admin) -> list[dict[str, Any]]:
    """Retire les agendas reserves, sauf pour le Super Admin.

    Le filtrage est fait ICI, pas dans l'interface : masquer une ligne dans un
    menu ne protege rien, l'appel HTTP reste a la portee de n'importe qui.
    """
    if user.role == "Super Admin":
        return agendas
    return calendrier.sans_les_restreints(agendas)


@router.get("/agendas", response_model=list[AgendaOut])
async def lister_agendas(user: Admin = Depends(_LECTURE)) -> Any:
    """Les agendas consultables par le compte connecte."""
    agendas = _agendas_visibles(await calendrier.tous_les_agendas(), user)
    restreints = set(settings.google_calendar_restricted)
    return sorted(
        (calendrier.en_agenda(a, restreints) for a in agendas),
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
    debut, fin = calendrier.borner_fenetre(debut, fin)
    autorises = _agendas_visibles(await calendrier.tous_les_agendas(), user)
    evenements, noms_en_erreur = await calendrier.evenements_de(
        autorises, debut, fin, agendas
    )
    fige = calendrier.sur_instantane()
    return CalendrierOut(
        evenements=evenements,
        agendas_en_erreur=noms_en_erreur,
        # L'écran DOIT pouvoir le dire : un planning figé qui se présente comme
        # le direct ferait manquer un cours déplacé.
        instantane=fige,
        genere_le=calendrier_instantane.genere_le() if fige else None,
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
        fige = calendrier.sur_instantane()
        return EtatCalendrierOut(
            configure=False,
            instantane=fige,
            genere_le=calendrier_instantane.genere_le() if fige else None,
            nombre_agendas=(len(calendrier_instantane.agendas()) or None) if fige else None,
        )
    try:
        # La meme porte que le reste de l'onglet : un diagnostic qui
        # interrogerait Google autrement pourrait se declarer sain alors que
        # l'ecran, lui, echoue.
        agendas = await calendrier.tous_les_agendas()
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
