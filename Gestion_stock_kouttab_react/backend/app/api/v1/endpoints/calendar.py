"""Onglet Calendrier : les agendas Google de l'association, en lecture seule.

Rien n'est stocke en base. Google reste la source de verite — l'equipe continue
de saisir ses cours et ses reservations dans Google Agenda, l'application les
montre. Dupliquer les evenements chez nous aurait cree deux verites a tenir.

Le calcul (source, fenetre, normalisation) vit dans `services/calendrier.py` :
l'outil de gestion lit les memes evenements par un autre chemin
(`POST /auth/sso/calendrier`), et deux calculs finiraient par diverger.
"""

from __future__ import annotations

import collections
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.crud import calendrier as crud_calendrier
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.calendar import (
    AgendaOut,
    CalendrierOut,
    EtatCalendrierOut,
    ReglageAgendaOut,
    ReglagesAgendasIn,
    ReglagesAgendasOut,
    SalleDeduiteOut,
)
from app.services import calendrier, calendrier_instantane, calendrier_salles
from app.services.google_calendar import vider_cache

router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = get_logger("calendar")

# L'emploi du temps de l'institut n'est pas une page de consultation ouverte :
# il porte les creneaux de chaque enseignant et les reservations de salles.
# Meme cercle que la buvette — ceux qui organisent, et la comptabilite.
# Doit refleter `ACTIONS.CALENDAR_VIEW` dans `frontend/src/lib/auth.ts`.
_ROLES_LECTURE = ("Super Admin", "AdminBenevoles", "Compta")
_LECTURE = require_roles(*_ROLES_LECTURE)

# Ranger les agendas dans les salles decide de ce que TOUT le monde lit comme
# emploi du temps. Meme cercle que les agendas reserves : le Super Admin seul.
# Doit refleter `ACTIONS.CALENDAR_ROOMS_MANAGE` dans `frontend/src/lib/auth.ts`.
_REGLAGES = require_roles("Super Admin")


def _agendas_visibles(agendas: list[dict[str, Any]], user: Admin) -> list[dict[str, Any]]:
    """Retire les agendas reserves, sauf pour le Super Admin.

    Le filtrage est fait ICI, pas dans l'interface : masquer une ligne dans un
    menu ne protege rien, l'appel HTTP reste a la portee de n'importe qui.
    """
    if user.role == "Super Admin":
        return agendas
    return calendrier.sans_les_restreints(agendas)


@router.get("/agendas", response_model=list[AgendaOut])
async def lister_agendas(user: Admin = Depends(_LECTURE), db: Session = Depends(get_db)) -> Any:
    """Les agendas consultables par le compte connecte."""
    agendas = _agendas_visibles(await calendrier.tous_les_agendas(), user)
    restreints = set(settings.google_calendar_restricted)
    reglages = crud_calendrier.reglages_par_agenda(db)
    return sorted(
        (calendrier.en_agenda(a, restreints, reglages) for a in agendas),
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
    db: Session = Depends(get_db),
) -> Any:
    """Tous les evenements de la fenetre demandee, tous agendas confondus."""
    debut, fin = calendrier.borner_fenetre(debut, fin)
    autorises = _agendas_visibles(await calendrier.tous_les_agendas(), user)
    reglages = crud_calendrier.reglages_par_agenda(db)
    evenements, noms_en_erreur = await calendrier.evenements_de(
        autorises, debut, fin, agendas, reglages
    )
    fige = calendrier.sur_instantane()
    return CalendrierOut(
        evenements=evenements,
        agendas_en_erreur=noms_en_erreur,
        # L'écran DOIT pouvoir le dire : un planning figé qui se présente comme
        # le direct ferait manquer un cours déplacé.
        instantane=fige,
        genere_le=calendrier_instantane.genere_le() if fige else None,
        salles=dict(calendrier_salles.SALLES),
    )


def _en_reglages(reglages: dict[str, Any]) -> ReglagesAgendasOut:
    return ReglagesAgendasOut(
        reglages=sorted(
            (
                ReglageAgendaOut(agenda_id=aid, salle=r.salle, nom_court=r.nom_court)
                for aid, r in reglages.items()
            ),
            key=lambda r: r.agenda_id,
        ),
        salles=dict(calendrier_salles.SALLES),
    )


@router.get("/reglages-agendas", response_model=ReglagesAgendasOut)
async def lire_reglages_agendas(
    _: Admin = Depends(_REGLAGES), db: Session = Depends(get_db)
) -> Any:
    """Les salles habituelles et noms courts deja saisis."""
    return _en_reglages(crud_calendrier.reglages_par_agenda(db))


@router.put("/reglages-agendas", response_model=ReglagesAgendasOut)
async def enregistrer_reglages_agendas(
    corps: ReglagesAgendasIn = Body(),
    user: Admin = Depends(_REGLAGES),
    db: Session = Depends(get_db),
) -> Any:
    """Enregistre un lot de reglages.

    En lot, et non une route par agenda : l'ecran est un tableau de quarante-
    cinq lignes, le geste naturel est « j'en regle dix, j'enregistre », et dix
    requetes vers une base distante coutent dix allers-retours.

    Ce qui n'est pas envoye n'est pas touche ; `null` efface.
    """
    noms = {}
    try:
        noms = {
            a.get("id"): (a.get("summaryOverride") or a.get("summary") or "")
            for a in await calendrier.tous_les_agendas()
        }
    except AppException:
        # Google injoignable ne doit pas empecher d'enregistrer un reglage :
        # le nom n'est qu'un confort de relecture.
        logger.warning("Noms d'agendas indisponibles a l'enregistrement des reglages.")

    reglages = crud_calendrier.enregistrer_reglages(
        db,
        {aid: champs.model_dump() for aid, champs in corps.reglages.items()},
        auteur=user.full_name,
        noms_agendas=noms,
    )
    return _en_reglages(reglages)


@router.get("/reglages-agendas/deduire", response_model=list[SalleDeduiteOut])
async def deduire_les_salles(
    jours: int = Query(default=60, ge=7, le=365),
    user: Admin = Depends(_REGLAGES),
    db: Session = Depends(get_db),
) -> Any:
    """Propose une salle par agenda, d'apres les reservations deja faites.

    C'est ce qui rend l'ecran tenable : plutot que de regler quarante-cinq
    lignes a la main, on part des 24 % d'evenements qui reservent vraiment une
    salle et on en deduit l'habitude de leur agenda.

    **Rien n'est enregistre.** La proposition remplit le formulaire, une
    personne valide. Ecrire d'office ferait dire a la grille qu'un cours se
    tient quelque part alors que personne ne l'a verifie — et une salle devinee
    presentee comme un fait est exactement le genre d'affichage qui ment.
    """
    fin = datetime.now(timezone.utc)
    debut = fin - timedelta(days=jours)
    autorises = _agendas_visibles(await calendrier.tous_les_agendas(), user)
    evenements, _ = await calendrier.evenements_de(autorises, debut, fin)

    comptes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    totaux: collections.Counter = collections.Counter()
    noms: dict[str, str] = {}
    for evenement in evenements:
        totaux[evenement.agenda_id] += 1
        noms.setdefault(evenement.agenda_id, evenement.agenda_nom)
        # Seules les vraies reservations instruisent : une salle deja deduite
        # se confirmerait elle-meme.
        if evenement.salle and evenement.salle_source == "google":
            comptes[evenement.agenda_id][evenement.salle] += 1

    deja_reglees = crud_calendrier.reglages_par_agenda(db)
    propositions = []
    for agenda_id, compte in comptes.items():
        if deja_reglees.get(agenda_id) and deja_reglees[agenda_id].salle:
            continue  # ne pas proposer de defaire un reglage existant
        salle, occurrences = compte.most_common(1)[0]
        propositions.append(
            SalleDeduiteOut(
                agenda_id=agenda_id,
                agenda_nom=noms.get(agenda_id, agenda_id),
                salle=salle,
                occurrences=occurrences,
                total_evenements=totaux[agenda_id],
            )
        )
    return sorted(propositions, key=lambda p: -p.occurrences)


@router.get(
    "/etat",
    response_model=EtatCalendrierOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
async def etat_calendrier(db: Session = Depends(get_db)) -> Any:
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
    reglees = {a for a, r in crud_calendrier.reglages_par_agenda(db).items() if r.salle}
    return EtatCalendrierOut(
        configure=True,
        compte_impersonne=settings.google_calendar_subject,
        nombre_agendas=len(agendas),
        agendas_restreints=settings.google_calendar_restricted,
        agendas_sans_salle=sum(1 for a in agendas if a.get("id") not in reglees),
    )


@router.post(
    "/rafraichir",
    response_model=EtatCalendrierOut,
    dependencies=[Depends(require_roles("Super Admin", "AdminBenevoles"))],
)
async def rafraichir(db: Session = Depends(get_db)) -> Any:
    """Vide le cache memoire.

    Le cache tient quelques minutes : c'est ce qui evite 42 appels par clic.
    Mais quand on vient de corriger un horaire dans Google, attendre sans
    comprendre pourquoi l'ecran ment est plus couteux que le rechargement.
    """
    await vider_cache()
    return await etat_calendrier(db)
