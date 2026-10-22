"""Le RIB part chez le tresorier, et ne reste nulle part.

Ce qui est teste ici est surtout ce qui NE se passe PAS : ni IBAN ni releve en
base, aucun fichier qui survive a l'envoi, aucune trace « transmis » pour un
envoi rate.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.db.models import Admin
from app.services import email as email_service
from app.services import rib as rib_service

IBAN = "FR76 3000 1007 9412 3456 7890 185"


def _png() -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (60, 30), (10, 90, 160)).save(tampon, format="PNG")
    return tampon.getvalue()


@pytest.fixture()
def envois(monkeypatch):
    """Capture les envois, et ce que contenaient les pieces AU MOMENT de l'envoi."""
    captures: list[dict] = []

    async def faux_send_raw(subject, body, recipients, *, html=False, attachments=None):
        captures.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "pieces": [(Path(p), Path(p).read_bytes()) for p in attachments or []],
            }
        )

    async def faux_send(subject, body, recipients, html=False):
        captures.append({"subject": subject, "body": body, "recipients": list(recipients)})

    monkeypatch.setattr(email_service, "_send_raw", faux_send_raw)
    monkeypatch.setattr(email_service, "_send", faux_send)
    monkeypatch.setattr(settings, "rib_destinataire_email", "tresorier@example.com")
    return captures


def _deposer(client, iban: str = IBAN, contenu: bytes | None = None):
    return client.post(
        "/api/v1/users/me/rib",
        data={"iban": iban},
        files={"file": ("rib.png", contenu or _png(), "image/png")},
    )


def test_le_rib_part_chez_le_tresorier_et_rien_ne_reste(
    client_authenticated_as, benevole_sans_rib, db_session, envois
):
    reponse = _deposer(client_authenticated_as(benevole_sans_rib))

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["rib_iban_fin"] == "0185"
    assert corps["rib_transmis_le"] is not None
    assert "rib" not in corps and "rib_document_nom" not in corps

    au_tresorier = envois[0]
    assert au_tresorier["recipients"] == ["tresorier@example.com"]
    assert "FR76 3000 1007 9412 3456 7890 185" in au_tresorier["body"]
    [(chemin, octets)] = au_tresorier["pieces"]
    assert octets.startswith(b"%PDF")  # la photo a ete convertie
    # Le fichier temporaire n'a pas survecu a l'envoi.
    assert not chemin.exists()

    db_session.expire_all()
    compte = db_session.get(Admin, benevole_sans_rib.id)
    assert compte.rib is None
    assert compte.rib_document is None
    assert compte.rib_document_type is None


def test_le_benevole_recoit_un_accuse_sans_chiffre_bancaire(
    client_authenticated_as, benevole_sans_rib, envois
):
    _deposer(client_authenticated_as(benevole_sans_rib))

    accuse = next(e for e in envois if e["recipients"] == [benevole_sans_rib.email])
    assert "0185" not in accuse["body"] and "FR76" not in accuse["body"]


def test_un_ancien_rib_en_base_est_efface_au_nouveau_depot(
    client_authenticated_as, benevole_user, db_session, envois
):
    benevole_user.rib = "FR7612345678901234567890123"
    benevole_user.rib_document = b"%PDF ancien"
    db_session.commit()

    assert _deposer(client_authenticated_as(benevole_user)).status_code == 200

    db_session.expire_all()
    compte = db_session.get(Admin, benevole_user.id)
    assert compte.rib is None and compte.rib_document is None


def test_un_envoi_rate_ne_marque_rien_transmis(
    client_authenticated_as, benevole_sans_rib, db_session, monkeypatch, envois
):
    async def panne(*args, **kwargs):
        raise AppException(ErrorCode.EMAIL_SEND_FAILED)

    monkeypatch.setattr(email_service, "_send_raw", panne)

    reponse = _deposer(client_authenticated_as(benevole_sans_rib))

    assert reponse.status_code == 502
    db_session.expire_all()
    assert db_session.get(Admin, benevole_sans_rib.id).rib_transmis_le is None


def test_sans_destinataire_configure_rien_ne_part(
    client_authenticated_as, benevole_sans_rib, monkeypatch, envois
):
    monkeypatch.setattr(settings, "rib_destinataire_email", "")

    reponse = _deposer(client_authenticated_as(benevole_sans_rib))

    assert reponse.status_code == 503
    assert envois == []


def test_un_iban_faux_est_refuse_avant_tout_envoi(
    client_authenticated_as, benevole_sans_rib, envois
):
    # Un chiffre change : la cle ne tombe plus juste.
    reponse = _deposer(client_authenticated_as(benevole_sans_rib), iban=IBAN[:-1] + "6")

    assert reponse.status_code == 422
    assert reponse.json()["code"] == "VAL_5013"
    assert envois == []


def test_les_anciennes_routes_du_document_ont_disparu(client_authenticated_as, compta_user):
    client = client_authenticated_as(compta_user)
    assert client.get("/api/v1/users/me/rib-document").status_code in (404, 405)
    assert client.get(f"/api/v1/users/{compta_user.id}/rib-document").status_code in (404, 405)


def test_le_profil_n_accepte_plus_d_iban(client_authenticated_as, benevole_user, db_session):
    client = client_authenticated_as(benevole_user)
    client.patch("/api/v1/users/me/profile", json={"rib": "FR7612345678901234567890123"})

    db_session.expire_all()
    assert db_session.get(Admin, benevole_user.id).rib is None


@pytest.mark.parametrize(
    ("iban", "attendu"),
    [
        ("FR7630001007941234567890185", True),
        ("fr76 3000 1007 9412 3456 7890 185", True),
        ("FR7630001007941234567890186", False),
        ("GB82WEST12345698765432", True),
        ("FR76", False),
        ("", False),
    ],
)
def test_validation_de_l_iban(iban, attendu):
    assert rib_service.iban_valide(rib_service.normaliser_iban(iban)) is attendu
