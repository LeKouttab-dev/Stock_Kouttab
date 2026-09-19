"""Le client Google Agenda : la cle, l'assertion signee, et ce qui est demande.

Aucun appel ne sort : le transport httpx est remplace par un double qui rend
des reponses fabriquees. Ce qui est verifie ici, c'est ce que le serveur ENVOIE
a Google — la partie qu'aucun test d'API ne couvre, parce qu'elle s'arrete a la
frontiere du reseau.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.services import google_calendar as service


pytestmark = pytest.mark.unit


def _cle_privee() -> str:
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return cle.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def _compte_de_service() -> dict[str, str]:
    return {
        "type": "service_account",
        "client_email": "kouttab-agenda@projet.iam.gserviceaccount.com",
        "private_key": _cle_privee(),
        "private_key_id": "cle-1",
    }


def _settings(**extra) -> Settings:
    base = {
        "GOOGLE_CALENDAR_SUBJECT": "admin@lekouttab.com",
        "GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(_compte_de_service()),
    }
    base.update(extra)
    return Settings(**base)  # type: ignore[arg-type]


class _Transport(httpx.MockTransport):
    """Double du reseau : retient les requetes et rend des reponses plausibles."""

    def __init__(self) -> None:
        self.requetes: list[httpx.Request] = []
        super().__init__(self._repondre)

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if requete.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200, json={"access_token": "jeton-de-test", "expires_in": 3600}
            )
        return httpx.Response(200, json={"items": [{"id": "evt"}]})


@pytest.fixture()
def reseau(monkeypatch) -> _Transport:
    transport = _Transport()
    original = httpx.AsyncClient.__init__

    def _avec_double(self, *args, **kwargs):
        kwargs["transport"] = transport
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", _avec_double)
    return transport


@pytest.mark.asyncio
async def test_l_assertion_porte_le_compte_impersonne_et_le_scope_lecture(reseau):
    """Sans `sub`, le compte de service n'a que ses propres agendas : aucun."""
    client = service.GoogleCalendarClient(_settings())
    assert await client._jeton() == "jeton-de-test"

    envoi = reseau.requetes[0]
    assert str(envoi.url) == "https://oauth2.googleapis.com/token"
    corps = dict(
        paire.split("=", 1) for paire in envoi.content.decode().split("&")
    )
    assert corps["grant_type"] == "urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer"

    claims = jwt.get_unverified_claims(corps["assertion"])
    assert claims["sub"] == "admin@lekouttab.com"
    # Un seul scope, en lecture : la delegation donne tout ce que voit le
    # compte impersonne, l'ecriture comprise si on l'accorde.
    assert claims["scope"] == "https://www.googleapis.com/auth/calendar.readonly"
    assert claims["aud"] == "https://oauth2.googleapis.com/token"


@pytest.mark.asyncio
async def test_le_jeton_est_reutilise_entre_deux_appels(reseau):
    """Il vaut une heure ; le redemander a chaque agenda ferait 42 echanges."""
    client = service.GoogleCalendarClient(_settings())
    await client._jeton()
    await client._jeton()
    jetons = [r for r in reseau.requetes if r.url.host == "oauth2.googleapis.com"]
    assert len(jetons) == 1


@pytest.mark.asyncio
async def test_l_identifiant_d_agenda_est_encode_dans_le_chemin(reseau):
    """C'est une adresse : « @ » et « . » sortiraient du segment de chemin."""
    client = service.GoogleCalendarClient(_settings())
    await client.lister_evenements(
        "psy@group.calendar.google.com",
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 30, tzinfo=timezone.utc),
    )
    appel = reseau.requetes[-1]
    assert "psy%40group.calendar.google.com" in str(appel.url)
    # Les recurrences sont developpees par Google : sans cela, un cours
    # hebdomadaire n'arriverait qu'une fois, avec sa regle a interpreter.
    assert appel.url.params["singleEvents"] == "true"


def test_la_cle_est_acceptee_en_base64(reseau):
    """Le JSON brut contient des sauts de ligne : colle dans un .env, il le casse."""
    infos = _compte_de_service()
    encode = base64.b64encode(json.dumps(infos).encode()).decode()
    client = service.GoogleCalendarClient(
        _settings(GOOGLE_SERVICE_ACCOUNT_JSON=encode)
    )
    assert client._compte_de_service()["client_email"] == infos["client_email"]


def test_sans_compte_impersonne_la_fonctionnalite_est_dite_non_configuree():
    """Une cle sans `subject` ne voit aucun agenda : ce n'est pas « aucun evenement »."""
    client = service.GoogleCalendarClient(_settings(GOOGLE_CALENDAR_SUBJECT=""))
    with pytest.raises(AppException) as erreur:
        client._compte_de_service()
    assert erreur.value.code is ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED


def test_une_cle_illisible_ne_passe_pas_pour_une_panne_reseau():
    client = service.GoogleCalendarClient(
        _settings(GOOGLE_SERVICE_ACCOUNT_JSON="ceci n'est ni du json ni du base64")
    )
    with pytest.raises(AppException) as erreur:
        client._compte_de_service()
    assert erreur.value.code is ErrorCode.GOOGLE_CALENDAR_NOT_CONFIGURED
