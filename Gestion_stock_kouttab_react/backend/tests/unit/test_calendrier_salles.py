"""La lecture entre les lignes des agendas Google.

Ces fonctions sont pures, et c'est tout l'intérêt : la règle de
raccourcissement se vérifie sur les **vrais** noms d'agendas de l'institut,
relevés le 2026-10-14, et non sur des exemples inventés qui lui donneraient
toujours raison.
"""

from __future__ import annotations

import pytest

from app.services.calendrier_salles import (
    LONGUEUR_NOM_COURT,
    SALLES,
    enseignant_de,
    nom_court,
    numero_de,
    salle_de_ressource,
    salle_reservee,
)

pytestmark = pytest.mark.unit


# Les 45 agendas de l'institut, et ce que la grille doit en afficher.
# Tout changement de la règle se lit ici, agenda par agenda.
AGENDAS_REELS = [
    ("Alphabétisation - femmes U.isabelle 2026/2027", "Alpha F", "U. Isabelle"),
    ("Arabe immersion - primaire 1 2026/2027", "Arabe imm. PRIM 1", None),
    ("Arabe immersion - éveil 1 2026/2027", "Arabe imm. ÉVEIL 1", None),
    ("Coran - enfants 1 U.soundousse 2026/2027", "Coran ENF 1", "U. Soundousse"),
    ("Coran - enfants 1+2 U.soundousse 2026/2027", "Coran ENF 1+2", "U. Soundousse"),
    ("Coran - enfants 2 U.mohamed 2026/2027", "Coran ENF 2", "U. Mohamed"),
    ("Coran - enfants 3 U.isabelle 2026/2027", "Coran ENF 3", "U. Isabelle"),
    ("Coran - femmes niveau 1 semaine 2026/2027", "Coran F N 1 semaine", None),
    ("Coran - femmes niveau 1 weekend 2026/2027", "Coran F N 1 weekend", None),
    ("Coran - hommes niveau 2 2026/2027", "Coran H N 2", None),
    ("Education islamique 11-16ans 2026/2027", "Éduc. isl. 11-16ans", None),
    ("Education islamique 6-11ans 2026/2027", "Éduc. isl. 6-11ans", None),
    ("Hafiz famille 2026/2027", "Hafiz fam.", None),
    ("Hors cursus - SI - avancé 2026/2027", "Hors cursus SI avancé", None),
    ("Madrassah niveau 1 2026/2027", "Madrassah N 1", None),
    ("Non classé", "Non classé", None),
    ("Permanence administrative 2026/2027", "Perm. admin.", None),
    ("Permanence pédagogique 2026/2027", "Perm. péda.", None),
    ("SI - Adorations 2026/2027", "SI Adorations", None),
    ("SI - Analyse de la vie prophétique 2026/2027", "SI Analyse vie proph.", None),
    ("SI - Croyance / Spiritualité", "SI Croyance/Spirit.", None),
    ("SI - Fondements du coran et du hadith 2026/2027", "SI Fond. coran hadith", None),
    ("SI - Transactions commerciales 2026/2027", "SI Transac. comm.", None),
    ("SI - initiation 2026/2027", "SI initiation", None),
    ("Salle - Imam Zarrouq", "Salle Imam Zarrouq", None),
]


@pytest.mark.parametrize("nom, attendu, _enseignant", AGENDAS_REELS)
def test_nom_court_sur_les_agendas_reels(nom: str, attendu: str, _enseignant: str | None):
    assert nom_court(nom) == attendu


@pytest.mark.parametrize("nom, _court, attendu", AGENDAS_REELS)
def test_enseignant_sur_les_agendas_reels(nom: str, _court: str, attendu: str | None):
    assert enseignant_de(nom) == attendu


def test_aucun_nom_reel_ne_depasse_la_largeur_d_une_colonne():
    """La carte est tronquée par CSS en dernier recours, pas par défaut."""
    for nom, court, _ in AGENDAS_REELS:
        assert len(court) <= LONGUEUR_NOM_COURT, nom


def test_un_nom_tres_long_est_tronque_proprement():
    # Le seul agenda réel que la règle n'arrive pas à loger. Il se corrige à la
    # main dans les réglages ; en attendant, il doit rester lisible.
    court = nom_court("SI - Coran / Hadith / Fondements de la jurisprudence")
    assert court.endswith("…")
    assert len(court) <= LONGUEUR_NOM_COURT
    assert court.startswith("SI Coran/Hadith")


def test_le_tiret_d_une_tranche_d_age_survit():
    """« 11-16ans » n'est pas un séparateur de parties, contrairement à « - »."""
    assert "11-16ans" in nom_court("Education islamique 11-16ans 2026/2027")


def test_l_annee_scolaire_disparait_quelle_que_soit_sa_forme():
    assert nom_court("SI - Mariage 2026/2027") == "SI Mariage"
    assert nom_court("SI - Mariage 2026-2027") == "SI Mariage"


def test_nom_court_tolere_l_absence():
    assert nom_court(None) == ""
    assert nom_court("") == ""


def test_enseignant_absent_vaut_none():
    assert enseignant_de("Madrassah niveau 1 2026/2027") is None
    assert enseignant_de(None) is None


class TestSalleDeRessource:
    """Le libellé Google est `Le Kouttâb-3-Salle Imam Maziri (50)`."""

    def test_les_trois_salles_de_cours(self):
        assert salle_de_ressource("Le Kouttâb-3-Salle Imam Maziri (50)") == "maziri"
        assert salle_de_ressource("Le Kouttâb-3-Salle Imam Nafi' (25)") == "nafi"
        assert salle_de_ressource("Le Kouttâb-3-Salle Imam Zarruq (25)") == "zarrouq"

    def test_zarruq_et_zarrouq_sont_la_meme_salle(self):
        """Google écrit « Zarruq », l'agenda du même nom écrit « Zarrouq »."""
        assert salle_de_ressource("Salle Imam Zarruq") == salle_de_ressource("Salle Imam Zarrouq")

    def test_une_autre_salle_de_l_institut_tombe_dans_autre(self):
        assert salle_de_ressource("Le Kouttâb-3-Salle de conférence (60)") == "autre"

    def test_ce_qui_n_est_pas_une_salle_ne_rend_rien(self):
        # Sinon « 55 rue Charles Delescluze » deviendrait une colonne.
        assert salle_de_ressource("le kouttab") is None
        assert salle_de_ressource("55 rue Charles Delescluze, 93170 Bagnolet") is None
        assert salle_de_ressource(None) is None

    def test_toutes_les_cles_rendues_sont_des_colonnes_connues(self):
        for libelle in ("Salle Imam Maziri", "Salle de conférence", "Salle Imam Nafi'"):
            assert salle_de_ressource(libelle) in SALLES


class TestSalleReservee:
    def test_le_participant_ressource_fait_foi(self):
        evenement = {
            "location": "le kouttab",
            "attendees": [
                {"email": "prof@lekouttab.com"},
                {
                    "email": "c_188@resource.calendar.google.com",
                    "displayName": "Le Kouttâb-3-Salle Imam Maziri (50)",
                    "resource": True,
                },
            ],
        }
        assert salle_reservee(evenement) == "maziri"

    def test_le_lieu_sert_de_repli_s_il_nomme_une_des_trois_salles(self):
        assert salle_reservee({"location": "Le Kouttâb-3-Salle Imam Nafi' (25)"}) == "nafi"

    def test_un_lieu_en_texte_libre_ne_vaut_pas_reservation(self):
        # Les trois quarts des événements sont dans ce cas : c'est la
        # correspondance saisie dans l'application qui prendra le relais.
        assert salle_reservee({"location": "le kouttab"}) is None
        assert salle_reservee({}) is None

    def test_une_salle_inconnue_ecrite_a_la_main_ne_vaut_pas_reservation(self):
        """« Salle 2 » est un mot tapé dans un champ libre, pas une pièce réservée.

        La nuance porte : une ressource Google inconnue tombe dans « Autre »
        parce que quelqu'un a bel et bien bloqué une pièce ; un texte libre ne
        bloque rien, et le présenter comme une réservation enverrait un
        enseignant devant une porte occupée.
        """
        assert salle_reservee({"location": "Salle 2"}) is None
        ressource = {
            "attendees": [{"displayName": "Le Kouttâb-3-Salle de réunion", "resource": True}]
        }
        assert salle_reservee(ressource) == "autre"

    def test_un_participant_humain_n_est_jamais_une_salle(self):
        evenement = {"attendees": [{"displayName": "Salle Imam Maziri", "email": "a@b.fr"}]}
        assert salle_reservee(evenement) is None


class TestNumeroDeSeance:
    def test_la_propriete_privee_fait_foi(self):
        evenement = {
            "summary": "cours 05",
            "extendedProperties": {"private": {"numero": "05", "serie": "coran_enfants_3"}},
        }
        assert numero_de(evenement) == "05"

    def test_le_titre_sert_de_repli(self):
        assert numero_de({"summary": "cours 19"}) == "19"
        assert numero_de({"summary": "Cours 7"}) == "7"

    def test_la_propriete_l_emporte_sur_le_titre(self):
        evenement = {
            "summary": "cours 99",
            "extendedProperties": {"private": {"numero": "05"}},
        }
        assert numero_de(evenement) == "05"

    def test_ce_qui_n_est_pas_une_seance_n_a_pas_de_numero(self):
        # Permanences, réunions, « Hafiz famille » : la carte omet le numéro
        # plutôt que d'en inventer un.
        assert numero_de({"summary": "Permanence administrative (paiement) (Karima T.)"}) is None
        assert numero_de({"summary": "Hafiz famille"}) is None
        assert numero_de({}) is None

    def test_une_propriete_vide_retombe_sur_le_titre(self):
        evenement = {"summary": "cours 12", "extendedProperties": {"private": {"numero": "  "}}}
        assert numero_de(evenement) == "12"
