"""Le calendrier de l'institut, lu par gestion.lekouttab.fr.

POST /api/v1/auth/sso/calendrier — lecture serveur a serveur, jeton dedie
(typ 'sso-calendrier', 60 s) signe du secret partage. L'outil de gestion s'en
sert pour son propre onglet Calendrier : une seule connexion Google a
configurer, un seul cache, un seul endroit a corriger.

Trois proprietes sont verrouillees ici :

 1. **La fenetre est DANS le jeton signe**, jamais dans le corps. Sans cela,
    quiconque tient le secret balaierait l'annee en changeant un parametre —
    meme doctrine que pour les depenses.
 2. **Les agendas reserves ne traversent jamais la frontiere**, quel que soit
    le demandeur. Les servir reviendrait a confier leur filtrage a l'autre
    outil, alors qu'ils portent des donnees de sante.
 3. **Le jeton d'un autre usage ne vaut rien ici.** Une pastille ne doit pas
    ouvrir le planning de l'institut.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.api.v1.endpoints import auth as auth_endpoint
from app.core.config import settings
from app.services import calendrier, google_calendar


pytestmark = pytest.mark.integration

SECRET_TEST = "secret-partage-de-test-suffisamment-long-1234"
URL = "/api/v1/auth/sso/calendrier"

AGENDA_OUVERT = {
    "id": "cours@group.calendar.google.com",
    "summary": "Coran - enfants 1",
    "backgroundColor": "#0b8043",
}
AGENDA_RESTREINT = {
    "id": "psy@group.calendar.google.com",
    "summary": "PSY RDV",
    "backgroundColor": "#8e24aa",
}

DEBUT = "2026-09-21T00:00:00+02:00"
FIN = "2026-09-28T00:00:00+02:00"


class _ClientDouble:
    def __init__(self) -> None:
        self.agendas_demandes: list[str] = []

    async def lister_agendas(self) -> list[dict[str, Any]]:
        return [AGENDA_OUVERT, AGENDA_RESTREINT]

    async def lister_evenements(self, calendar_id: str, debut, fin) -> list[dict[str, Any]]:
        self.agendas_demandes.append(calendar_id)
        titre = "Cours de Coran" if calendar_id == AGENDA_OUVERT["id"] else "RDV psychologue"
        return [
            {
                "id": f"evt-{calendar_id[:3]}",
                "summary": titre,
                "start": {"dateTime": "2026-09-21T17:00:00+02:00"},
                "end": {"dateTime": "2026-09-21T18:30:00+02:00"},
            }
        ]


@pytest.fixture()
def pont(monkeypatch) -> _ClientDouble:
    """Secret partage actif, Google repute configure, agenda PSY reserve."""
    double = _ClientDouble()
    monkeypatch.setattr(settings, "sso_shared_secret", SECRET_TEST)
    monkeypatch.setattr(settings, "google_service_account_json", "{}", raising=False)
    monkeypatch.setattr(
        settings, "google_calendar_subject", "admin@lekouttab.com", raising=False
    )
    monkeypatch.setattr(
        settings, "google_calendar_restricted_raw", AGENDA_RESTREINT["id"], raising=False
    )
    monkeypatch.setattr(
        calendrier, "get_google_calendar_client", lambda *a, **k: double
    )
    google_calendar._cache._valeurs.clear()
    return double


def _jeton(
    secret: str = SECRET_TEST,
    *,
    email: str = "staff@example.com",
    typ: str = "sso-calendrier",
    debut: str | None = DEBUT,
    fin: str | None = FIN,
    aud: str = "stock.lekouttab.fr",
    iss: str = "gestion.lekouttab.fr",
    vie: int = 45,
) -> str:
    maintenant = int(time.time())
    charge = {
        "iss": iss,
        "aud": aud,
        "typ": typ,
        "jti": uuid.uuid4().hex,
        "iat": maintenant,
        "exp": maintenant + vie,
        "email": email,
        "debut": debut,
        "fin": fin,
    }
    return jose_jwt.encode(charge, secret, algorithm="HS256")


def test_le_pont_sert_le_planning(client: TestClient, pont):
    reponse = client.post(URL, json={"token": _jeton()})
    assert reponse.status_code == 200, reponse.text
    charge = reponse.json()
    assert [a["nom"] for a in charge["agendas"]] == ["Coran - enfants 1"]
    assert [e["titre"] for e in charge["evenements"]] == ["Cours de Coran"]
    assert charge["evenements"][0]["agenda_nom"] == "Coran - enfants 1"
    assert charge["instantane"] is False


def test_l_agenda_reserve_ne_traverse_jamais_la_frontiere(client: TestClient, pont):
    """Ni dans la liste, ni dans les evenements, ni meme interroge chez Google."""
    charge = client.post(URL, json={"token": _jeton()}).json()
    assert AGENDA_RESTREINT["id"] not in [a["id"] for a in charge["agendas"]]
    assert "RDV psychologue" not in [e["titre"] for e in charge["evenements"]]
    assert AGENDA_RESTREINT["id"] not in pont.agendas_demandes


def test_un_jeton_de_pastille_n_ouvre_pas_le_planning(client: TestClient, pont):
    reponse = client.post(URL, json={"token": _jeton(typ="sso-pastille")})
    assert reponse.status_code == 401
    assert reponse.json()["code"] == "AUTH_1011"


def test_un_autre_secret_est_refuse(client: TestClient, pont):
    reponse = client.post(URL, json={"token": _jeton(secret="un-autre-secret-tout-aussi-long-42")})
    assert reponse.status_code == 401


def test_une_fenetre_absente_du_jeton_est_refusee(client: TestClient, pont):
    """La fenetre vient du jeton signe : rien a substituer dans le corps."""
    reponse = client.post(URL, json={"token": _jeton(debut=None, fin=None)})
    assert reponse.status_code == 422


def test_une_fenetre_demesuree_est_refusee(client: TestClient, pont):
    reponse = client.post(
        URL,
        json={"token": _jeton(debut="2020-01-01T00:00:00+01:00", fin="2030-01-01T00:00:00+01:00")},
    )
    assert reponse.status_code == 422


def test_sans_secret_configure_l_endpoint_n_existe_pas(client: TestClient, monkeypatch, pont):
    """Meme parti que le passage signe : la fonctionnalite coupee est invisible."""
    monkeypatch.setattr(settings, "sso_shared_secret", "")
    reponse = client.post(URL, json={"token": _jeton()})
    assert reponse.status_code == 404


def test_le_releve_fige_est_annonce_comme_tel(client: TestClient, monkeypatch, pont):
    """Gestion doit pouvoir afficher la meme banniere datee que nous."""
    monkeypatch.setattr(settings, "google_service_account_json", "", raising=False)
    monkeypatch.setattr(settings, "google_calendar_subject", "", raising=False)
    google_calendar._cache._valeurs.clear()

    charge = client.post(URL, json={"token": _jeton()}).json()
    assert charge["instantane"] is True
    assert charge["genere_le"]
    assert charge["evenements"], "le releve livre couvre cette semaine-la"
