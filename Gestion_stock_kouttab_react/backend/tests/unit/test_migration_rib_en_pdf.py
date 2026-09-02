"""La migration qui met les RIB deja deposes au format PDF, executee pour de vrai.

Sans elle, la contrainte posee sur le depot d'une note de frais bloquerait, sans
recours et sans qu'ils comprennent pourquoi, tous ceux qui avaient depose une
photo de leur RIB quand c'etait encore accepte. Une contrainte nouvelle sur un
depot existant se livre avec la migration qui met le stock en conformite.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
from PIL import Image
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"

_FICHIER = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_09_02_1000-e8b2f4a7c1d5_rib_en_pdf.py"
)


def _png() -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", (60, 30), (10, 90, 160)).save(tampon, format="PNG")
    return tampon.getvalue()


def _charger_migration():
    spec = importlib.util.spec_from_file_location("migration_rib_pdf", _FICHIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def base():
    """Une table `Admins` reduite aux colonnes du RIB en document."""
    moteur = create_engine("sqlite:///:memory:")
    connexion = moteur.connect()
    connexion.execute(
        text(
            "CREATE TABLE Admins ("
            " id INTEGER PRIMARY KEY,"
            " rib_document BLOB,"
            " rib_document_nom VARCHAR(255),"
            " rib_document_type VARCHAR(100))"
        )
    )
    yield connexion
    connexion.close()


def _executer(module, connexion, sens: str = "upgrade") -> None:
    """Branche le `op` global d'Alembic sur notre connexion de test."""
    contexte = MigrationContext.configure(connexion)
    module.op = Operations(contexte)
    getattr(module, sens)()


def _documents(connexion) -> dict[int, tuple]:
    lignes = connexion.execute(
        text("SELECT id, rib_document, rib_document_nom, rib_document_type FROM Admins")
    ).fetchall()
    return {ligne[0]: tuple(ligne[1:]) for ligne in lignes}


def test_convertit_les_images_et_laisse_les_pdf_intacts(base):
    image = _png()
    base.execute(
        text(
            "INSERT INTO Admins (id, rib_document, rib_document_nom, rib_document_type)"
            " VALUES (1, :img, 'mon-rib.png', 'image/png'),"
            "        (2, :pdf, 'rib.pdf', 'application/pdf'),"
            "        (3, NULL, NULL, NULL)"
        ),
        {"img": image, "pdf": PDF},
    )

    _executer(_charger_migration(), base)

    apres = _documents(base)
    contenu, nom, type_mime = apres[1]
    assert bytes(contenu).startswith(b"%PDF")
    assert nom == "mon-rib.pdf"
    assert type_mime == "application/pdf"
    # Un PDF n'est jamais reencapsule : il perdrait son texte selectionnable.
    assert apres[2] == (PDF, "rib.pdf", "application/pdf")
    # Un compte sans document reste sans document.
    assert apres[3] == (None, None, None)


def test_un_document_illisible_n_arrete_pas_la_migration(base):
    """Le deploiement execute `alembic upgrade head` avant de redemarrer l'API.

    Un octet corrompu sur un seul compte ne doit pas empecher la mise a jour de
    tourner : son proprietaire se verra demander un nouveau depot, ce que le
    controle sur la note de frais fait deja.
    """
    base.execute(
        text(
            "INSERT INTO Admins (id, rib_document, rib_document_nom, rib_document_type)"
            " VALUES (1, :abime, 'casse.png', 'image/png'), (2, :pdf, 'rib.pdf', 'application/pdf')"
        ),
        {"abime": b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "pdf": PDF},
    )

    _executer(_charger_migration(), base)

    apres = _documents(base)
    assert apres[1] == (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "casse.png", "image/png")
    assert apres[2][2] == "application/pdf"


def test_migration_rejouee_est_sans_effet(base):
    """Alembic ne la rejouera pas, mais une reprise manuelle apres incident, si."""
    base.execute(
        text(
            "INSERT INTO Admins (id, rib_document, rib_document_nom, rib_document_type)"
            " VALUES (1, :img, 'mon-rib.png', 'image/png')"
        ),
        {"img": _png()},
    )
    module = _charger_migration()

    _executer(module, base)
    premier = _documents(base)[1]
    _executer(module, base)

    assert _documents(base)[1] == premier
