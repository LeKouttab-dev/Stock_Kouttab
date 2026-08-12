"""La migration qui chiffre les RIB existants, executee pour de vrai.

Elle ne tourne qu'une fois, sur la base de production, sur la donnee la plus
sensible du projet. Une erreur y est irrattrapable : autant l'avoir vue tourner.
"""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.core import crypto


RIB_A = "FR76 3000 6000 0112 3456 7890 189"
RIB_B = "FR14 2004 1010 0505 0001 3M02 606"

_FICHIER = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_08_12_1200-a1c8e6f2b307_chiffrer_les_rib_existants.py"
)


def _charger_migration():
    spec = importlib.util.spec_from_file_location("migration_rib", _FICHIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def cle(monkeypatch: pytest.MonkeyPatch):
    crypto.reinitialiser_cle()
    monkeypatch.setenv(
        "RIB_ENCRYPTION_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode()
    )
    yield
    crypto.reinitialiser_cle()


@pytest.fixture()
def base():
    """Une table `Admins` reduite au strict necessaire, et sa connexion."""
    moteur = create_engine("sqlite:///:memory:")
    connexion = moteur.connect()
    connexion.execute(text("CREATE TABLE Admins (id INTEGER PRIMARY KEY, rib VARCHAR(255))"))
    yield connexion
    connexion.close()


def _executer(module, connexion, sens: str = "upgrade") -> None:
    """Branche le `op` global d'Alembic sur notre connexion de test."""
    contexte = MigrationContext.configure(connexion)
    module.op = Operations(contexte)
    getattr(module, sens)()


def _ribs(connexion) -> dict[int, str | None]:
    return {r[0]: r[1] for r in connexion.execute(text("SELECT id, rib FROM Admins")).fetchall()}


def test_convertit_le_clair_et_respecte_le_reste(base, cle):
    module = _charger_migration()
    deja_chiffre = crypto.chiffrer(RIB_B)
    base.execute(
        text("INSERT INTO Admins (id, rib) VALUES (1, :a), (2, NULL), (3, :c), (4, '')"),
        {"a": RIB_A, "c": deja_chiffre},
    )

    _executer(module, base)

    apres = _ribs(base)
    # Le clair est devenu illisible...
    assert crypto.est_chiffre(apres[1])
    assert RIB_A not in apres[1]
    # ...mais reste dechiffrable a l'identique.
    assert crypto.dechiffrer(apres[1]) == RIB_A
    # Ce qui etait deja chiffre n'est pas rechiffre une seconde fois.
    assert apres[3] == deja_chiffre
    # Les champs vides sont laisses tranquilles.
    assert apres[2] is None
    assert apres[4] == ""


def test_sans_cle_la_migration_echoue_sans_rien_modifier(base, monkeypatch):
    """Mieux vaut un arret net qu'une base a moitie chiffree."""
    crypto.reinitialiser_cle()
    monkeypatch.delenv("RIB_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(crypto, "_valeur_brute", lambda: "")
    module = _charger_migration()
    base.execute(text("INSERT INTO Admins (id, rib) VALUES (1, :a)"), {"a": RIB_A})

    with pytest.raises(RuntimeError, match="RIB_ENCRYPTION_KEY"):
        _executer(module, base)

    assert _ribs(base)[1] == RIB_A


def test_le_retour_arriere_rend_les_rib_lisibles(base, cle):
    """L'ancienne version du code lit la colonne telle quelle : lui laisser du
    chiffre afficherait « gcm1:... » a la comptabilite."""
    module = _charger_migration()
    base.execute(text("INSERT INTO Admins (id, rib) VALUES (1, :a)"), {"a": RIB_A})

    _executer(module, base)
    _executer(module, base, "downgrade")

    assert _ribs(base)[1] == RIB_A


def test_migration_rejouee_est_sans_effet(base, cle):
    """Alembic ne la rejouera pas, mais une reprise manuelle apres incident,
    si : elle ne doit pas chiffrer deux fois."""
    module = _charger_migration()
    base.execute(text("INSERT INTO Admins (id, rib) VALUES (1, :a)"), {"a": RIB_A})

    _executer(module, base)
    premier = _ribs(base)[1]
    _executer(module, base)

    assert _ribs(base)[1] == premier
