"""Relance d'un justificatif manquant — le point d'assemblage UNIQUE.

Deux chemins envoient cette relance : l'endpoint (rappel n°1, à l'ouverture du
ticket ou sur demande) et le worker de la file (n°2 à 5, tous les trois
jours). Ils recopiaient le même appel à huit arguments, et avaient déjà
divergé une fois : le worker n'envoyait pas le rôle du destinataire, si bien
qu'un compte « BenevoleFrais » recevait quatre relances sur cinq avec un lien
vers un écran de connexion où il n'a pas de mot de passe. Un seul point
d'assemblage supprime la classe de bug, pas seulement ce cas-là.
"""

from __future__ import annotations

from app.crud import ticket as ticket_crud
from app.db.models import JustificatifTicket
from app.services import email as email_service


async def envoyer(ticket: JustificatifTicket) -> None:
    """Compose et envoie la relance du ticket (rappel n° ``rappels_envoyes + 1``).

    Suppose ``ticket.user`` chargé et pourvu d'une adresse — les deux appelants
    le vérifient avant, chacun avec sa propre réaction (log ou abandon).
    """
    await email_service.send_justificatif_reminder(
        recipient=ticket.user.email,
        prenom=ticket.user.prenom,
        role=ticket.user.role,
        libelle=ticket.libelle,
        description=ticket.description,
        montant=(
            f"{ticket.montant_attendu:.2f} EUR"
            if ticket.montant_attendu is not None
            else None
        ),
        date_achat=(
            ticket.date_achat.strftime("%d/%m/%Y") if ticket.date_achat else None
        ),
        fournisseur=ticket.fournisseur,
        rappel_numero=ticket.rappels_envoyes + 1,
        rappels_max=ticket_crud.RAPPELS_MAX,
    )
