"""Calculs monetaires du domaine.

**Jumeau de `frontend/src/lib/money.ts`**, au meme titre que `naming.py` l'est de
`naming.ts` : les deux modules doivent rendre le meme chiffre sur les memes
donnees. Le front l'affiche a la comptabilite, le back le grave dans le
justificatif remis et dans ``Remboursements.montant_total``. Une divergence
produirait un document contredisant l'ecran qui l'a declenche.

Toute correction ici en appelle une la-bas, et les deux jeux de tests couvrent
les memes cas.

``Decimal`` de bout en bout, jamais ``float`` : la colonne est un DECIMAL(10,2),
et `0.1 + 0.2` en virgule flottante vaut 0.30000000000000004 — un ecart qu'une
piece comptable ne peut pas porter.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Protocol


class _Remboursable(Protocol):
    """Ce dont le calcul a besoin : ni l'ORM, ni un schema particulier."""

    montant: Decimal | None
    remboursement_deja_emis: Decimal | None
    remise: Decimal | None


ZERO = Decimal("0")


def _decimal(valeur: Decimal | int | float | str | None) -> Decimal:
    if valeur is None:
        return ZERO
    if isinstance(valeur, Decimal):
        return valeur
    return Decimal(str(valeur))


def montant_du(note: _Remboursable) -> Decimal:
    """Montant reellement du au benevole pour une note de frais.

    On soustrait ce qui a deja ete rembourse (avance en especes) et la remise
    obtenue chez le fournisseur.

    Le resultat est borne a zero : un remboursement negatif se lirait comme une
    dette du benevole envers l'association, ce que la donnee ne dit pas.
    """
    reste = _decimal(note.montant) - _decimal(note.remboursement_deja_emis) - _decimal(note.remise)
    return reste if reste > ZERO else ZERO


def total_a_rembourser(notes: Iterable[_Remboursable]) -> Decimal:
    """Somme des montants dus, note par note.

    Le plafonnement a zero s'applique **par note** et non sur le total : une
    note soldee d'avance ne doit pas venir amputer le remboursement d'une autre.
    """
    return sum((montant_du(n) for n in notes), ZERO)


__all__ = ["montant_du", "total_a_rembourser"]
