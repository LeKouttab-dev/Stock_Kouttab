"""Types de colonnes maison.

``ChampChiffre`` place le chiffrement a la frontiere de la base plutot que dans
le CRUD : tout ce qui lit ou ecrit ``Admin.rib`` passe par lui, y compris le
code ecrit plus tard qui ignorerait tout du sujet. Un chiffrement qu'on peut
oublier d'appeler finit toujours par etre oublie quelque part.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core import crypto
from app.core.logger import get_logger


logger = get_logger("db.types")


class ChampChiffre(TypeDecorator):
    """Colonne texte chiffree au repos (AES-256-GCM).

    Le stockage reste un ``VARCHAR`` : le schema MySQL est partage et ne doit
    pas bouger. Une valeur chiffree tient largement dans les 255 caracteres de
    ``Admins.rib`` — la validation Pydantic borne la saisie en amont.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        """Ecriture : chiffre systematiquement."""
        if value is None:
            return None
        return crypto.chiffrer(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Lecture : dechiffre, et supporte les valeurs en clair heritees.

        Une valeur illisible ne fait pas tomber la requete : la note de frais
        s'affiche sans le RIB, et l'incident est journalise. Le contraire
        rendrait toute la page inaccessible pour un seul compte abime, alors
        que la comptabilite a besoin des autres.
        """
        if value is None:
            return None
        try:
            return crypto.dechiffrer(str(value))
        except (crypto.ErreurDechiffrement, crypto.CleAbsente) as exc:
            logger.error("RIB illisible en base : %s", exc)
            return None


__all__ = ["ChampChiffre"]
