"""Moyens de paiement et etablissements proposes au remboursement.

Listes **figees**, contrairement aux poles et aux categories de depense : elles
tiennent en trois entrees, ne bougent qu'au rythme des comptes bancaires de
l'association, et un referentiel administrable pour cela couterait plus cher a
maintenir qu'il ne rapporterait.

Ce que la valeur enregistree devient : une chaine en clair sur
``Remboursements``, pas une cle etrangere. Un justificatif deja remis a la
comptabilite doit rester lisible tel qu'il a ete emis, meme si ces listes
changent — meme raisonnement que ``Invoice.pole``.
"""

from __future__ import annotations


MOYENS: tuple[str, ...] = ("Virement bancaire", "Espèce", "Chèque")
ETABLISSEMENTS: tuple[str, ...] = ("Wise", "Crédit Mutuel", "SumUp")

# Valeurs pre-remplies dans le formulaire, arretees avec le client.
MOYEN_PAR_DEFAUT = MOYENS[0]
ETABLISSEMENT_PAR_DEFAUT = ETABLISSEMENTS[0]
APPROBATEUR_PAR_DEFAUT = "DTC"


def valider_moyen(valeur: str) -> str:
    """Retourne le moyen s'il fait partie de la liste, leve sinon."""
    return _valider(valeur, MOYENS, "moyen de remboursement")


def valider_etablissement(valeur: str) -> str:
    return _valider(valeur, ETABLISSEMENTS, "etablissement")


def _valider(valeur: str, autorisees: tuple[str, ...], libelle: str) -> str:
    from app.core.errors import ErrorCode
    from app.core.exceptions import AppException

    nettoyee = (valeur or "").strip()
    if nettoyee not in autorisees:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"{libelle} invalide : {', '.join(autorisees)}.",
        )
    return nettoyee


__all__ = [
    "APPROBATEUR_PAR_DEFAUT",
    "ETABLISSEMENTS",
    "ETABLISSEMENT_PAR_DEFAUT",
    "MOYENS",
    "MOYEN_PAR_DEFAUT",
    "valider_etablissement",
    "valider_moyen",
]
