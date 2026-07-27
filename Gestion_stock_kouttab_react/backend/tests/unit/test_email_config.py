"""Coherence du mode TLS SMTP.

La configuration livree combinait le port 465 (TLS implicite) avec STARTTLS.
La connexion echouait, et ``_send`` avalant les exceptions, plus aucun email ne
partait sans qu'aucune alerte ne le signale.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.email import _resolve_tls_mode


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("port", "use_tls", "use_ssl", "expected"),
    [
        # Port 465 : TLS implicite, quelle que soit la combinaison declaree.
        (465, True, False, (False, True)),  # le cas casse en production
        (465, False, True, (False, True)),  # deja correct
        (465, False, False, (False, True)),
        # Port 587 : STARTTLS.
        (587, True, False, (True, False)),  # deja correct
        (587, False, True, (True, False)),  # incoherent -> corrige
        # Port non standard : on respecte la declaration de l'operateur.
        (2525, True, False, (True, False)),
        (2525, False, True, (False, True)),
    ],
)
def test_tls_mode_follows_the_port(
    monkeypatch: pytest.MonkeyPatch,
    port: int,
    use_tls: bool,
    use_ssl: bool,
    expected: tuple[bool, bool],
) -> None:
    monkeypatch.setattr(settings, "smtp_port", port)
    monkeypatch.setattr(settings, "smtp_use_tls", use_tls)
    monkeypatch.setattr(settings, "smtp_use_ssl", use_ssl)
    assert _resolve_tls_mode() == expected


def test_compta_emails_parses_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "compta_email_raw", " comptabilite@lekouttab.fr , tresorier@lekouttab.fr "
    )
    assert settings.compta_emails == [
        "comptabilite@lekouttab.fr",
        "tresorier@lekouttab.fr",
    ]


def test_compta_emails_is_empty_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "compta_email_raw", "")
    assert settings.compta_emails == []
