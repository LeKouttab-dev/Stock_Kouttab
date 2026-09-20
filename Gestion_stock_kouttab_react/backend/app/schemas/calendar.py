"""Schemas de l'onglet Calendrier (miroir en lecture des agendas Google)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgendaOut(BaseModel):
    """Un agenda Google visible dans l'application."""

    id: str
    nom: str
    description: str | None = None
    couleur: str | None = Field(
        default=None,
        description="Couleur de fond choisie dans Google, reprise telle quelle.",
    )
    couleur_texte: str | None = None
    fuseau: str | None = None
    # Un agenda restreint n'est servi qu'au Super Admin. Le drapeau accompagne
    # la ligne pour que l'ecran puisse le signaler a celui qui le voit.
    restreint: bool = False


class EvenementOut(BaseModel):
    """Une occurrence d'evenement, recurrences deja developpees par Google."""

    id: str
    agenda_id: str
    agenda_nom: str
    titre: str
    debut: str = Field(description="ISO 8601. Date seule si journee entiere.")
    fin: str
    journee_entiere: bool = False
    lieu: str | None = None
    description: str | None = None
    organisateur: str | None = None
    couleur: str | None = None
    lien: str | None = None
    statut: str | None = None
    recurrent: bool = False


class CalendrierOut(BaseModel):
    """Reponse de l'onglet : les evenements d'une fenetre, et ce qui a echoue."""

    evenements: list[EvenementOut]
    # Un agenda supprime ou devenu inaccessible ne doit pas vider la page des
    # quarante autres : on sert ce qu'on a, en disant ce qui manque.
    agendas_en_erreur: list[str] = []
    # Releve fige, servi tant que la connexion Google n'est pas faite. L'ecran
    # l'affiche : un planning date qui se presenterait comme le direct ferait
    # manquer un cours deplace.
    instantane: bool = False
    genere_le: str | None = None


class EtatCalendrierOut(BaseModel):
    """Diagnostic de l'integration, pour l'ecran d'administration."""

    configure: bool
    # Vrai quand l'onglet sert le releve fige faute de connexion Google.
    instantane: bool = False
    genere_le: str | None = None
    compte_impersonne: str | None = None
    nombre_agendas: int | None = None
    agendas_restreints: list[str] = []
    erreur: str | None = None
