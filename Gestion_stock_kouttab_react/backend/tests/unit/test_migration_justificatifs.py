"""La migration qui charge les justificatifs existants en base.

Elle ne tourne qu'une fois, sur des pieces comptables a conserver plusieurs
annees. Un fichier manque a l'appel et c'est un justificatif perdu : autant
l'avoir vue tourner sur des cas tordus avant de la lancer en production.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


pytestmark = pytest.mark.unit


_FICHIER = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_08_12_2200-f6b3d1e8a295_justificatifs_en_base.py"
)


def _charger():
    spec = importlib.util.spec_from_file_location("migration_blob", _FICHIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def base():
    moteur = create_engine("sqlite:///:memory:")
    connexion = moteur.connect()
    for table in ("FichiersNotesDeFrais", "FichiersFactures"):
        connexion.execute(
            text(
                f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, "
                "chemin_fichier VARCHAR(500) NOT NULL)"
            )
        )
    yield connexion
    connexion.close()


def _executer(module, connexion, sens: str = "upgrade") -> None:
    contexte = MigrationContext.configure(connexion)
    module.op = Operations(contexte)
    getattr(module, sens)()


def test_les_fichiers_du_disque_arrivent_en_base(base, tmp_path):
    piece = tmp_path / "ticket.pdf"
    octets = b"%PDF-1.4 contenu du justificatif"
    piece.write_bytes(octets)
    base.execute(
        text("INSERT INTO FichiersFactures (id, chemin_fichier) VALUES (1, :c)"),
        {"c": str(piece)},
    )

    _executer(_charger(), base)

    stocke = base.execute(text("SELECT contenu FROM FichiersFactures WHERE id = 1")).scalar()
    assert bytes(stocke) == octets


def test_les_deux_tables_sont_traitees(base, tmp_path):
    for i, table in enumerate(("FichiersNotesDeFrais", "FichiersFactures"), start=1):
        piece = tmp_path / f"p{i}.pdf"
        piece.write_bytes(f"contenu {i}".encode())
        base.execute(
            text(f"INSERT INTO {table} (id, chemin_fichier) VALUES (1, :c)"),
            {"c": str(piece)},
        )

    _executer(_charger(), base)

    for i, table in enumerate(("FichiersNotesDeFrais", "FichiersFactures"), start=1):
        stocke = base.execute(text(f"SELECT contenu FROM {table} WHERE id = 1")).scalar()
        assert bytes(stocke) == f"contenu {i}".encode()


def test_un_fichier_deja_disparu_n_arrete_pas_la_migration(base, tmp_path):
    """Une piece perdue avant la migration ne doit pas empecher de sauver les
    autres — c'est justement contre ce genre de perte qu'on migre."""
    present = tmp_path / "present.pdf"
    present.write_bytes(b"je suis la")
    base.execute(
        text("INSERT INTO FichiersFactures (id, chemin_fichier) VALUES (1, :a), (2, :b)"),
        {"a": str(tmp_path / "envole.pdf"), "b": str(present)},
    )

    _executer(_charger(), base)

    lignes = dict(base.execute(text("SELECT id, contenu FROM FichiersFactures")).all())
    assert lignes[1] is None
    assert bytes(lignes[2]) == b"je suis la"


def test_une_base_sans_fichier_passe_sans_erreur(base):
    _executer(_charger(), base)
    colonnes = [r[1] for r in base.execute(text("PRAGMA table_info(FichiersFactures)")).all()]
    assert "contenu" in colonnes


def test_le_retour_arriere_retire_la_colonne(base, tmp_path):
    """Les fichiers restent sur le disque : rien n'est perdu."""
    piece = tmp_path / "t.pdf"
    piece.write_bytes(b"x")
    base.execute(
        text("INSERT INTO FichiersFactures (id, chemin_fichier) VALUES (1, :c)"),
        {"c": str(piece)},
    )
    module = _charger()

    _executer(module, base)
    _executer(module, base, "downgrade")

    colonnes = [r[1] for r in base.execute(text("PRAGMA table_info(FichiersFactures)")).all()]
    assert "contenu" not in colonnes
    assert piece.read_bytes() == b"x"
