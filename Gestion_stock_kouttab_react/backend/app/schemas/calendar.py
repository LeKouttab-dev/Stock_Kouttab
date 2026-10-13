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
    # Le libelle affiche sur une carte de cours : « Coran ENF 1 » plutot que
    # « Coran - enfants 1 U.soundousse 2026/2027 ». Calcule, ou saisi dans les
    # reglages quand la regle tombe mal.
    nom_court: str = ""
    # L'enseignant, lu dans le nom de l'agenda (« U.soundousse »). Tous les
    # agendas n'en portent pas.
    enseignant: str | None = None
    # La salle habituelle, saisie dans les reglages. Ce n'est pas une
    # reservation : cf. `salle_source` sur l'evenement.
    salle_par_defaut: str | None = None


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
    # --- Lecture « emploi du temps » ------------------------------------
    # La colonne de la grille : cle de `calendrier_salles.SALLES`, ou None.
    salle: str | None = None
    # **D'ou vient cette salle**, et c'est tout sauf un detail : `google`, elle
    # est reservee ; `correspondance`, c'est l'habitude de l'agenda, devinee
    # par l'application. Une habitude affichee comme une reservation enverrait
    # quelqu'un devant une porte fermee.
    salle_source: str | None = None
    salle_libelle: str | None = None
    # Le numero de seance : « cours 19 » -> « 19 ». Absent des permanences.
    numero: str | None = None
    enseignant: str | None = None
    nom_court: str = ""


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
    # Le referentiel des salles, dans l'ordre des colonnes de la grille. Servi
    # plutot que recopie cote front : les colonnes et la liste deroulante de
    # l'ecran de reglage doivent etre la meme chose, et ajouter une salle ne
    # doit couter qu'une ligne de Python.
    salles: dict[str, str] = {}


class ReglageAgendaIn(BaseModel):
    """Ce qu'une personne saisit pour un agenda, dans l'ecran de reglage.

    Les deux champs sont facultatifs et `null` les rend a leur calcul : vider
    le nom court fait revenir l'abreviation automatique, vider la salle fait
    retomber l'agenda dans « Autre ».
    """

    salle: str | None = None
    nom_court: str | None = Field(default=None, max_length=64)


class ReglagesAgendasIn(BaseModel):
    """Un lot de reglages, indexe par identifiant d'agenda Google."""

    reglages: dict[str, ReglageAgendaIn]


class ReglageAgendaOut(BaseModel):
    agenda_id: str
    salle: str | None = None
    nom_court: str | None = None


class ReglagesAgendasOut(BaseModel):
    """L'etat complet des reglages, plus le referentiel des salles.

    Le referentiel est servi plutot que recopie cote front : les colonnes de la
    grille et la liste deroulante de l'ecran doivent etre la meme chose.
    """

    reglages: list[ReglageAgendaOut]
    salles: dict[str, str]


class SalleDeduiteOut(BaseModel):
    """Une salle *proposee* pour un agenda, d'apres les reservations passees."""

    agenda_id: str
    agenda_nom: str
    salle: str
    # Sur combien d'evenements la deduction s'appuie : une salle vue une fois
    # ne vaut pas une salle vue trente fois, et la personne doit le savoir.
    occurrences: int
    total_evenements: int


class EtatCalendrierOut(BaseModel):
    """Diagnostic de l'integration, pour l'ecran d'administration."""

    configure: bool
    # Vrai quand l'onglet sert le releve fige faute de connexion Google.
    instantane: bool = False
    genere_le: str | None = None
    compte_impersonne: str | None = None
    nombre_agendas: int | None = None
    agendas_restreints: list[str] = []
    # Combien d'agendas n'ont pas encore de salle habituelle. Tant que ce
    # nombre est eleve, la grille entasse les cours dans « Autre » et l'ecran
    # parait casse sans qu'on sache pourquoi.
    agendas_sans_salle: int | None = None
    erreur: str | None = None
