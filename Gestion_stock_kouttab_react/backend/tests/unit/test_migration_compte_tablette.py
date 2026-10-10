"""La migration du compte systeme de la tablette, executee pour de vrai (SQLite)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.core import tablette
from app.core.security import is_legacy_hash, verify_password


pytestmark = pytest.mark.unit

_FICHIER = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_10_10_1400-f6a3b8c0d5e7_compte_tablette_buvette.py"
)


def _charger():
    spec = importlib.util.spec_from_file_location("migration_compte_tablette", _FICHIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def connexion():
    moteur = create_engine("sqlite:///:memory:")
    c = moteur.connect()
    c.execute(
        text(
            "CREATE TABLE Admins (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE,"
            " password_hash VARCHAR(255) NOT NULL, role VARCHAR(50) NOT NULL DEFAULT 'Benevole',"
            " validation_status VARCHAR(20) DEFAULT 'pending', nom VARCHAR(255),"
            " prenom VARCHAR(255), email VARCHAR(255), telephone VARCHAR(50),"
            " created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            " updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
    )
    yield c
    c.close()


def _executer(connexion, sens: str) -> None:
    module = _charger()
    contexte = MigrationContext.configure(connexion)
    with Operations.context(contexte):
        getattr(module, sens)()


def test_upgrade_cree_le_compte_puis_idempotent(connexion) -> None:
    _executer(connexion, "upgrade")
    _executer(connexion, "upgrade")
    lignes = connexion.execute(
        text("SELECT username, role, validation_status, email, password_hash, prenom, nom FROM Admins")
    ).all()
    assert len(lignes) == 1
    username, role, statut, email, empreinte, prenom, nom = lignes[0]
    assert username == tablette.USERNAME_TABLETTE
    assert role == "AdminStock" and statut == "active"
    assert email == tablette.EMAIL_TABLETTE
    assert f"{prenom} {nom}" == "Tablette buvette"
    # Mot de passe inutilisable : ni bcrypt, ni SHA-256 herite.
    assert empreinte == tablette.MOT_DE_PASSE_INUTILISABLE
    assert not is_legacy_hash(empreinte)
    assert not verify_password(empreinte, empreinte)


def test_downgrade_supprime_le_compte(connexion) -> None:
    _executer(connexion, "upgrade")
    _executer(connexion, "downgrade")
    assert connexion.execute(text("SELECT COUNT(*) FROM Admins")).scalar_one() == 0


def test_constantes_alignees_sur_le_code() -> None:
    module = _charger()
    assert module.USERNAME == tablette.USERNAME_TABLETTE
    assert module.EMAIL == tablette.EMAIL_TABLETTE
    assert module.MOT_DE_PASSE_INUTILISABLE == tablette.MOT_DE_PASSE_INUTILISABLE
