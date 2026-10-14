"""Ce qu'il faut lire entre les lignes d'un agenda Google pour en faire un
emploi du temps : la salle, l'enseignant, le numéro de séance, le nom court.

Google Agenda ne connaît pas les écoles. Il porte des agendas nommés
`Coran - enfants 1 U.soundousse 2026/2027` et des événements nommés `cours 19` :
tout le sens est dans le nom de l'agenda, et la grille affichait le titre. Ce
module fait la lecture inverse.

**Tout y est pur** — pas de base, pas de réseau, pas de `settings`. C'est ce qui
permet de le dérouler sur les 45 agendas réels dans un test unitaire, et c'est
nécessaire : une règle de raccourcissement ne se relit pas, elle se vérifie sur
les vrais noms.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, NamedTuple

# Les trois salles de cours de l'institut. Référentiel figé : ce ne sont pas
# des données, ce sont les colonnes de la grille, et en ajouter une relève d'un
# changement d'écran, pas d'un réglage.
SALLES: dict[str, str] = {
    "maziri": "Imam Maziri",
    "nafi": "Imam Nafi'",
    "zarrouq": "Imam Zarrouq",
}

# Où va un cours dont personne ne connaît la salle. Il y avait une colonne
# « Autre » ; elle mangeait une place de colonne pour trois quarts de cours que
# l'équipe sait de toute façon se tenir en Maziri, la grande salle.
#
# **Ce n'est ni une réservation ni une habitude**, et l'API le dit :
# `salle_source = "defaut"`. La carte garde ses pointillés — sans eux, la
# colonne Maziri afficherait comme bloqués des créneaux que personne n'a posés.
SALLE_PAR_DEFAUT = "maziri"

# Longueur visée pour le nom court. C'est ce qui tient dans une colonne de
# salle sur un écran de bureau, panneaux repliés.
LONGUEUR_NOM_COURT = 22

# Un créneau de moins de ça n'est pas un cours : à la buvette comme ici, les
# permanences administratives sont des rendez-vous de paiement de 5 minutes.
# La grille les fusionne plutôt que d'afficher des filets d'un pixel.
MINUTES_MICRO_CRENEAU = 15

_ABREVIATIONS: dict[str, str] = {
    "Alphabétisation": "Alpha",
    "Education": "Éduc.",
    "Permanence": "Perm.",
    "Transactions": "Transac.",
    "administrative": "admin.",
    "commerciales": "comm.",
    "comparée": "comp.",
    "comportement": "comport.",
    "enfants": "ENF",
    "femmes": "F",
    "hommes": "H",
    "éveil": "ÉVEIL",
    "immersion": "imm.",
    "islamique": "isl.",
    "jurisprudence": "jurisp.",
    "niveau": "N",
    "pédagogique": "péda.",
    "primaire": "PRIM",
    "prophétique": "proph.",
    "famille": "fam.",
    "Fondements": "Fond.",
    "Spiritualité": "Spirit.",
    "Analyse": "Analyse",
}

# Mots de liaison, retirés seulement si le nom dépasse encore après abréviation.
# Les ôter d'emblée donnerait « SI Mariage Sciences » -> « SI Mariage Sciences »
# (rien à gagner) mais « Coran - femmes niveau 1 semaine » -> « Coran F N 1
# semaine », où « semaine » distingue deux agendas réels. On ne coupe que sous
# la contrainte.
_LIAISONS = ("de la", "du", "de", "des", "et", "l'", "la", "le", "les")


class ReglageAgenda(NamedTuple):
    """Ce qu'une personne a saisi dans *Réglages des agendas*, pour un agenda.

    Volontairement détaché du modèle SQLAlchemy : la normalisation doit rester
    testable sans base, et c'est l'endpoint qui charge la table.
    """

    salle: str | None = None
    nom_court: str | None = None


def _sans_accents(texte: str | None) -> str:
    decompose = unicodedata.normalize("NFD", texte or "")
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn").lower()


def _salle_nommee(libelle: str | None) -> str | None:
    """Une des trois salles de cours, reconnue dans n'importe quel libellé.

    Recherche par sous-chaîne sans accents, et non égalité : **Google écrit
    « Zarruq », l'agenda du même nom écrit « Zarrouq »**, l'apostrophe de
    « Nafi' » est tantôt droite tantôt typographique, et le libellé complet est
    `Le Kouttâb-3-Salle Imam Maziri (50)` — bâtiment, étage, nom, capacité.
    """
    plie = _sans_accents(libelle)
    if not plie:
        return None
    if "maziri" in plie:
        return "maziri"
    if "nafi" in plie:
        return "nafi"
    # « zarr » couvre Zarruq, Zarrouq et Zarrouk d'un coup.
    if "zarr" in plie:
        return "zarrouq"
    return None


def salle_de_ressource(libelle: str | None) -> str | None:
    """La colonne d'une **ressource Google** réservée, si c'est une des trois.

    Une ressource qui n'est aucune des salles de cours — la salle de
    conférence — rend `None`. Il n'y a plus de colonne « Autre » où la ranger,
    et la classer en Maziri avec `salle_source = "google"` ferait passer une
    réservation de la salle de conférence pour une réservation de Maziri. Elle
    retombe donc sur la salle par défaut, en pointillés, et le lieu réel reste
    lisible dans la fiche (`lieu`).
    """
    return _salle_nommee(libelle)


def salle_reservee(brut: dict[str, Any]) -> str | None:
    """La salle **réellement réservée** dans Google, ou `None`.

    Deux sources, et elles ne se valent pas :

    - `attendees[]` avec `resource: true` — c'est la réservation au sens de
      Google Workspace, le créneau est bloqué pour cette pièce. Fait foi.
    - `location` — du **texte libre**. On n'y accepte qu'une des trois salles
      nommées. « Salle 2 », « le kouttab » ou une adresse postale n'y donnent
      rien : quelqu'un a écrit un mot, personne n'a réservé de pièce, et
      afficher ce créneau comme une réservation enverrait un enseignant
      devant une porte occupée.

    Un participant humain n'est jamais une salle, d'où le test sur `resource`.
    """
    for participant in brut.get("attendees") or []:
        if participant.get("resource"):
            salle = salle_de_ressource(participant.get("displayName"))
            if salle is not None:
                return salle
    return _salle_nommee(brut.get("location"))


def enseignant_de(nom_agenda: str | None) -> str | None:
    """`Coran - enfants 1 U.soundousse 2026/2027` -> `U. Soundousse`.

    Le « U. » est pour Ustadh / Ustadha. Tous les agendas n'en portent pas :
    les cours collectifs et les permanences n'ont pas d'enseignant nommé.
    """
    trouve = re.search(r"\bU\.\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]*)", nom_agenda or "")
    if not trouve:
        return None
    return f"U. {trouve.group(1).capitalize()}"


def _abreger(texte: str) -> str:
    for long, bref in sorted(_ABREVIATIONS.items(), key=lambda kv: -len(kv[0])):
        texte = re.sub(rf"\b{re.escape(long)}\b", bref, texte)
    return texte


def _sans_liaisons(texte: str) -> str:
    for mot in _LIAISONS:
        texte = re.sub(rf"\s+{re.escape(mot)}\s+", " ", texte, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", texte).strip()


def nom_court(nom_agenda: str | None) -> str:
    """Le nom d'agenda tel qu'il doit tenir sur une carte de cours.

    Trois passes, de la moins destructrice à la plus : abréviations, puis
    retrait des mots de liaison **seulement si c'est encore trop long**, puis
    troncature. La progressivité compte — `Coran - femmes niveau 1 semaine` et
    `… weekend` sont deux agendas distincts, et c'est le dernier mot qui les
    sépare.

    La règle tombe juste sur une quarantaine des 45 agendas réels. Les autres
    se corrigent à la main dans *Réglages des agendas* : quatre exceptions
    saisies valent mieux que quatre exceptions codées ici.
    """
    texte = nom_agenda or ""
    texte = re.sub(r"\s*\b20\d{2}\s*[/-]\s*20\d{2}\b", "", texte)  # l'année scolaire
    texte = re.sub(r"\bU\.\s*[A-Za-zÀ-ÿ'-]+", "", texte)  # l'enseignant, affiché à part
    texte = texte.replace(" / ", "/")
    texte = _abreger(texte)
    # « Coran - ENF 1 » -> « Coran ENF 1 ». Les espaces sont exigés autour du
    # tiret : sans eux, « 11-16ans » y perdrait le sien.
    texte = re.sub(r"\s+-\s+", " ", texte)
    texte = re.sub(r"\s{2,}", " ", texte).strip(" -")

    if len(texte) > LONGUEUR_NOM_COURT:
        texte = _sans_liaisons(texte)
    if len(texte) > LONGUEUR_NOM_COURT:
        texte = texte[: LONGUEUR_NOM_COURT - 1].rstrip() + "…"
    return texte


def numero_de(brut: dict[str, Any]) -> str | None:
    """Le numéro de séance : `cours 19` -> `19`.

    La propriété privée posée par l'outil qui génère les cours fait foi ; le
    titre n'est qu'un repli, parce qu'il se saisit à la main et se formule
    autrement d'un agenda à l'autre. Rend `None` pour ce qui n'est pas une
    séance — une permanence, une réunion — et la carte omet alors le numéro.
    """
    prive = (brut.get("extendedProperties") or {}).get("private") or {}
    depuis_propriete = prive.get("numero")
    if isinstance(depuis_propriete, str) and depuis_propriete.strip():
        return depuis_propriete.strip()
    trouve = re.search(r"\bcours\s*(\d+)", brut.get("summary") or "", re.IGNORECASE)
    return trouve.group(1) if trouve else None


__all__ = [
    "LONGUEUR_NOM_COURT",
    "MINUTES_MICRO_CRENEAU",
    "SALLES",
    "SALLE_PAR_DEFAUT",
    "ReglageAgenda",
    "enseignant_de",
    "nom_court",
    "numero_de",
    "salle_de_ressource",
    "salle_reservee",
]
