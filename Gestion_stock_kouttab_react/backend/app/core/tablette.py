"""Le compte système « Tablette buvette » et la signature des actions faites depuis la tablette.

L'écran « Personnel » de la tablette de caisse affiche l'application stock
elle-même. La tablette est partagée : pas de mot de passe à retenir, on demande
seulement le NOM de la personne, qui signe chaque action (« Nom (tablette) »).

- Le compte est créé par la migration ``f6a3b8c0d5e7`` (rôle ``AdminStock``,
  donc confiné à la buvette). Son mot de passe est INUTILISABLE et la connexion
  par formulaire le refuse explicitement : sa seule porte est
  ``POST /auth/caisse/session``, gardée par la clé de la caisse.
- Le nom de l'opérateur voyage dans les jetons (revendication ``op``) ; la
  dépendance d'authentification le pose sur l'objet utilisateur, sans jamais
  le persister.
- Son adresse est un identifiant interne, pas une boîte : le compte est exclu
  des destinataires des courriels de la buvette.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

USERNAME_TABLETTE = "tablette_buvette"
EMAIL_TABLETTE = "tablette-buvette@lekouttab.fr"
PRENOM_TABLETTE = "Tablette"
NOM_TABLETTE = "buvette"
ROLE_TABLETTE = "AdminStock"
# Ni un bcrypt (« $2b$… »), ni un SHA-256 hérité (64 hex) : aucun mot de passe
# ne peut lui correspondre. La connexion le refuse de toute façon avant de
# comparer (cf. `auth._do_login`).
MOT_DE_PASSE_INUTILISABLE = "!compte-systeme-tablette-sans-mot-de-passe"

# Attribut posé sur l'instance `Admin` par `deps.get_current_user` (non mappé).
ATTRIBUT_OPERATEUR = "operateur_tablette"

OPERATEUR_MIN = 2
OPERATEUR_MAX = 60

_ESPACES = re.compile(r"\s+")


def est_compte_tablette(user: Any) -> bool:
    """Vrai pour le compte système de la tablette (identifié par son identifiant)."""
    return user is not None and getattr(user, "username", None) == USERNAME_TABLETTE


def nettoyer_operateur(brut: str | None) -> str:
    """Nom saisi sur la tablette : caractères de contrôle retirés, espaces réduits.

    Lève ``ValueError`` si le résultat ne fait pas 2 à 60 caractères.
    """
    # Espaces (tabulations, retours a la ligne compris) ramenes a un seul, puis
    # caracteres de controle et invisibles (categories Unicode « C ») retires.
    texte = _ESPACES.sub(" ", brut or "")
    texte = "".join(c for c in texte if not unicodedata.category(c).startswith("C"))
    texte = _ESPACES.sub(" ", texte).strip()
    if not (OPERATEUR_MIN <= len(texte) <= OPERATEUR_MAX):
        raise ValueError(
            f"Le nom doit faire entre {OPERATEUR_MIN} et {OPERATEUR_MAX} caractères."
        )
    return texte


def operateur_de(user: Any) -> str | None:
    """Nom de l'opérateur d'une session tablette, ``None`` sinon."""
    if not est_compte_tablette(user):
        return None
    op = getattr(user, ATTRIBUT_OPERATEUR, None)
    return op or None


def nom_auteur(user: Any) -> str:
    """Le nom figé sur une action (inventaire, clôture, réappro, produit…).

    ``"<op> (tablette)"`` pour une session tablette, sinon le nom complet.
    Toute écriture d'auteur passe par ici, jamais par ``full_name`` directement.
    """
    op = operateur_de(user)
    if op:
        return f"{op} (tablette)"
    return user.full_name
