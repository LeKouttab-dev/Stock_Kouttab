"""Journal de la tablette (13/10/2026) : `POST /buvette/caisse/journal`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.buvette import CaisseJournalEntree
from app.services import journal_tablette


pytestmark = pytest.mark.integration

CLE = "cle-de-test-de-la-caisse-au-moins-32-caracteres"
URL = "/api/v1/buvette/caisse/journal"


@pytest.fixture(autouse=True)
def _caisse_et_dossier(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", CLE)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))


def _entree(ts: str = "2026-10-13T06:58:12+02:00", **autres) -> dict:
    return {"ts": ts, "niveau": "info", "message": "Démarrage 0.8.8", **autres}


def test_le_journal_exige_la_cle(client: TestClient) -> None:
    corps = {"entrees": [_entree()]}
    assert client.post(URL, json=corps).status_code == 401
    assert client.post(URL, json=corps, headers={"X-Caisse-Key": "faux"}).status_code == 401
    assert not journal_tablette.dossier().exists()


def test_les_entrees_vont_dans_le_fichier_du_jour_de_la_tablette(client: TestClient) -> None:
    corps = {
        "entrees": [
            _entree(),
            # 23 h 30 heure de Paris le 12 : fichier du 12, pas du 13 (UTC).
            _entree(ts="2026-10-12T23:30:00+02:00", niveau="warn", message="Écran\néteint\thors caisse"),
        ]
    }
    assert client.post(URL, json=corps, headers={"X-Caisse-Key": CLE}).status_code == 204

    dossier = journal_tablette.dossier()
    du_13 = (dossier / "2026-10-13.log").read_text(encoding="utf-8").splitlines()
    du_12 = (dossier / "2026-10-12.log").read_text(encoding="utf-8").splitlines()
    assert len(du_13) == 1 and len(du_12) == 1
    heure, niveau, message, _recu = du_13[0].split("\t")
    assert (heure, niveau, message) == ("2026-10-13T06:58:12+02:00", "INFO", "Démarrage 0.8.8")
    # Retour a la ligne et tabulation neutralises : une entree = une ligne, 4 colonnes.
    assert du_12[0].split("\t")[1:3] == ["WARN", "Écran éteint hors caisse"]

    # Un second envoi s'ajoute, il n'ecrase pas.
    client.post(URL, json={"entrees": [_entree()]}, headers={"X-Caisse-Key": CLE})
    assert len((dossier / "2026-10-13.log").read_text(encoding="utf-8").splitlines()) == 2


def test_un_lot_trop_gros_est_refuse(client: TestClient) -> None:
    corps = {"entrees": [_entree()] * 501}
    assert client.post(URL, json=corps, headers={"X-Caisse-Key": CLE}).status_code == 422


def test_les_vieux_fichiers_sont_purges() -> None:
    dossier = journal_tablette.dossier()
    dossier.mkdir(parents=True)
    (dossier / "2026-07-01.log").write_text("ancien\n", encoding="utf-8")
    (dossier / "2026-09-01.log").write_text("recent\n", encoding="utf-8")
    (dossier / "autre.txt").write_text("garde\n", encoding="utf-8")

    journal_tablette.ecrire(
        [CaisseJournalEntree(ts=datetime(2026, 10, 13, 8, tzinfo=timezone.utc), message="x")],
        recu=datetime(2026, 10, 13, 8, tzinfo=timezone.utc),
    )

    assert not (dossier / "2026-07-01.log").exists()  # plus de 60 jours
    assert (dossier / "2026-09-01.log").exists()
    assert (dossier / "autre.txt").exists()
