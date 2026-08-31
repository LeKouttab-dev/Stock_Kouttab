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
    send_raw_reel,
) -> None:
    """EMAIL_ENABLED=false doit couper l'envoi avant toute connexion SMTP.

    Le `.env` de developpement porte les identifiants de la messagerie reelle de
    l'association : sans ce coupe-circuit, une seance de tests sur les notes de
    frais ecrit a de vrais destinataires.

    Le coupe-circuit **leve** desormais, au lieu de rendre la main en silence.
    Il retournait auparavant comme si l'envoi avait reussi, et `outbox` marquait
    la ligne « Envoyee » : la production a tourne trois semaines muette, avec un
    ecran d'envois tout en vert. Cf. `tests/integration/test_envoi_desactive.py`.
    """
    from app.core.exceptions import AppException
    from app.services import email as email_service

    envoyes: list[object] = []

    class _MailerEspion:
        async def send_message(self, message):  # noqa: ANN001
            envoyes.append(message)

    monkeypatch.setattr(email_service, "_mailer", _MailerEspion())
    monkeypatch.setattr(email_service.settings, "email_enabled", False)

    with pytest.raises(AppException):
        await send_raw_reel("Sujet", "Corps", ["vrai.destinataire@example.com"])

    assert envoyes == [], "aucun message ne doit atteindre le serveur SMTP"


@pytest.mark.asyncio
async def test_mail_is_sent_when_enabled(
    monkeypatch: pytest.MonkeyPatch, send_raw_reel
) -> None:
    from app.services import email as email_service

    envoyes: list[object] = []

    class _MailerEspion:
        async def send_message(self, message):  # noqa: ANN001
            envoyes.append(message)

    monkeypatch.setattr(email_service, "_mailer", _MailerEspion())
    monkeypatch.setattr(email_service.settings, "email_enabled", True)

    await send_raw_reel("Sujet", "Corps", ["destinataire@example.com"])

    assert len(envoyes) == 1


# ---- Ne pas se notifier soi-meme ---------------------------------------------


def test_author_is_excluded_from_their_own_notification(db_session, monkeypatch) -> None:
    """Sur une petite structure, une seule personne cumule les roles.

    Deposer une facture declenchait un courriel annoncant a son auteur qu'une
    facture venait d'etre deposee. Ce bruit finit par masquer les notifications
    utiles.
    """
    from app.services import email as email_service

    monkeypatch.setattr(
        email_service,
        "get_emails_by_roles",
        lambda db, roles: ["omar@example.com", "compta@example.com"],
    )

    restants = email_service._destinataires_sauf_auteur(
        db_session, ["Compta"], "omar@example.com"
    )
    assert restants == ["compta@example.com"]


def test_author_exclusion_ignores_case(db_session, monkeypatch) -> None:
    from app.services import email as email_service

    monkeypatch.setattr(
        email_service, "get_emails_by_roles", lambda db, roles: ["Omar@Example.COM"]
    )
    assert email_service._destinataires_sauf_auteur(db_session, ["Compta"], "omar@example.com") == []


def test_everyone_is_kept_when_the_author_is_unknown(db_session, monkeypatch) -> None:
    from app.services import email as email_service

    monkeypatch.setattr(email_service, "get_emails_by_roles", lambda db, roles: ["a@b.fr"])
    assert email_service._destinataires_sauf_auteur(db_session, ["Compta"], None) == ["a@b.fr"]


def test_status_change_skips_self_validation() -> None:
    """Valider sa propre note ne doit pas declencher de courriel.

    La regle est testee sur la fonction de decision : la fixture `captured_emails`
    remplace `send_status_change` en entier pour qu'aucun test ne joigne un vrai
    serveur SMTP, ce qui rend l'envoi lui-meme inobservable ici.
    """
    from app.services.email import doit_notifier_du_statut

    assert doit_notifier_du_statut("omar@example.com", "omar@example.com") is False
    assert doit_notifier_du_statut("Omar@Example.COM", "omar@example.com") is False
    assert doit_notifier_du_statut("benevole@example.com", "omar@example.com") is True
    assert doit_notifier_du_statut("benevole@example.com", None) is True


# ---- L'avis de depot trouve toujours un destinataire -------------------------
#
# L'exclusion de l'auteur (2026-08-12) pouvait vider entierement la liste : le
# seul compte portant un role comptable etant celui qui depose, plus aucun avis
# ne partait a la comptabilite, et la fonction sortait sans un mot. Le defaut
# ressemblait a une panne SMTP — il a ete cherche la pendant des semaines.


def test_le_depot_bascule_sur_la_boite_compta_quand_l_auteur_est_seul(
    db_session, monkeypatch
) -> None:
    """`COMPTA_EMAIL` est une boite, pas une personne.

    Elle recoit deja les pieces comptables et peut etre lue par un tresorier
    sans compte dans l'application : l'ecarter parce que le deposant porte le
    role `Compta` privait de l'avis quelqu'un qui n'avait rien depose.
    """
    from app.core.config import settings
    from app.services import email as email_service

    monkeypatch.setattr(
        email_service, "get_emails_by_roles", lambda db, roles: ["omar@example.com"]
    )
    monkeypatch.setattr(settings, "compta_email_raw", "comptabilite@example.test")

    destinataires = email_service._destinataires_du_depot(
        db_session, "omar@example.com", quoi="note de frais", deposant="Omar"
    )
    assert destinataires == ["comptabilite@example.test"]


def test_les_comptes_comptables_priment_sur_le_repli(db_session, monkeypatch) -> None:
    """Le repli ne se declenche que si l'exclusion n'a laisse personne.

    Sinon la boite comptable recevrait un doublon de chaque avis deja adresse
    nominativement.
    """
    from app.core.config import settings
    from app.services import email as email_service

    monkeypatch.setattr(
        email_service,
        "get_emails_by_roles",
        lambda db, roles: ["omar@example.com", "tresorier@example.com"],
    )
    monkeypatch.setattr(settings, "compta_email_raw", "comptabilite@example.test")

    destinataires = email_service._destinataires_du_depot(
        db_session, "omar@example.com", quoi="facture", deposant="Omar"
    )
    assert destinataires == ["tresorier@example.com"]


def test_sans_compte_ni_boite_l_avis_perdu_est_journalise(db_session, monkeypatch) -> None:
    """La seule branche ou l'avis se perd vraiment doit se dire.

    C'est la sortie muette d'origine qui a fait chercher la panne du cote du
    serveur SMTP, qui n'y etait pour rien.

    On intercepte le logger du module plutot que d'utiliser `caplog` : celui de
    l'application ne propage pas vers la racine (cf.
    `test_suppression_definitive_note`), et le test passerait en n'observant rien.
    """
    from app.core.config import settings
    from app.services import email as email_service

    monkeypatch.setattr(
        email_service, "get_emails_by_roles", lambda db, roles: ["omar@example.com"]
    )
    monkeypatch.setattr(settings, "compta_email_raw", "")

    traces: list[str] = []
    monkeypatch.setattr(
        email_service.logger,
        "warning",
        lambda message, *args, **_: traces.append(message % args if args else message),
    )

    destinataires = email_service._destinataires_du_depot(
        db_session, "omar@example.com", quoi="note de frais", deposant="Omar"
    )

    assert destinataires == []
    assert "COMPTA_EMAIL" in " ".join(traces)
