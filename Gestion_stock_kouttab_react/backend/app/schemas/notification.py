"""Schemas des rappels affiches a l'utilisateur connecte."""

from __future__ import annotations

from pydantic import BaseModel


class PendingSummaryOut(BaseModel):
    """Dossiers en attente, deja filtres par les droits du demandeur.

    Un compteur a 0 signifie « rien a traiter » **ou** « pas concerne » : les
    deux se presentent pareil, et c'est voulu — l'interface n'a pas a distinguer
    les deux cas, et le nombre reel n'est jamais envoye a qui n'y a pas droit.
    """

    notes_a_valider: int = 0
    factures_a_traiter: int = 0
    modifications_stock: int = 0
    comptes_a_valider: int = 0
    articles_en_alerte: int = 0
    # Tickets que la comptabilite m'adresse (tout utilisateur).
    justificatifs_demandes: int = 0
    # Tickets ouverts, toutes personnes confondues (comptabilite).
    tickets_ouverts: int = 0
    # Mes pieces sur lesquelles la comptabilite s'est prononcee sans que je
    # l'aie vu : chacun pour soi, visible de tous.
    notes_suivies: int = 0
    factures_suivies: int = 0
    # Fils de discussion qui attendent une reponse de l'equipe.
    conversations_a_traiter: int = 0
    # Mes fils ou une reponse est arrivee que je n'ai pas encore ouverte.
    conversations_non_lues: int = 0

    @property
    def total(self) -> int:
        return (
            self.notes_a_valider
            + self.factures_a_traiter
            + self.modifications_stock
            + self.comptes_a_valider
            + self.justificatifs_demandes
            + self.conversations_a_traiter
            + self.conversations_non_lues
            + self.notes_suivies
            + self.factures_suivies
        )
