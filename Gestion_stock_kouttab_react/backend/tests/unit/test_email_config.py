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


@pytest.mark.asyncio
async def test_no_mail_leaves_the_process_when_sending_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EMAIL_ENABLED=false doit couper l'envoi avant toute connexion SMTP.

    Le `.env` de developpement porte les identifiants de la messagerie reelle de
    l'association : sans ce coupe-circuit, une seance de tests sur les notes de
    frais ecrit a de vrais destinataires.
    """
    from app.services import email as email_service

    envoyes: list[object] = []

    class _MailerEspion:
        async def send_message(self, message):  # noqa: ANN001
            envoyes.append(message)

    monkeypatch.setattr(email_service, "_mailer", _MailerEspion())
    monkeypatch.setattr(email_service.settings, "email_enabled", False)

    await email_service._send_raw("Sujet", "Corps", ["vrai.destinataire@example.com"])

    assert envoyes == [], "aucun message ne doit atteindre le serveur SMTP"


@pytest.mark.asyncio
async def test_mail_is_sent_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import email as email_service

    envoyes: list[object] = []

    class _MailerEspion:
        async def send_message(self, message):  # noqa: ANN001
            envoyes.append(message)

    monkeypatch.setattr(email_service, "_mailer", _MailerEspion())
    monkeypatch.setattr(email_service.settings, "email_enabled", True)

    await email_service._send_raw("Sujet", "Corps", ["destinataire@example.com"])

    assert len(envoyes) == 1
