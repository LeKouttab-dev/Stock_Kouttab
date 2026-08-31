"""Liens d'accès placés dans les courriels au déposant.

Un courriel qui dit « rendez-vous dans l'application » sans lien oblige à
retrouver l'adresse soi-même ; et le MAUVAIS lien est pire : un compte
« BenevoleFrais » n'a pas de mot de passe stock — le renvoyer vers l'écran de
connexion serait une impasse. Sa porte d'entrée est l'outil de gestion, où un
clic sur « Notes de frais » refait le passage signé.

JAMAIS de jeton dans un courriel — et ce n'est pas une lacune, c'est un choix :
nos jetons de passage vivent 60 secondes et servent une fois, un « lien
magique » durable dans une boîte mail serait une session volable au premier
transfert de message ou à la première fuite de boîte.
"""

from __future__ import annotations

from app.core.config import settings


def lien_espace(role: str | None, page: str = "expenses") -> str:
    """L'URL absolue que le courriel propose au déposant, selon son compte."""
    if role == "BenevoleFrais":
        return f"{settings.gestion_url.rstrip('/')}/benevole"
    return f"{settings.frontend_url.rstrip('/')}/{page.lstrip('/')}"


def avec_lien(texte: str | None, lien: str) -> str:
    """Ajoute la ligne d'accès à une conclusion de courriel, ou la constitue."""
    ligne = f"Acceder a votre espace : {lien}"
    return f"{texte}\n\n{ligne}" if texte else ligne
