"""Mise en page commune des courriels.

Neuf gabarits vivent dans `email.py`, plus ceux composes dans les endpoints.
Chacun ouvrait par son propre « Bonjour » et signait a sa facon — « Cordialement,
Votre systeme de gestion », « Le Kouttab. »... Les corriger un par un les aurait
fait rediverger au premier ajout.

Ce module tient l'en-tete, le pied et la mise en forme des details. Les gabarits
n'ecrivent plus que ce qu'ils ont a dire.

La salutation est **« Assalamu alaykum »**, comme demande par le client : ces
courriels s'adressent aux benevoles d'un institut, et le registre compte autant
que le contenu.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable


SALUTATION = "Assalamu alaykum wa rahmatullah"
SIGNATURE = "Qu'Allah vous recompense pour votre engagement.\n\nL'institut Le Kouttâb"

# Largeur du libelle dans les blocs de details : aligner les valeurs rend un
# courriel de dix lignes lisible d'un coup d'oeil, ce qu'une suite de
# « cle : valeur » non alignes ne permet pas.
_LARGEUR = 16


def entete(prenom: str | None = None) -> str:
    """Salutation, personnalisee quand le prenom est connu."""
    nom = (prenom or "").strip()
    return f"{SALUTATION} {nom}," if nom else f"{SALUTATION},"


def details(lignes: Iterable[tuple[str, object]]) -> str:
    """Bloc « libelle : valeur », aligne, sans les entrees vides.

    Une ligne dont la valeur est absente est **retiree** plutot qu'affichee avec
    un tiret : un courriel troue de « - » donne l'impression d'un envoi
    automatique mal configure, alors qu'il s'agit simplement d'un champ
    facultatif que personne n'a rempli.
    """
    utiles = [(libelle, valeur) for libelle, valeur in lignes if _valeur(valeur)]
    if not utiles:
        return ""
    # Largeur calculee sur le bloc, et non figee : un libelle plus long que la
    # constante decalait sa ligne, et l'alignement — seule raison d'etre de ce
    # remplissage — sautait pour tout le message.
    largeur = max(_LARGEUR, *(len(libelle) for libelle, _ in utiles))
    return "\n".join(f"{libelle.ljust(largeur)}: {_valeur(valeur)}" for libelle, valeur in utiles)


def _valeur(valeur: object) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, Decimal | float | int) and not isinstance(valeur, bool):
        return f"{Decimal(str(valeur)):.2f} EUR"
    if isinstance(valeur, date):
        return valeur.strftime("%d/%m/%Y")
    texte = str(valeur).strip()
    return texte


def composer(
    *,
    prenom: str | None = None,
    introduction: str,
    blocs: Iterable[tuple[str, object]] | None = None,
    conclusion: str | None = None,
) -> str:
    """Assemble un courriel complet : salutation, propos, details, signature."""
    morceaux = [entete(prenom), "", introduction]
    corps = details(blocs or [])
    if corps:
        morceaux += ["", corps]
    if conclusion:
        morceaux += ["", conclusion]
    morceaux += ["", SIGNATURE]
    return "\n".join(morceaux)


__all__ = ["SALUTATION", "SIGNATURE", "composer", "details", "entete"]
