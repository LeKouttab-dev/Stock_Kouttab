"""Les salles de l'emploi du temps : d'ou elles viennent, et qui les regle.

Le point sensible est l'**ordre de resolution**. Trois quarts des cours ne
reservent aucune salle dans Google : l'application comble avec la salle
habituelle de l'agenda. Mais une habitude n'est pas une reservation, et l'API
doit toujours dire laquelle des deux elle sert — sans quoi l'ecran enverrait
quelqu'un devant une porte occupee.

Aucun appel ne sort vers Google : le client est remplace par un double.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import calendrier
from app.services import google_calendar as google_service

pytestmark = pytest.mark.integration


AGENDA_CORAN = {
    "id": "coran@group.calendar.google.com",
    "summary": "Coran - enfants 1 U.soundousse 2026/2027",
    "backgroundColor": "#4986e7",
    "timeZone": "Europe/Paris",
}
AGENDA_SI = {
    "id": "si@group.calendar.google.com",
    "summary": "SI - Adorations 2026/2027",
    "backgroundColor": "#f83a22",
    "timeZone": "Europe/Paris",
}

# Reserve une salle dans Google, comme 24 % des evenements reels.
EVENEMENT_AVEC_SALLE = {
    "id": "evt-si",
    "summary": "cours 06",
    "start": {"dateTime": "2026-10-19T20:00:00+02:00"},
    "end": {"dateTime": "2026-10-19T22:00:00+02:00"},
    "attendees": [
        {"email": "prof@lekouttab.com"},
        {
            "email": "c_188@resource.calendar.google.com",
            "displayName": "Le Kouttâb-3-Salle Imam Maziri (50)",
            "resource": True,
        },
    ],
    "extendedProperties": {"private": {"numero": "06", "serie": "si_adorations"}},
}
# N'en reserve aucune, comme les trois quarts restants.
EVENEMENT_SANS_SALLE = {
    "id": "evt-coran",
    "summary": "cours 19",
    "start": {"dateTime": "2026-10-20T17:30:00+02:00"},
    "end": {"dateTime": "2026-10-20T18:30:00+02:00"},
    "extendedProperties": {"private": {"numero": "19"}},
}

FENETRE = {"debut": "2026-10-13T00:00:00+02:00", "fin": "2026-10-27T00:00:00+02:00"}


class _ClientDouble:
    async def lister_agendas(self) -> list[dict[str, Any]]:
        return [AGENDA_CORAN, AGENDA_SI]

    async def lister_evenements(self, calendar_id: str, debut, fin) -> list[dict[str, Any]]:
        if calendar_id == AGENDA_SI["id"]:
            return [EVENEMENT_AVEC_SALLE]
        return [EVENEMENT_SANS_SALLE]


@pytest.fixture()
def google(monkeypatch) -> _ClientDouble:
    double = _ClientDouble()
    monkeypatch.setattr(calendrier, "get_google_calendar_client", lambda *a, **k: double)
    monkeypatch.setattr(settings, "google_calendar_restricted_raw", "", raising=False)
    monkeypatch.setattr(settings, "google_service_account_json", "{}", raising=False)
    monkeypatch.setattr(settings, "google_calendar_subject", "admin@lekouttab.com", raising=False)
    google_service._cache._valeurs.clear()
    return double


def _evenements(client: TestClient, user, auth_headers) -> dict[str, dict]:
    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(user))
    assert reponse.status_code == 200, reponse.text
    return {e["id"]: e for e in reponse.json()["evenements"]}


def _regler(client, super_admin_user, auth_headers, agenda_id, **champs):
    return client.put(
        "/api/v1/calendar/reglages-agendas",
        json={"reglages": {agenda_id: champs}},
        headers=auth_headers(super_admin_user),
    )


class TestOrdreDeResolution:
    def test_une_salle_reservee_dans_google_est_annoncee_comme_telle(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        evenements = _evenements(client, super_admin_user, auth_headers)
        evt = evenements["evt-si"]
        assert evt["salle"] == "maziri"
        assert evt["salle_source"] == "google"
        assert evt["salle_libelle"] == "Imam Maziri"

    def test_sans_reservation_ni_reglage_le_cours_va_en_maziri_par_defaut(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        """Il n'y a plus de colonne « Autre » : le défaut est Maziri.

        Mais l'API dit `defaut`, jamais `google` ni `correspondance` — sans
        quoi la colonne Maziri afficherait comme bloqués des créneaux que
        personne n'a posés.
        """
        evt = _evenements(client, super_admin_user, auth_headers)["evt-coran"]
        assert evt["salle"] == "maziri"
        assert evt["salle_source"] == "defaut"

    def test_le_reglage_comble_les_evenements_sans_reservation(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(client, super_admin_user, auth_headers, AGENDA_CORAN["id"], salle="nafi")
        evt = _evenements(client, super_admin_user, auth_headers)["evt-coran"]
        assert evt["salle"] == "nafi"
        # Et surtout : l'ecran doit pouvoir dire que c'est une habitude.
        assert evt["salle_source"] == "correspondance"

    def test_google_l_emporte_sur_le_reglage(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        """Une reservation reelle ne se fait jamais ecraser par une habitude."""
        _regler(client, super_admin_user, auth_headers, AGENDA_SI["id"], salle="zarrouq")
        evt = _evenements(client, super_admin_user, auth_headers)["evt-si"]
        assert evt["salle"] == "maziri"
        assert evt["salle_source"] == "google"


class TestNumeroEtLibelle:
    def test_le_numero_de_seance_remonte(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        evenements = _evenements(client, super_admin_user, auth_headers)
        assert evenements["evt-si"]["numero"] == "06"
        assert evenements["evt-coran"]["numero"] == "19"

    def test_le_nom_court_et_l_enseignant_accompagnent_l_evenement(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        evt = _evenements(client, super_admin_user, auth_headers)["evt-coran"]
        assert evt["nom_court"] == "Coran ENF 1"
        assert evt["enseignant"] == "U. Soundousse"
        # Le titre Google brut reste disponible : c'est lui que porte la fiche.
        assert evt["titre"] == "cours 19"

    def test_un_nom_court_saisi_l_emporte_sur_la_regle(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(
            client, super_admin_user, auth_headers, AGENDA_CORAN["id"], nom_court="Coran P'tits"
        )
        evt = _evenements(client, super_admin_user, auth_headers)["evt-coran"]
        assert evt["nom_court"] == "Coran P'tits"

    def test_vider_le_nom_court_rend_la_main_a_la_regle(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(client, super_admin_user, auth_headers, AGENDA_CORAN["id"], nom_court="Bidule")
        _regler(client, super_admin_user, auth_headers, AGENDA_CORAN["id"], nom_court=None)
        evt = _evenements(client, super_admin_user, auth_headers)["evt-coran"]
        assert evt["nom_court"] == "Coran ENF 1"

    def test_la_liste_des_agendas_porte_aussi_le_nom_court(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        reponse = client.get("/api/v1/calendar/agendas", headers=auth_headers(super_admin_user))
        par_id = {a["id"]: a for a in reponse.json()}
        assert par_id[AGENDA_CORAN["id"]]["nom_court"] == "Coran ENF 1"
        assert par_id[AGENDA_CORAN["id"]]["enseignant"] == "U. Soundousse"


class TestAccesAuxReglages:
    def test_seul_le_super_admin_lit_et_ecrit_les_reglages(
        self, client: TestClient, admin_benevoles_user, compta_user, benevole_user, auth_headers
    ):
        for compte in (admin_benevoles_user, compta_user, benevole_user):
            lecture = client.get("/api/v1/calendar/reglages-agendas", headers=auth_headers(compte))
            assert lecture.status_code == 403, compte.role
            ecriture = client.put(
                "/api/v1/calendar/reglages-agendas",
                json={"reglages": {"a@b": {"salle": "nafi"}}},
                headers=auth_headers(compte),
            )
            assert ecriture.status_code == 403, compte.role

    def test_sans_authentification_rien_ne_sort(self, client: TestClient):
        assert client.get("/api/v1/calendar/reglages-agendas").status_code == 401


class TestEcritureDesReglages:
    def test_une_salle_inconnue_est_refusee_et_rien_n_est_ecrit(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        """Une salle hors referentiel creerait une colonne fantome."""
        reponse = client.put(
            "/api/v1/calendar/reglages-agendas",
            json={
                "reglages": {
                    AGENDA_CORAN["id"]: {"salle": "nafi"},
                    AGENDA_SI["id"]: {"salle": "cafeteria"},
                }
            },
            headers=auth_headers(super_admin_user),
        )
        assert reponse.status_code == 422
        # Tout ou rien : le reglage valide du meme lot ne doit pas etre passe.
        apres = client.get(
            "/api/v1/calendar/reglages-agendas", headers=auth_headers(super_admin_user)
        ).json()
        assert apres["reglages"] == []

    def test_ce_qui_n_est_pas_envoye_n_est_pas_touche(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(client, super_admin_user, auth_headers, AGENDA_CORAN["id"], salle="nafi")
        _regler(client, super_admin_user, auth_headers, AGENDA_SI["id"], salle="maziri")
        etat = client.get(
            "/api/v1/calendar/reglages-agendas", headers=auth_headers(super_admin_user)
        ).json()
        assert {r["agenda_id"]: r["salle"] for r in etat["reglages"]} == {
            AGENDA_CORAN["id"]: "nafi",
            AGENDA_SI["id"]: "maziri",
        }

    def test_vider_les_deux_champs_retire_la_ligne(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(client, super_admin_user, auth_headers, AGENDA_CORAN["id"], salle="nafi")
        _regler(
            client, super_admin_user, auth_headers, AGENDA_CORAN["id"], salle=None, nom_court=None
        )
        etat = client.get(
            "/api/v1/calendar/reglages-agendas", headers=auth_headers(super_admin_user)
        ).json()
        assert etat["reglages"] == []

    def test_le_referentiel_des_salles_est_servi_et_non_recopie(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        """L'ecran et la grille doivent lire la meme liste de colonnes."""
        etat = client.get(
            "/api/v1/calendar/reglages-agendas", headers=auth_headers(super_admin_user)
        ).json()
        assert list(etat["salles"]) == ["maziri", "nafi", "zarrouq"]

        evenements = client.get(
            "/api/v1/calendar", params=FENETRE, headers=auth_headers(super_admin_user)
        ).json()
        assert evenements["salles"] == etat["salles"]


class TestDeductionDepuisGoogle:
    def test_la_deduction_propose_sans_rien_enregistrer(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        reponse = client.get(
            "/api/v1/calendar/reglages-agendas/deduire",
            params={"jours": 365},
            headers=auth_headers(super_admin_user),
        )
        assert reponse.status_code == 200, reponse.text
        propositions = {p["agenda_id"]: p for p in reponse.json()}
        # Seul l'agenda qui reserve vraiment une salle est propose.
        assert AGENDA_SI["id"] in propositions
        assert propositions[AGENDA_SI["id"]]["salle"] == "maziri"
        assert AGENDA_CORAN["id"] not in propositions

        # Rien n'a ete ecrit : la proposition remplit un formulaire, elle ne
        # decide pas a la place d'une personne.
        etat = client.get(
            "/api/v1/calendar/reglages-agendas", headers=auth_headers(super_admin_user)
        ).json()
        assert etat["reglages"] == []

    def test_la_deduction_est_reservee_au_super_admin(
        self, client: TestClient, compta_user, auth_headers
    ):
        reponse = client.get(
            "/api/v1/calendar/reglages-agendas/deduire", headers=auth_headers(compta_user)
        )
        assert reponse.status_code == 403


class TestEtat:
    def test_l_etat_compte_les_agendas_sans_salle(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        """Sinon la grille entasse tout dans « Autre » sans qu'on sache pourquoi."""
        etat = client.get("/api/v1/calendar/etat", headers=auth_headers(super_admin_user)).json()
        assert etat["agendas_sans_salle"] == 2

        _regler(client, super_admin_user, auth_headers, AGENDA_CORAN["id"], salle="nafi")
        etat = client.get("/api/v1/calendar/etat", headers=auth_headers(super_admin_user)).json()
        assert etat["agendas_sans_salle"] == 1


class TestCategories:
    def _agendas(self, client, user, auth_headers) -> dict[str, dict]:
        reponse = client.get("/api/v1/calendar/agendas", headers=auth_headers(user))
        return {a["id"]: a for a in reponse.json()}

    def test_la_categorie_est_deduite_du_nom(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        agendas = self._agendas(client, super_admin_user, auth_headers)
        assert agendas[AGENDA_CORAN["id"]]["categorie"] == "Coran"
        assert agendas[AGENDA_CORAN["id"]]["sous_categorie"] == "Coran enfants"
        assert agendas[AGENDA_SI["id"]]["categorie"] == "Sciences islamiques"
        # Le rang est servi : le front n'a pas à recopier l'ordre des catégories.
        assert (
            agendas[AGENDA_CORAN["id"]]["categorie_rang"]
            < agendas[AGENDA_SI["id"]]["categorie_rang"]
        )

    def test_une_categorie_saisie_l_emporte_et_vider_rend_la_main(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(
            client,
            super_admin_user,
            auth_headers,
            AGENDA_SI["id"],
            categorie="Coran",
            sous_categorie="Coran adultes",
        )
        agenda = self._agendas(client, super_admin_user, auth_headers)[AGENDA_SI["id"]]
        assert (agenda["categorie"], agenda["sous_categorie"]) == ("Coran", "Coran adultes")

        _regler(client, super_admin_user, auth_headers, AGENDA_SI["id"], categorie=None)
        agenda = self._agendas(client, super_admin_user, auth_headers)[AGENDA_SI["id"]]
        assert agenda["categorie"] == "Sciences islamiques"

    def test_une_categorie_saisie_inconnue_se_range_avant_autres(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        _regler(client, super_admin_user, auth_headers, AGENDA_SI["id"], categorie="Événements")
        agenda = self._agendas(client, super_admin_user, auth_headers)[AGENDA_SI["id"]]
        assert agenda["categorie"] == "Événements"
        # Après les catégories connues, avant « Autres ».
        from app.services.calendrier_salles import ORDRE_CATEGORIES

        assert agenda["categorie_rang"] == len(ORDRE_CATEGORIES)

    def test_une_categorie_trop_longue_est_refusee(
        self, client: TestClient, super_admin_user, auth_headers, google
    ):
        reponse = _regler(
            client, super_admin_user, auth_headers, AGENDA_SI["id"], categorie="x" * 65
        )
        assert reponse.status_code == 422
