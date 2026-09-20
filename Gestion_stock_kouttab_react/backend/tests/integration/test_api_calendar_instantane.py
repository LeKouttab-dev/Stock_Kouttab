"""L'instantané figé, servi tant que Google n'est pas branché.

Deux propriétés comptent plus que le contenu du relevé :

1. **Google l'emporte toujours.** Un fichier resté sur le disque après la
   configuration masquerait la source vivante, et se tairait à chaque horaire
   corrigé dans Google.
2. **L'écran sait que c'est figé.** Un planning daté qui se présente comme le
   direct ferait manquer un cours déplacé.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import calendar as calendar_endpoint
from app.core.config import settings
from app.services import calendrier_instantane, google_calendar


pytestmark = pytest.mark.integration

# La fenêtre du relevé livré (cf. app/ressources/calendrier_instantane.json).
FENETRE = {
    "debut": "2026-09-20T00:00:00+02:00",
    "fin": "2026-10-18T00:00:00+02:00",
}


@pytest.fixture()
def sans_google(monkeypatch):
    """Aucune clé, aucun compte impersonné : l'état de la production ce soir."""
    monkeypatch.setattr(settings, "google_service_account_json", "", raising=False)
    monkeypatch.setattr(settings, "google_service_account_file", "", raising=False)
    monkeypatch.setattr(settings, "google_calendar_subject", "", raising=False)
    monkeypatch.setattr(settings, "google_calendar_restricted_raw", "", raising=False)
    # Le cache de `google_calendar` vit dans le processus : sans purge, un test
    # precedent laisserait ses agendas et l'appel repondrait 200 la ou on
    # attend « pas configure ».
    google_calendar._cache._valeurs.clear()


def test_le_fichier_livre_est_lisible_et_non_vide():
    donnees = calendrier_instantane.charger()
    assert donnees is not None, "l'instantané doit être livré avec l'application"
    assert len(donnees["evenements"]) > 100
    assert donnees["genere_le"]


def test_psy_rdv_n_est_pas_dans_le_fichier_versionne():
    """Des rendez-vous de santé dans l'historique Git ne s'effacent plus."""
    donnees = calendrier_instantane.charger()
    assert donnees is not None
    noms = " ".join(a["nom"] for a in donnees["agendas"]).lower()
    assert "psy" not in noms


def test_sans_google_l_onglet_sert_l_instantane(
    client: TestClient, admin_benevoles_user, auth_headers, sans_google
):
    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(admin_benevoles_user))
    assert reponse.status_code == 200, reponse.text
    charge = reponse.json()
    assert charge["instantane"] is True
    assert charge["genere_le"]
    assert len(charge["evenements"]) > 100
    # Les agendas sortent aussi du relevé, sinon la liste latérale serait vide
    # alors que la grille est pleine.
    agendas = client.get("/api/v1/calendar/agendas", headers=auth_headers(admin_benevoles_user))
    assert len(agendas.json()) > 30


def test_les_evenements_de_l_instantane_sont_dans_la_fenetre_demandee(
    client: TestClient, admin_benevoles_user, auth_headers, sans_google
):
    """Une semaine demandée ne rend pas les quatre du relevé."""
    reponse = client.get(
        "/api/v1/calendar",
        params={"debut": "2026-09-21T00:00:00+02:00", "fin": "2026-09-28T00:00:00+02:00"},
        headers=auth_headers(admin_benevoles_user),
    )
    evenements = reponse.json()["evenements"]
    assert evenements
    debut = datetime.fromisoformat("2026-09-21T00:00:00+02:00")
    fin = datetime.fromisoformat("2026-09-28T00:00:00+02:00")
    for evenement in evenements:
        commence = datetime.fromisoformat(evenement["debut"])
        assert debut - timedelta(days=2) <= commence <= fin


def test_un_agenda_restreint_reste_filtre_sur_l_instantane(
    client: TestClient, admin_benevoles_user, super_admin_user, auth_headers, monkeypatch, sans_google
):
    """Le filtrage ne dépend pas de la source : c'est le même chemin de code."""
    donnees = calendrier_instantane.charger()
    assert donnees is not None
    cible = donnees["agendas"][0]["id"]
    monkeypatch.setattr(settings, "google_calendar_restricted_raw", cible, raising=False)

    pour_benevole = client.get(
        "/api/v1/calendar/agendas", headers=auth_headers(admin_benevoles_user)
    ).json()
    pour_super_admin = client.get(
        "/api/v1/calendar/agendas", headers=auth_headers(super_admin_user)
    ).json()
    assert cible not in [a["id"] for a in pour_benevole]
    assert cible in [a["id"] for a in pour_super_admin]


def test_google_configure_reprend_la_main_sur_l_instantane(
    client: TestClient, admin_benevoles_user, auth_headers, monkeypatch
):
    """Le fichier est toujours là, mais c'est Google qui répond."""

    class _Double:
        async def lister_agendas(self):
            return [{"id": "direct@group.calendar.google.com", "summary": "Direct"}]

        async def lister_evenements(self, calendar_id, debut, fin):
            return [
                {
                    "id": "evt-direct",
                    "summary": "Cours ajouté après le relevé",
                    "start": {"dateTime": "2026-09-21T10:00:00+02:00"},
                    "end": {"dateTime": "2026-09-21T11:00:00+02:00"},
                }
            ]

    monkeypatch.setattr(settings, "google_service_account_json", "{}", raising=False)
    monkeypatch.setattr(
        settings, "google_calendar_subject", "admin@lekouttab.com", raising=False
    )
    monkeypatch.setattr(settings, "google_calendar_restricted_raw", "", raising=False)
    monkeypatch.setattr(
        calendar_endpoint, "get_google_calendar_client", lambda *a, **k: _Double()
    )
    google_calendar._cache._valeurs.clear()

    assert calendrier_instantane.disponible() is True
    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(admin_benevoles_user))
    charge = reponse.json()
    assert charge["instantane"] is False
    assert [e["titre"] for e in charge["evenements"]] == ["Cours ajouté après le relevé"]


def test_l_etat_annonce_l_instantane_au_super_admin(
    client: TestClient, super_admin_user, auth_headers, sans_google
):
    reponse = client.get("/api/v1/calendar/etat", headers=auth_headers(super_admin_user))
    etat = reponse.json()
    assert etat["configure"] is False
    assert etat["instantane"] is True
    assert etat["genere_le"]


def test_un_instantane_absent_redonne_le_message_de_configuration(
    client: TestClient, admin_benevoles_user, auth_headers, monkeypatch, sans_google
):
    """Une fois le fichier supprimé et Google absent, on dit ce qui manque."""
    monkeypatch.setattr(calendrier_instantane, "charger", lambda: None)
    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(admin_benevoles_user))
    assert reponse.status_code == 503
    assert reponse.json()["code"] == "EXT_6040"


def test_les_horaires_gardent_leur_fuseau(
    client: TestClient, admin_benevoles_user, auth_headers, sans_google
):
    """Un cours de 17 h reste à 17 h : les offsets du relevé sont servis tels quels."""
    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(admin_benevoles_user))
    debuts = [e["debut"] for e in reponse.json()["evenements"]]
    assert all("+0" in d or "Z" in d or len(d) == 10 for d in debuts)
    minuit_utc = [d for d in debuts if d.endswith("Z")]
    assert not minuit_utc, "aucune date ne doit avoir été reconvertie en UTC"
