"""La mise a jour de la tablette de caisse, a distance.

La tablette tourne en mode borne : personne ne va au magasin d'applications,
c'est elle qui vient chercher son APK. Deux proprietes comptent plus que le
reste :

 1. **L'APK n'est JAMAIS servi sans authentification.** Contrairement aux photos
    de produits, il porte en clair la cle affiliee SumUp et `CAISSE_API_KEY` :
    public, il donnerait a quiconque le droit de poster des ventes.
 2. **Publier est reserve au Super Admin.** Distribuer cet APK, c'est distribuer
    de quoi encaisser.
"""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import caisse_app


pytestmark = pytest.mark.integration

CLE = "cle-de-caisse-de-test-suffisamment-longue-1234"


def _apk(marque: bytes = b"v3") -> bytes:
    """Une archive ZIP, comme l'est un APK — signature `PK\\x03\\x04` comprise."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("AndroidManifest.xml", marque)
    return tampon.getvalue()


@pytest.fixture()
def caisse(monkeypatch, tmp_path) -> str:
    """Cle de caisse active et dossier d'upload isole du poste."""
    monkeypatch.setattr(settings, "caisse_api_key", CLE)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return CLE


@pytest.fixture()
def entetes_caisse(caisse) -> dict[str, str]:
    return {"X-Caisse-Key": caisse}


def _publier(client, super_admin_user, auth_headers, contenu=None, code=3, nom="0.3.0"):
    return client.post(
        "/api/v1/buvette/app",
        files={"file": ("caisse.apk", contenu or _apk(), "application/vnd.android.package-archive")},
        data={"version_code": code, "version_name": nom},
        headers=auth_headers(super_admin_user),
    )


def test_publier_puis_servir_a_la_tablette(
    client: TestClient, super_admin_user, auth_headers, entetes_caisse
):
    contenu = _apk()
    publication = _publier(client, super_admin_user, auth_headers, contenu)
    assert publication.status_code == 200, publication.text
    publie = publication.json()
    assert publie["version_code"] == 3
    assert publie["sha256"] == hashlib.sha256(contenu).hexdigest()
    assert publie["taille"] == len(contenu)

    version = client.get("/api/v1/buvette/caisse/app", headers=entetes_caisse)
    assert version.status_code == 200, version.text
    annonce = version.json()
    assert annonce["version_code"] == 3
    assert annonce["version_name"] == "0.3.0"
    # L'empreinte annoncee doit etre celle du fichier servi : la tablette
    # supprime le telechargement et n'installe rien si elles different.
    assert annonce["sha256"] == hashlib.sha256(contenu).hexdigest()

    apk = client.get("/api/v1/buvette/caisse/app/apk", headers=entetes_caisse)
    assert apk.status_code == 200
    assert apk.headers["content-type"] == "application/vnd.android.package-archive"
    assert hashlib.sha256(apk.content).hexdigest() == annonce["sha256"]


def test_l_apk_n_est_jamais_servi_sans_la_cle(
    client: TestClient, super_admin_user, auth_headers, entetes_caisse
):
    """Il porte la cle SumUp et CAISSE_API_KEY en clair."""
    _publier(client, super_admin_user, auth_headers)

    assert client.get("/api/v1/buvette/caisse/app/apk").status_code == 401
    assert client.get("/api/v1/buvette/caisse/app").status_code == 401
    assert (
        client.get(
            "/api/v1/buvette/caisse/app/apk", headers={"X-Caisse-Key": "mauvaise-cle"}
        ).status_code
        == 401
    )


def test_sans_cle_configuree_les_routes_n_existent_pas(
    client: TestClient, monkeypatch, super_admin_user, auth_headers
):
    """Meme parti que le reste de la caisse : coupee, elle est invisible."""
    monkeypatch.setattr(settings, "caisse_api_key", "")
    assert client.get("/api/v1/buvette/caisse/app").status_code == 404


def test_seul_le_super_admin_publie(
    client: TestClient, admin_benevoles_user, compta_user, benevole_user, auth_headers, caisse
):
    for compte in (admin_benevoles_user, compta_user, benevole_user):
        reponse = client.post(
            "/api/v1/buvette/app",
            files={"file": ("caisse.apk", _apk(), "application/vnd.android.package-archive")},
            data={"version_code": 3, "version_name": "0.3.0"},
            headers=auth_headers(compte),
        )
        assert reponse.status_code == 403, compte.role


def test_un_fichier_qui_n_est_pas_un_apk_est_refuse(
    client: TestClient, super_admin_user, auth_headers, caisse
):
    reponse = _publier(client, super_admin_user, auth_headers, contenu=b"%PDF-1.4 pas un apk")
    assert reponse.status_code == 422


def test_aucune_version_publiee_repond_404(client: TestClient, entetes_caisse):
    """Etat normal tant que personne n'a publie : la tablette garde la sienne."""
    assert client.get("/api/v1/buvette/caisse/app", headers=entetes_caisse).status_code == 404
    assert client.get("/api/v1/buvette/caisse/app/apk", headers=entetes_caisse).status_code == 404


def test_publier_remplace_la_version_precedente(
    client: TestClient, super_admin_user, auth_headers, entetes_caisse
):
    """Une seule version est conservee : la tablette n'en demande jamais d'autre."""
    _publier(client, super_admin_user, auth_headers, _apk(b"ancienne"), code=3, nom="0.3.0")
    nouveau = _apk(b"nouvelle")
    _publier(client, super_admin_user, auth_headers, nouveau, code=4, nom="0.4.0")

    annonce = client.get("/api/v1/buvette/caisse/app", headers=entetes_caisse).json()
    assert annonce["version_code"] == 4
    assert annonce["sha256"] == hashlib.sha256(nouveau).hexdigest()

    apk = client.get("/api/v1/buvette/caisse/app/apk", headers=entetes_caisse)
    assert apk.content == nouveau


def test_retirer_la_version(
    client: TestClient, super_admin_user, auth_headers, entetes_caisse
):
    _publier(client, super_admin_user, auth_headers)
    retrait = client.delete("/api/v1/buvette/app", headers=auth_headers(super_admin_user))
    assert retrait.status_code == 200, retrait.text
    assert client.get("/api/v1/buvette/caisse/app", headers=entetes_caisse).status_code == 404


def test_l_ecran_d_administration_lit_la_version(
    client: TestClient, super_admin_user, admin_benevoles_user, auth_headers, caisse
):
    assert (
        client.get("/api/v1/buvette/app", headers=auth_headers(admin_benevoles_user)).json() is None
    )
    _publier(client, super_admin_user, auth_headers)
    etat = client.get("/api/v1/buvette/app", headers=auth_headers(admin_benevoles_user)).json()
    assert etat["version_name"] == "0.3.0"
    assert etat["depose_le"]


def test_un_manifeste_illisible_vaut_aucune_version(
    client: TestClient, super_admin_user, auth_headers, entetes_caisse
):
    """Servir un APK sans empreinte verifiable serait pire que ne rien servir."""
    _publier(client, super_admin_user, auth_headers)
    (settings.upload_path / "caisse-app" / "version.json").write_text("{ pas du json", encoding="utf-8")

    assert caisse_app.version_publiee() is None
    assert client.get("/api/v1/buvette/caisse/app", headers=entetes_caisse).status_code == 404


def test_le_script_de_publication_depuis_le_vps(tmp_path, monkeypatch, caisse):
    """Le script du VPS et l'ecran web aboutissent au meme endroit.

    C'est ce que la chaine de compilation de l'application appelle apres avoir
    copie l'APK dans le conteneur : il calcule l'empreinte et ecrit le manifeste
    lui-meme, parce qu'un APK depose seul ne serait servi a personne.
    """
    import json
    import sys

    sys.path.insert(0, "scripts")
    from publier_app_caisse import main  # noqa: PLC0415

    apk = tmp_path / "buvette.apk"
    apk.write_bytes(_apk(b"depuis-le-vps"))
    descripteur = tmp_path / "app.json"
    descripteur.write_text(
        json.dumps({"version_code": 7, "version_name": "0.7.0"}), encoding="utf-8"
    )

    monkeypatch.setattr(
        sys, "argv", ["publier", str(apk), "--depuis-json", str(descripteur)]
    )
    assert main() == 0

    version = caisse_app.version_publiee()
    assert version is not None
    assert (version.version_code, version.version_name) == (7, "0.7.0")
    assert version.sha256 == hashlib.sha256(apk.read_bytes()).hexdigest()


def test_le_script_refuse_un_apk_introuvable(tmp_path, monkeypatch, caisse):
    import sys

    sys.path.insert(0, "scripts")
    from publier_app_caisse import main  # noqa: PLC0415

    monkeypatch.setattr(sys, "argv", ["publier", str(tmp_path / "absent.apk"), "3", "0.3.0"])
    assert main() == 1
