"""Instantané des agendas Google, servi tant que la connexion n'est pas faite.

**Provisoire, et daté.** Le fichier `app/ressources/calendrier_instantane.json` est un
relevé figé des agendas de l'association, pris le 2026-09-20 sur quatre
semaines. Il existe pour une seule raison : l'onglet Calendrier est en
production avant le compte de service Google, et un écran vide n'apprend rien à
personne.

Dès que `GOOGLE_SERVICE_ACCOUNT_JSON` et `GOOGLE_CALENDAR_SUBJECT` sont posés,
le direct prend la main **sans rien changer d'autre** : ce module n'est plus
appelé. Le fichier peut alors être supprimé, et ce module avec lui.

Ce qu'il ne contient pas, volontairement :

- **« PSY RDV »** — un fichier versionné vit dans l'historique Git pour de bon,
  et ces titres nomment les familles suivies. Cet agenda ne reviendra que par la
  connexion en direct, où le filtrage par rôle s'applique.
- **Les descriptions et les participants** — inutiles à l'affichage, et c'est
  autant de contenu qui n'entre pas dans le dépôt.

Les couleurs ne viennent pas de Google : cet accès ne les expose pas. Elles sont
posées par famille de cours, pour que la grille reste lisible ; les vraies
arrivent avec le direct.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.logger import get_logger


logger = get_logger("calendrier_instantane")

CHEMIN = Path(__file__).resolve().parent.parent / "ressources" / "calendrier_instantane.json"


@lru_cache(maxsize=1)
def charger() -> dict[str, Any] | None:
    """Lit le fichier une fois pour la vie du processus. ``None`` s'il est absent.

    Absent n'est pas une erreur : c'est l'état normal une fois la connexion
    Google faite et le fichier supprimé.
    """
    if not CHEMIN.exists():
        return None
    try:
        donnees = json.loads(CHEMIN.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # Un instantané illisible ne doit pas empêcher l'onglet de dire
        # « pas encore configuré » : c'est la même situation pour l'utilisateur.
        logger.error("Instantané du calendrier illisible (%s) : %s", CHEMIN, exc)
        return None
    if not isinstance(donnees, dict) or "evenements" not in donnees:
        logger.error("Instantané du calendrier au format inattendu (%s).", CHEMIN)
        return None
    return donnees


def disponible() -> bool:
    return charger() is not None


def genere_le() -> str | None:
    donnees = charger()
    return donnees.get("genere_le") if donnees else None


def agendas() -> list[dict[str, Any]]:
    """Agendas au format d'une entrée `calendarList` de Google.

    La forme est celle de l'API pour que l'endpoint normalise les deux sources
    avec le MÊME code : deux convertisseurs finiraient par diverger, et l'écran
    afficherait des choses différentes selon la source.
    """
    donnees = charger()
    if not donnees:
        return []
    return [
        {
            "id": a["id"],
            "summary": a["nom"],
            "backgroundColor": a.get("couleur"),
            "timeZone": "Europe/Paris",
        }
        for a in donnees.get("agendas", [])
    ]


def _moment(valeur: str) -> datetime:
    """ISO 8601 du fichier → instant comparable. Date seule = minuit à Paris."""
    brut = f"{valeur}T00:00:00+02:00" if len(valeur) == 10 else valeur
    instant = datetime.fromisoformat(brut)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant


def evenements(
    calendar_ids: list[str], debut: datetime, fin: datetime
) -> dict[str, list[dict[str, Any]]]:
    """Événements de la fenêtre, au format d'un `events.list` de Google.

    Un événement est retenu dès qu'il CHEVAUCHE la fenêtre, comme le fait
    `timeMin`/`timeMax` chez Google : une sortie de trois jours doit rester
    visible depuis la semaine où elle se termine.
    """
    donnees = charger()
    if not donnees:
        return {}

    voulus = set(calendar_ids)
    par_agenda: dict[str, list[dict[str, Any]]] = {c: [] for c in calendar_ids}
    for evenement in donnees.get("evenements", []):
        agenda_id = evenement.get("agenda_id")
        if agenda_id not in voulus:
            continue
        try:
            commence, termine = _moment(evenement["debut"]), _moment(evenement["fin"])
        except (KeyError, ValueError):
            continue
        if termine <= debut or commence >= fin:
            continue
        journee_entiere = bool(evenement.get("journee_entiere"))
        cle = "date" if journee_entiere else "dateTime"
        par_agenda[agenda_id].append(
            {
                "id": evenement.get("id", ""),
                "summary": evenement.get("titre"),
                "start": {cle: evenement["debut"]},
                "end": {cle: evenement["fin"]},
                "location": evenement.get("lieu"),
                "status": "confirmed",
            }
        )
    return par_agenda


__all__ = ["agendas", "charger", "disponible", "evenements", "genere_le"]
