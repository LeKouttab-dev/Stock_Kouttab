"""Journal de la tablette de caisse : ce qui lui arrive, consultable sur le VPS.

Constat du 13/10/2026 : la tablette a ete retrouvee au matin sur l'accueil
d'Android, et rien ne permettait de savoir quand ni pourquoi la caisse avait
quitte l'ecran (seul le dernier releve d'etat est garde). La tablette tient donc
un journal (demarrage, plantage, retour force, ecran allume/eteint, secteur,
veille, mises a jour) qu'elle envoie ici, et qui s'ajoute a un fichier par jour.

**Sur le disque, pas en base**, comme l'APK (`caisse_app`) : c'est un outil de
diagnostic, pas une donnee metier. Le volume `uploads` est deja monte dans le
conteneur et survit aux redeploiements, contrairement a `docker logs`.

Lecture sur le VPS :
    docker exec kouttab-stock-api ls /app/uploads/journal-tablette
    docker exec kouttab-stock-api cat /app/uploads/journal-tablette/2026-10-13.log

Une ligne par entree, separee par des tabulations : heure de la tablette,
niveau, message, heure de reception (UTC). Fichiers de plus de
[JOURS_CONSERVES] jours supprimes au fil des ecritures.
"""

from __future__ import annotations

import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.core.logger import get_logger
from app.schemas.buvette import CaisseJournalEntree


logger = get_logger("journal_tablette")

_DOSSIER = "journal-tablette"
_NOM_FICHIER = re.compile(r"^(\d{4}-\d{2}-\d{2})\.log$")
JOURS_CONSERVES = 60

# Deux requetes simultanees ne doivent pas entrelacer leurs lignes.
_verrou = threading.Lock()


def dossier() -> Path:
    return settings.upload_path / _DOSSIER


def ecrire(entrees: list[CaisseJournalEntree], recu: datetime | None = None) -> int:
    """Ajoute les entrees au fichier de leur jour (heure de la tablette)."""
    if not entrees:
        return 0
    recu = recu or datetime.now(timezone.utc)
    recu_txt = recu.astimezone(timezone.utc).isoformat(timespec="seconds")
    par_jour: dict[str, list[str]] = {}
    for e in entrees:
        jour = e.ts.date().isoformat()
        ligne = f"{e.ts.isoformat(timespec='seconds')}\t{e.niveau}\t{e.message}\t{recu_txt}\n"
        par_jour.setdefault(jour, []).append(ligne)

    with _verrou:
        racine = dossier()
        racine.mkdir(parents=True, exist_ok=True)
        for jour, lignes in par_jour.items():
            with (racine / f"{jour}.log").open("a", encoding="utf-8") as f:
                f.writelines(lignes)
        _purger(racine, recu.date())

    # Aussi dans `docker logs`, pour un coup d'oeil immediat.
    for e in entrees:
        if e.niveau in ("WARN", "ERREUR", "ERROR"):
            logger.warning("tablette %s %s", e.ts.isoformat(timespec="seconds"), e.message)
    return len(entrees)


def _purger(racine: Path, aujourd_hui: date) -> None:
    limite = aujourd_hui - timedelta(days=JOURS_CONSERVES)
    for fichier in racine.iterdir():
        trouve = _NOM_FICHIER.match(fichier.name)
        if not trouve:
            continue
        try:
            if date.fromisoformat(trouve.group(1)) < limite:
                fichier.unlink()
        except (ValueError, OSError):
            continue
