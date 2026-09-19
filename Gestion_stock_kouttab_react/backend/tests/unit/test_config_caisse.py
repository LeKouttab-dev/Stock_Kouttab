"""La cle de la caisse en production.

Elle autorise a decrementer le stock sans session : une cle courte se devine,
et la reprendre d'un autre secret ferait fuir les deux a la fois. Meme garde-fou
que `SSO_SHARED_SECRET` : la production refuse de demarrer plutot que de
tourner avec une porte mal fermee.
"""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from app.core.config import Settings


pytestmark = pytest.mark.unit

JWT = "j" * 64


def _production(**autres: str) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="production",
        APP_DEBUG="false",
        JWT_SECRET_KEY=JWT,
        CORS_ORIGINS="https://stock.lekouttab.fr",
        RIB_ENCRYPTION_KEY=base64.urlsafe_b64encode(bytes(32)).decode(),
        **autres,
    )


def test_une_cle_de_caisse_courte_empeche_le_demarrage() -> None:
    with pytest.raises(ValidationError, match="CAISSE_API_KEY est trop courte"):
        _production(CAISSE_API_KEY="courte")


def test_la_cle_de_caisse_ne_reprend_pas_le_secret_jwt() -> None:
    with pytest.raises(ValidationError, match="CAISSE_API_KEY doit différer"):
        _production(CAISSE_API_KEY=JWT)


def test_sans_cle_la_production_demarre_caisse_fermee() -> None:
    """Vide = routes /caisse en 404 : un choix légitime, pas une erreur."""
    assert _production(CAISSE_API_KEY="").caisse_api_key == ""


def test_une_cle_robuste_est_acceptee() -> None:
    cle = "c" * 48
    assert _production(CAISSE_API_KEY=cle).caisse_api_key == cle
