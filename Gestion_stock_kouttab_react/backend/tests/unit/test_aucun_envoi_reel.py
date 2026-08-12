"""Garde-fou : la suite de tests ne doit joindre aucun serveur SMTP.

Ce n'est pas une precaution theorique. Le `.env` de developpement porte les
identifiants de la messagerie reelle de l'association, et la suite a longtemps
arrose la boite de la comptabilite de fausses pieces — « [Facture] EV(T) —
Gala d'ete 2026 » — a chaque execution, plusieurs fois par jour.

Deux causes, toutes deux couvertes ici :

1. `EMAIL_ENABLED` restait a `true`, valeur heritee du `.env` du poste ;
2. la fixture d'interception ne couvrait que `_send` (notifications), pas
   `_send_raw` (circuit comptable, celui qui porte les PDF).

Ces tests echouent si l'une ou l'autre protection saute.
"""

from __future__ import annotations

import inspect

import pytest

from app.core.config import settings
from app.services import email as email_service


pytestmark = pytest.mark.unit


def test_le_coupe_circuit_est_arme():
    """`EMAIL_ENABLED=false` : `_send_raw` sort avant tout acces au SMTP."""
    assert settings.email_enabled is False, (
        "EMAIL_ENABLED doit valoir false pendant les tests — sinon les envois "
        "partent vers le vrai serveur de l'association (cf. conftest.py)."
    )


def test_les_deux_chemins_d_envoi_sont_interceptes():
    """`_send` ET `_send_raw` : oublier le second est l'erreur historique."""
    for nom in ("_send", "_send_raw"):
        fonction = getattr(email_service, nom)
        module = inspect.getmodule(fonction)
        assert module is not None and module.__name__.startswith("tests"), (
            f"{nom} n'est pas interceptee : un test peut joindre un vrai "
            "serveur SMTP. Voir la fixture `captured_emails`."
        )


@pytest.mark.anyio
async def test_un_envoi_comptable_est_capture_et_non_expedie(captured_emails):
    """Le circuit comptable aboutit dans la liste, jamais sur le reseau."""
    await email_service._send_raw(
        "[Facture] Essai", "corps", ["comptabilite@example.test"]
    )
    assert len(captured_emails) == 1
    assert captured_emails[0].recipients == ["comptabilite@example.test"]
    assert captured_emails[0].extras.get("kind") == "compta"
