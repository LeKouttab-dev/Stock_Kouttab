"""La migration de la cloture de caisse ponctuelle, executee pour de vrai (SQLite).

Les clotures journalieres existantes doivent recevoir une periode logique (la
journee de leur `jour` a Paris, arretee a la saisie) et le nombre de ventes
especes de cette periode ; l'index unique sur `jour` doit disparaitre.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.unit

_FICHIER = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_10_10_1000-e5f2a7b9c4d6_cloture_caisse_ponctuelle.py"
)


def _charger_migration():
    spec = importlib.util.spec_from_file_location("migration_cloture_ponctuelle", _FICHIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def base():
    moteur = create_engine("sqlite:///:memory:")
    connexion = moteur.connect()
    connexion.execute(
        text(
            "CREATE TABLE CloturesCaisse ("
            " id INTEGER PRIMARY KEY, jour DATE NOT NULL,"
            " attendu_cents INTEGER NOT NULL, compte_cents INTEGER NOT NULL,"
            " ecart_cents INTEGER NOT NULL, commentaire TEXT, saisi_par VARCHAR(255),"
            " created_at DATETIME NOT NULL,"
            " CONSTRAINT uq_cloture_caisse_jour UNIQUE (jour))"
        )
    )
    connexion.execute(
        text(
            "CREATE TABLE BuvetteSales ("
            " id INTEGER PRIMARY KEY, source VARCHAR(20), caisse_tx_id VARCHAR(64),"
            " sumup_tx_code VARCHAR(64), sold_at DATETIME, processed_at DATETIME)"
        )
    )
    yield connexion
    connexion.close()


def _executer(module, connexion, sens: str) -> None:
    contexte = MigrationContext.configure(connexion)
    module.op = Operations(contexte)
    getattr(module, sens)()


def _vente(connexion, tx: str, quand: str, code: str | None = None) -> None:
    connexion.execute(
        text(
            "INSERT INTO BuvetteSales (source, caisse_tx_id, sumup_tx_code, sold_at, processed_at)"
            " VALUES ('caisse', :tx, :code, :quand, :quand)"
        ),
        {"tx": tx, "code": code, "quand": quand},
    )


def test_retro_remplit_les_clotures_journalieres(base) -> None:
    # Cloture du 05/10 saisie a 22 h (Paris) = 20 h UTC ; celle du 06/10 saisie le
    # lendemain matin : toute la journee du 06.
    base.execute(
        text(
            "INSERT INTO CloturesCaisse VALUES"
            " (1, '2026-10-05', 500, 450, -50, NULL, 'Yusuf', '2026-10-05 20:00:00'),"
            " (2, '2026-10-06', 0, 0, 0, NULL, 'Yusuf', '2026-10-07 07:00:00')"
        )
    )
    _vente(base, "a", "2026-10-05 10:00:00")
    _vente(base, "a", "2026-10-05 10:00:00")  # deuxieme ligne du meme panier
    _vente(base, "b", "2026-10-05 21:30:00")
    _vente(base, "c", "2026-10-05 22:30:00")  # apres la saisie
    _vente(base, "d", "2026-10-05 12:00:00", code="TX1")  # carte
    _vente(base, "e", "2026-10-06 23:00:00")

    _executer(_charger_migration(), base, "upgrade")

    lignes = base.execute(
        text("SELECT id, periode_debut, periode_fin, nb_ventes FROM CloturesCaisse ORDER BY id")
    ).fetchall()
    def dt(v):
        return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))

    assert dt(lignes[0][1]) == datetime(2026, 10, 4, 22, 0)
    assert dt(lignes[0][2]) == datetime(2026, 10, 5, 20, 0)
    assert lignes[0][3] == 2
    assert dt(lignes[1][1]) == datetime(2026, 10, 5, 22, 0)
    assert dt(lignes[1][2]) == datetime(2026, 10, 6, 22, 0)
    assert lignes[1][3] == 1

    # Plus d'unicite sur le jour : deux clotures le meme jour passent.
    base.execute(
        text(
            "INSERT INTO CloturesCaisse (jour, periode_debut, periode_fin, nb_ventes,"
            " attendu_cents, compte_cents, ecart_cents, created_at) VALUES"
            " ('2026-10-06', '2026-10-06 22:00:00', '2026-10-06 23:00:00', 0, 0, 0, 0,"
            " '2026-10-06 23:00:00')"
        )
    )
    index = {i["name"] for i in inspect(base).get_indexes("CloturesCaisse")}
    assert {"ix_cloture_caisse_jour", "ix_cloture_caisse_periode_fin"} <= index
    base.execute(text("DELETE FROM CloturesCaisse WHERE id = 3"))

    _executer(_charger_migration(), base, "downgrade")
    colonnes = {c["name"] for c in inspect(base).get_columns("CloturesCaisse")}
    assert not {"periode_debut", "periode_fin", "nb_ventes"} & colonnes
    assert base.execute(text("SELECT COUNT(*) FROM CloturesCaisse")).scalar() == 2
