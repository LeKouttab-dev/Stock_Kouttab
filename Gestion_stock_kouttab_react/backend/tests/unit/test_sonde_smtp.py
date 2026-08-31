"""La sonde qui aurait signale la panne de courriel.

Le 2026-08-30, il a fallu qu'un utilisateur remarque l'absence de courriels pour
decouvrir que plus rien ne partait depuis des semaines : O2Switch avait cesse de
servir un certificat couvrant `mail.lekouttab.fr` et presentait celui du cluster
(`*.sauterelle.o2switch.net`). La poignee de main TLS echouait, `_send` avalait
l'exception, et l'ecran d'administration affichait tout en vert.

`verifier_smtp` repond a la question que personne ne pouvait poser : est-ce
qu'un courriel partirait, la, maintenant ?
"""

from __future__ import annotations

import smtplib
import ssl

import pytest

from app.core.config import settings
from app.services import email as email_service


pytestmark = pytest.mark.unit


def test_la_sonde_n_ouvre_aucune_connexion_quand_les_envois_sont_coupes():
    """Le coupe-circuit passe AVANT le reseau — comme dans `_send_raw`.

    Sans cette garde, la sonde joindrait la messagerie reelle de l'association a
    chaque test, exactement le defaut que `test_aucun_envoi_reel` verrouille
    pour les envois.
    """
    assert settings.email_enabled is False, "cf. tests/conftest.py"

    def _interdit(*args, **kwargs):  # pragma: no cover — ne doit jamais courir
        raise AssertionError("la sonde a ouvert une connexion SMTP")

    original = smtplib.SMTP_SSL
    smtplib.SMTP_SSL = _interdit  # type: ignore[assignment]
    try:
        joignable, motif = email_service.verifier_smtp()
    finally:
        smtplib.SMTP_SSL = original  # type: ignore[assignment]

    assert joignable is False
    assert motif is not None and "EMAIL_ENABLED" in motif


def test_un_certificat_qui_ne_couvre_pas_l_hote_est_dit_comme_tel(monkeypatch):
    """Le motif doit nommer le remede : changer SMTP_HOST, pas le mot de passe.

    Un « echec de connexion » generique aurait envoye chercher du cote des
    identifiants ou du reseau — ni l'un ni l'autre n'etait en cause.
    """
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "mail.exemple.test")
    monkeypatch.setattr(settings, "smtp_user", "no-reply@exemple.test")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_port", 465)

    def _certificat_invalide(*args, **kwargs):
        raise ssl.SSLCertVerificationError(
            1, "certificate verify failed: Hostname mismatch"
        )

    monkeypatch.setattr(smtplib, "SMTP_SSL", _certificat_invalide)

    joignable, motif = email_service.verifier_smtp()

    assert joignable is False
    assert motif is not None
    assert "mail.exemple.test" in motif
    assert "sauterelle.o2switch.net" in motif


def test_une_liaison_saine_ne_rapporte_aucun_motif(monkeypatch):
    """Le cas nominal : connexion et authentification, sans le moindre envoi.

    `send_message` n'est jamais appele — une sonde qui derange une vraie boite
    finit debranchee, et c'est alors la panne qui redevient invisible.
    """
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "mail.exemple.test")
    monkeypatch.setattr(settings, "smtp_user", "no-reply@exemple.test")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_port", 465)

    gestes: list[str] = []

    class _Serveur:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, user, password):
            gestes.append("login")

        def send_message(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("la sonde ne doit rien expedier")

    monkeypatch.setattr(smtplib, "SMTP_SSL", lambda *a, **k: _Serveur())

    joignable, motif = email_service.verifier_smtp()

    assert joignable is True
    assert motif is None
    assert gestes == ["login"]


@pytest.mark.parametrize(
    "manquant", ["smtp_host", "smtp_user", "smtp_password"]
)
def test_une_variable_manquante_est_nommee(monkeypatch, manquant):
    """Dire laquelle : `SMTP_PASSWORD` vide construisait quand meme le mailer.

    L'envoi echouait alors a l'authentification, plus loin et plus obscurement
    que necessaire.
    """
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "mail.exemple.test")
    monkeypatch.setattr(settings, "smtp_user", "no-reply@exemple.test")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, manquant, "")

    joignable, motif = email_service.verifier_smtp()

    assert joignable is False
    assert motif is not None and manquant.upper() in motif
