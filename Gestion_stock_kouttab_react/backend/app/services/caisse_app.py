"""L'application de la tablette de caisse, servie pour ses mises a jour.

La tablette tourne en mode borne : aucune autre application ne peut s'y ouvrir,
personne ne va au magasin d'applications. Elle est proprietaire de l'appareil,
donc Android la laisse installer un APK sans confirmation — c'est le seul
chemin de mise a jour possible, et il suppose que quelqu'un serve le fichier.

**L'APK n'est JAMAIS public**, contrairement aux photos de produits : il porte
en clair la cle affiliee SumUp et `CAISSE_API_KEY`. Le rendre telechargeable
donnerait a n'importe qui le droit de poster des ventes et de lire le catalogue.
Les deux routes qui le servent exigent donc l'en-tete `X-Caisse-Key`, comme le
catalogue et les ventes.

**Sur le disque, pas en base.** Les justificatifs vivent en base parce que le
disque du VPS n'est pas sauvegarde et qu'une piece comptable ne se reconstruit
pas. Un APK, si : il se rebatit depuis les sources en une commande. Quarante
mega-octets dans une base MySQL distante couteraient un aller-retour reseau
complet a chaque lecture, et se heurteraient a `max_allowed_packet`.

Le fichier vit donc dans le volume `uploads`, **deja monte** dans le conteneur —
aucune ligne a ajouter au `compose.yml`, qui ne se deploie pas tout seul et se
recopie a la main sur le VPS.

Une seule version est conservee : la tablette ne demande jamais une version
precise, elle compare un numero et telecharge si le notre est plus grand.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger


logger = get_logger("caisse_app")

_DOSSIER = "caisse-app"
_NOM_APK = "caisse.apk"
_NOM_MANIFESTE = "version.json"

# Un APK est une archive ZIP : elle commence par `PK\x03\x04`. Ce controle ne
# prouve pas qu'il s'agit d'une application Android, mais il arrete le fichier
# depose par erreur — une photo, un PDF — avant qu'il ne parte en caisse.
_SIGNATURE_ZIP = b"PK\x03\x04"


@dataclass(frozen=True)
class VersionApplication:
    """Ce que la tablette lit pour decider si elle doit se mettre a jour."""

    version_code: int
    version_name: str
    sha256: str
    taille: int
    depose_le: str


def _dossier() -> Path:
    return settings.upload_path / _DOSSIER


def chemin_apk() -> Path:
    return _dossier() / _NOM_APK


def _chemin_manifeste() -> Path:
    return _dossier() / _NOM_MANIFESTE


def version_publiee() -> VersionApplication | None:
    """La version actuellement servie, ou ``None`` si rien n'a ete depose.

    ``None`` n'est pas une erreur : c'est l'etat normal tant que personne n'a
    publie d'APK, et la tablette continue simplement avec la sienne.
    """
    manifeste, apk = _chemin_manifeste(), chemin_apk()
    if not manifeste.exists() or not apk.exists():
        return None
    try:
        donnees = json.loads(manifeste.read_text(encoding="utf-8"))
        return VersionApplication(
            version_code=int(donnees["version_code"]),
            version_name=str(donnees["version_name"]),
            sha256=str(donnees["sha256"]),
            taille=int(donnees.get("taille", apk.stat().st_size)),
            depose_le=str(donnees.get("depose_le", "")),
        )
    except (OSError, ValueError, KeyError) as exc:
        # Un manifeste illisible vaut « aucune version » : servir un APK sans
        # empreinte verifiable serait pire que ne rien servir du tout.
        logger.error("Manifeste de l'application caisse illisible : %s", exc)
        return None


def publier(contenu: bytes, *, version_code: int, version_name: str, depose_le: str) -> VersionApplication:
    """Remplace l'APK servi, empreinte comprise.

    Ecriture en deux temps — fichier temporaire puis renommage atomique : une
    tablette qui telecharge pendant le depot recevrait sinon un fichier
    tronque, dont l'empreinte ne correspondrait pas. Le manifeste est ecrit
    APRES l'APK, pour qu'il n'annonce jamais une version absente.
    """
    if not contenu.startswith(_SIGNATURE_ZIP):
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Ce fichier n'est pas un APK (archive Android attendue).",
        )
    plafond = settings.caisse_apk_max_mb * 1024 * 1024
    if len(contenu) > plafond:
        raise AppException(
            ErrorCode.FILE_TOO_LARGE,
            detail=f"APK trop volumineux (> {settings.caisse_apk_max_mb} Mo).",
            extras={"max_mb": settings.caisse_apk_max_mb},
        )

    dossier = _dossier()
    dossier.mkdir(parents=True, exist_ok=True)
    empreinte = hashlib.sha256(contenu).hexdigest()

    descripteur, temporaire = tempfile.mkstemp(dir=dossier, suffix=".part")
    try:
        with os.fdopen(descripteur, "wb") as sortie:
            sortie.write(contenu)
        os.replace(temporaire, chemin_apk())
    except OSError:
        Path(temporaire).unlink(missing_ok=True)
        raise

    version = VersionApplication(
        version_code=version_code,
        version_name=version_name,
        sha256=empreinte,
        taille=len(contenu),
        depose_le=depose_le,
    )
    _chemin_manifeste().write_text(
        json.dumps(
            {
                "version_code": version.version_code,
                "version_name": version.version_name,
                "sha256": version.sha256,
                "taille": version.taille,
                "depose_le": version.depose_le,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    logger.info(
        "Application caisse publiee : %s (code %s, %s octets).",
        version.version_name,
        version.version_code,
        version.taille,
    )
    return version


def retirer() -> None:
    """Retire la version publiee. Les tablettes gardent celle qu'elles executent."""
    # Le manifeste d'abord : tant qu'il existe, la tablette croit a une version.
    _chemin_manifeste().unlink(missing_ok=True)
    chemin_apk().unlink(missing_ok=True)


__all__ = [
    "VersionApplication",
    "chemin_apk",
    "publier",
    "retirer",
    "version_publiee",
]
