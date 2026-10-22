"""Reprise des RIB encore en base : transmettre, PUIS effacer, compte par compte."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.db.models import Admin
from app.services import email as email_service
from scripts import transmettre_et_purger_rib as purge


def _avec_ancien_rib(db_session, compte):
    compte.rib = "FR7630001007941234567890185"
    compte.rib_document = b"%PDF ancien releve"
    compte.rib_document_type = "application/pdf"
    compte.rib_transmis_le = None
    db_session.commit()


def test_a_sec_rien_ne_part_ni_ne_s_efface(db_session, benevole_user, monkeypatch):
    _avec_ancien_rib(db_session, benevole_user)
    envois = []

    async def faux(*a, **k):
        envois.append(a)

    monkeypatch.setattr(email_service, "_send_raw", faux)

    asyncio.run(purge.traiter(db_session, envoyer=False, purger_seulement=False))

    assert envois == []
    db_session.expire_all()
    assert db_session.get(Admin, benevole_user.id).rib is not None


def test_transmis_puis_efface(db_session, benevole_user, monkeypatch):
    _avec_ancien_rib(db_session, benevole_user)
    monkeypatch.setattr(settings, "rib_destinataire_email", "tresorier@example.com")
    envois = []

    async def faux(subject, body, recipients, *, html=False, attachments=None):
        envois.append((body, [Path(p).read_bytes() for p in attachments or []]))

    monkeypatch.setattr(email_service, "_send_raw", faux)

    traites, echecs = asyncio.run(purge.traiter(db_session, envoyer=True, purger_seulement=False))

    assert (traites, echecs) == (1, 0)
    corps, pieces = envois[0]
    assert "FR76 3000 1007 9412 3456 7890 185" in corps
    assert pieces == [b"%PDF ancien releve"]
    db_session.expire_all()
    compte = db_session.get(Admin, benevole_user.id)
    assert compte.rib is None and compte.rib_document is None
    assert compte.rib_transmis_le is not None and compte.rib_iban_fin == "0185"


def test_un_envoi_rate_ne_purge_pas_le_compte(db_session, benevole_user, monkeypatch):
    _avec_ancien_rib(db_session, benevole_user)
    monkeypatch.setattr(settings, "rib_destinataire_email", "tresorier@example.com")

    async def panne(*a, **k):
        raise AppException(ErrorCode.EMAIL_SEND_FAILED)

    monkeypatch.setattr(email_service, "_send_raw", panne)

    traites, echecs = asyncio.run(purge.traiter(db_session, envoyer=True, purger_seulement=False))

    assert (traites, echecs) == (0, 1)
    db_session.expire_all()
    compte = db_session.get(Admin, benevole_user.id)
    assert compte.rib == "FR7630001007941234567890185"
    assert compte.rib_transmis_le is None
