"""Onglet Calendrier : ce que chaque role a le droit de lire chez Google.

Le point sensible n'est pas l'affichage, c'est le filtrage. Un agenda declare
restreint porte des rendez-vous de sante ; il ne doit sortir de l'API que pour
un Super Admin, y compris quand son identifiant est demande explicitement dans
l'URL — le menu de l'interface ne protege rien.

Aucun appel ne sort vers Google : le client est remplace par un double.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import calendar as calendar_endpoint
from app.core.config import settings
from app.services import google_calendar as google_service


pytestmark = pytest.mark.integration


AGENDA_PUBLIC = {
    "id": "cours@group.calendar.google.com",
    "summary": "Coran - enfants 1",
    "backgroundColor": "#0b8043",
    "foregroundColor": "#ffffff",
    "timeZone": "Europe/Paris",
}
AGENDA_RESTREINT = {
    "id": "psy@group.calendar.google.com",
    "summary": "PSY RDV",
    "backgroundColor": "#8e24aa",
    "timeZone": "Europe/Paris",
}

EVENEMENT = {
    "id": "evt-1",
    "summary": "Cours de Coran",
    "start": {"dateTime": "2026-09-21T17:00:00+02:00"},
    "end": {"dateTime": "2026-09-21T18:30:00+02:00"},
    "location": "Salle 2",
    "htmlLink": "https://calendar.google.com/evt-1",
    "status": "confirmed",
    "recurringEventId": "serie-1",
}
EVENEMENT_SENSIBLE = {
    "id": "evt-2",
    "summary": "RDV psychologue — famille B.",
    "start": {"dateTime": "2026-09-21T14:00:00+02:00"},
    "end": {"dateTime": "2026-09-21T15:00:00+02:00"},
}

FENETRE = {"debut": "2026-09-14T00:00:00+02:00", "fin": "2026-09-28T00:00:00+02:00"}


class _ClientDouble:
    """Double du client Google : compte ce qu'on lui demande."""

    def __init__(self) -> None:
        self.agendas_demandes: list[str] = []

    async def lister_agendas(self) -> list[dict[str, Any]]:
        return [AGENDA_PUBLIC, AGENDA_RESTREINT]

    async def lister_evenements(self, calendar_id: str, debut, fin) -> list[dict[str, Any]]:
        self.agendas_demandes.append(calendar_id)
        if calendar_id == AGENDA_RESTREINT["id"]:
            return [EVENEMENT_SENSIBLE]
        return [EVENEMENT]


@pytest.fixture()
def google(monkeypatch) -> _ClientDouble:
    double = _ClientDouble()
    monkeypatch.setattr(
        calendar_endpoint, "get_google_calendar_client", lambda *a, **k: double
    )
    monkeypatch.setattr(
        settings, "google_calendar_restricted_raw", AGENDA_RESTREINT["id"], raising=False
    )
    # Le cache est partage par le processus : sans purge, un test heriterait
    # des agendas d'un autre.
    google_service._cache._valeurs.clear()
    return double


def test_un_benevole_ne_voit_pas_l_agenda_restreint(client: TestClient, benevole_user, auth_headers, google):
    reponse = client.get("/api/v1/calendar/agendas", headers=auth_headers(benevole_user))
    assert reponse.status_code == 200, reponse.text
    identifiants = [a["id"] for a in reponse.json()]
    assert AGENDA_PUBLIC["id"] in identifiants
    assert AGENDA_RESTREINT["id"] not in identifiants


def test_le_super_admin_voit_l_agenda_restreint_et_son_etiquette(
    client: TestClient, super_admin_user, auth_headers, google
):
    reponse = client.get("/api/v1/calendar/agendas", headers=auth_headers(super_admin_user))
    assert reponse.status_code == 200
    par_id = {a["id"]: a for a in reponse.json()}
    assert par_id[AGENDA_RESTREINT["id"]]["restreint"] is True
    assert par_id[AGENDA_PUBLIC["id"]]["restreint"] is False


def test_demander_l_agenda_restreint_dans_l_url_ne_le_donne_pas(
    client: TestClient, compta_user, auth_headers, google
):
    """Le filtrage porte sur l'intersection, pas sur la liste demandee."""
    reponse = client.get(
        "/api/v1/calendar",
        params={**FENETRE, "agendas": [AGENDA_RESTREINT["id"]]},
        headers=auth_headers(compta_user),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["evenements"] == []
    # Et surtout : l'agenda n'a meme pas ete interroge chez Google.
    assert AGENDA_RESTREINT["id"] not in google.agendas_demandes


def test_les_evenements_sont_normalises(client: TestClient, benevole_user, auth_headers, google):
    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(benevole_user))
    assert reponse.status_code == 200, reponse.text
    evenements = reponse.json()["evenements"]
    assert len(evenements) == 1
    evenement = evenements[0]
    assert evenement["titre"] == "Cours de Coran"
    assert evenement["agenda_nom"] == AGENDA_PUBLIC["summary"]
    assert evenement["journee_entiere"] is False
    assert evenement["recurrent"] is True
    assert evenement["couleur"] == AGENDA_PUBLIC["backgroundColor"]
    assert evenement["lieu"] == "Salle 2"


def test_un_evenement_sans_titre_reste_affichable(
    client: TestClient, benevole_user, auth_headers, google, monkeypatch
):
    async def _sans_titre(calendar_id: str, debut, fin):
        return [{**EVENEMENT, "summary": None}]

    monkeypatch.setattr(google, "lister_evenements", _sans_titre)
    google_service._cache._valeurs.clear()

    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(benevole_user))
    assert reponse.json()["evenements"][0]["titre"] == "(Sans titre)"


def test_un_agenda_en_panne_ne_vide_pas_la_page(
    client: TestClient, super_admin_user, auth_headers, google, monkeypatch
):
    """Un agenda illisible est signale, les autres sont servis quand meme."""
    from app.core.errors import ErrorCode
    from app.core.exceptions import AppException

    async def _un_sur_deux_echoue(calendar_id: str, debut, fin):
        if calendar_id == AGENDA_RESTREINT["id"]:
            raise AppException(ErrorCode.GOOGLE_CALENDAR_API_ERROR)
        return [EVENEMENT]

    monkeypatch.setattr(google, "lister_evenements", _un_sur_deux_echoue)
    google_service._cache._valeurs.clear()

    reponse = client.get("/api/v1/calendar", params=FENETRE, headers=auth_headers(super_admin_user))
    assert reponse.status_code == 200, reponse.text
    charge = reponse.json()
    assert len(charge["evenements"]) == 1
    assert charge["agendas_en_erreur"] == [AGENDA_RESTREINT["summary"]]


def test_une_fenetre_trop_large_est_refusee(client: TestClient, benevole_user, auth_headers, google):
    reponse = client.get(
        "/api/v1/calendar",
        params={"debut": "2020-01-01T00:00:00+01:00", "fin": "2030-01-01T00:00:00+01:00"},
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 422


def test_sans_authentification_rien_ne_sort(client: TestClient, google):
    assert client.get("/api/v1/calendar/agendas").status_code == 401
    assert client.get("/api/v1/calendar", params=FENETRE).status_code == 401


def test_l_etat_est_reserve_au_super_admin(
    client: TestClient, compta_user, super_admin_user, auth_headers, google
):
    assert (
        client.get("/api/v1/calendar/etat", headers=auth_headers(compta_user)).status_code == 403
    )
    reponse = client.get("/api/v1/calendar/etat", headers=auth_headers(super_admin_user))
    assert reponse.status_code == 200
    # Sans cle de compte de service, l'etat dit « pas configure » plutot que
    # de laisser croire a un agenda vide.
    assert reponse.json()["configure"] is False
