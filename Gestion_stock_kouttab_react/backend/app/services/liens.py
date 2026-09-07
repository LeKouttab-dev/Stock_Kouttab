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
from app.services.email_layout import SIGNATURE


def lien_espace(role: str | None, page: str = "expenses") -> str:
    """L'URL absolue que le courriel propose au déposant, selon son compte."""
    if role == "BenevoleFrais":
        return f"{settings.gestion_url.rstrip('/')}/benevole"
    return f"{settings.frontend_url.rstrip('/')}/{page.lstrip('/')}"


def avec_lien(texte: str | None, lien: str) -> str:
    """Ajoute la ligne d'accès à une conclusion de courriel, ou la constitue."""
    ligne = f"Acceder a votre espace : {lien}"
    return f"{texte}\n\n{ligne}" if texte else ligne


# ---- Filet de securite ------------------------------------------------------
#
# Les liens ci-dessus sont poses par les gabarits qui savent OU envoyer leur
# lecteur. Tous ne le savaient pas : l'alerte de stock, l'avis de depot a la
# comptabilite, la demande de compte, le fil « Nous contacter » partaient sans
# la moindre adresse — « connectez-vous a l'application » et rien de plus. Le
# destinataire devait retrouver le domaine de memoire.
#
# Le filet est pose la ou TOUT passe : la mise en file (`outbox.enqueue`) et
# l'envoi (`email._send_raw`). Un gabarit ajoute demain sans lien en heritera
# sans qu'on ait a y penser, et un gabarit qui en pose deja un n'est pas touche.

LIBELLE_ACCES = "Acceder a l'application"


def contient_un_lien(texte: str | None) -> bool:
    """Vrai des qu'une URL absolue figure dans le texte."""
    corps = texte or ""
    return "http://" in corps or "https://" in corps


def garantir_lien(corps: str | None, lien: str | None = None) -> str:
    """Rend un corps qui porte une URL, en ajoutant celle de l'application au besoin.

    La ligne se glisse **avant** la signature quand celle-ci est reconnue : un
    lien pose apres « L'institut Le Kouttâb » se lit comme une pièce rapportée.
    """
    texte = corps or ""
    if contient_un_lien(texte):
        return texte
    ligne = f"{LIBELLE_ACCES} : {lien or settings.frontend_url.rstrip('/')}"
    if SIGNATURE and SIGNATURE in texte:
        return texte.replace(SIGNATURE, f"{ligne}\n\n{SIGNATURE}", 1)
    return f"{texte}\n\n{ligne}" if texte else ligne
