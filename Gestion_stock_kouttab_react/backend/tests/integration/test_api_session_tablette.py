"""Session « tablette » : l'app stock dans l'écran Personnel de la tablette de caisse.

Contrat (10/10/2026) : compte système partagé « Tablette buvette » (AdminStock),
sans mot de passe utilisable ; `POST /auth/caisse/session` (clé de la caisse +
nom de l'opérateur) ouvre une session dont les jetons portent `op` ; le refresh
le conserve ; chaque action est signée « Nom (tablette) » ; le compte ne reçoit
aucun courriel de la buvette.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.core.tablette import EMAIL_TABLETTE, USERNAME_TABLETTE, nom_auteur
from app.crud import buvette as buvette_crud
from app.crud import tablette as tablette_crud
from app.main import app


pytestmark = pytest.mark.integration

CLE = "cle-de-test-de-la-caisse-au-moins-32-caracteres"
SESSION = "/api/v1/auth/caisse/session"
API = "/api/v1/buvette"


@pytest.fixture(autouse=True)
def _caisse_activee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", CLE)


@pytest.fixture()
def compte(db_session: Session):
    return tablette_crud.garantir_compte_tablette(db_session)


def _ouvrir(client: TestClient, nom: str = "Youssef", cle: str | None = CLE):
    entetes = {"X-Caisse-Key": cle} if cle is not None else {}
    return client.post(SESSION, json={"operateur": nom}, headers=entetes)


def _api(jeton: str) -> TestClient:
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {jeton}"})
    return c


# ---------------------------------------------------------------------------
# Ouverture de session
# ---------------------------------------------------------------------------


def test_session_avec_cle(client: TestClient, compte) -> None:
    reponse = _ouvrir(client, "  Youssef   B. ")
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["token_type"] == "bearer"
    assert corps["operateur"] == "Youssef B."
    assert corps["user"]["username"] == USERNAME_TABLETTE
    assert corps["user"]["role"] == "AdminStock"
    assert decode_token(corps["access_token"])["op"] == "Youssef B."
    assert decode_token(corps["refresh_token"])["op"] == "Youssef B."


def test_session_sans_cle_ou_cle_fausse(client: TestClient, compte) -> None:
    assert _ouvrir(client, cle=None).status_code == 401
    assert _ouvrir(client, cle="mauvaise-cle").status_code == 401
    # Cle fausse ET nom invalide : la cle est verifiee d'abord.
    assert _ouvrir(client, nom="x", cle="mauvaise-cle").status_code == 401


def test_session_caisse_non_configuree(
    client: TestClient, compte, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", "")
    assert _ouvrir(client).status_code == 404


@pytest.mark.parametrize("nom", ["", " ", "a", "  b  ", "x" * 61, "\x00\x07"])
def test_nom_invalide(client: TestClient, compte, nom: str) -> None:
    assert _ouvrir(client, nom).status_code == 422


def test_nom_nettoye_des_caracteres_de_controle(client: TestClient, compte) -> None:
    reponse = _ouvrir(client, "Ab​d\tel\nkader")
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["operateur"] == "Abd el kader"


def test_compte_absent(client: TestClient) -> None:
    assert _ouvrir(client).status_code == 404


def test_compte_desactive(client: TestClient, compte, db_session: Session) -> None:
    compte.validation_status = "rejected"
    db_session.commit()
    assert _ouvrir(client).status_code == 404


# ---------------------------------------------------------------------------
# Jetons : `op` dans le jeton, conserve au refresh, renvoye par /me
# ---------------------------------------------------------------------------


def test_op_conserve_au_refresh(client: TestClient, compte) -> None:
    premier = _ouvrir(client, "Amina").json()
    reponse = client.post("/api/v1/auth/refresh", json={"refresh_token": premier["refresh_token"]})
    assert reponse.status_code == 200, reponse.text
    second = reponse.json()
    assert second["operateur"] == "Amina"
    assert decode_token(second["access_token"])["op"] == "Amina"
    assert decode_token(second["refresh_token"])["op"] == "Amina"
    # Et encore apres une deuxieme rotation.
    troisieme = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    ).json()
    assert decode_token(troisieme["access_token"])["op"] == "Amina"


def test_me_renvoie_l_operateur(client: TestClient, compte) -> None:
    jeton = _ouvrir(client, "Amina").json()["access_token"]
    moi = _api(jeton).get("/api/v1/auth/me").json()
    assert moi["operateur"] == "Amina"
    assert moi["username"] == USERNAME_TABLETTE


def test_me_hors_tablette(client_authenticated_as, admin_stock_user) -> None:
    moi = client_authenticated_as(admin_stock_user).get("/api/v1/auth/me").json()
    assert moi["operateur"] is None


def test_op_ignore_pour_un_autre_compte(admin_stock_user) -> None:
    """Un `op` glisse dans le jeton d'un compte ordinaire ne signe rien."""
    from app.core.security import create_access_token

    jeton = create_access_token(admin_stock_user.id, "AdminStock", extra={"op": "Faux"})
    assert _api(jeton).get("/api/v1/auth/me").json()["operateur"] is None


def test_refresh_d_un_compte_ordinaire_sans_op(client: TestClient, admin_stock_user) -> None:
    reponse = client.post(
        "/api/v1/auth/login/json",
        json={"username": admin_stock_user.username, "password": admin_stock_user._plain_password},
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["operateur"] is None
    assert "op" not in decode_token(reponse.json()["access_token"])


# ---------------------------------------------------------------------------
# Droits : AdminStock seulement ; jamais de connexion par mot de passe
# ---------------------------------------------------------------------------


def test_droits_admin_stock_seulement(client: TestClient, compte) -> None:
    api = _api(_ouvrir(client).json()["access_token"])
    assert api.get(f"{API}/products").status_code == 200
    assert api.get(f"{API}/reglages").status_code == 403  # reserve aux admins
    assert api.get("/api/v1/users").status_code == 403
    assert api.get("/api/v1/stock/items").status_code == 403


@pytest.mark.parametrize(
    "identifiant", [USERNAME_TABLETTE, EMAIL_TABLETTE]
)
@pytest.mark.parametrize(
    "mot_de_passe", ["", "x", "!compte-systeme-tablette-sans-mot-de-passe"]
)
def test_connexion_par_mot_de_passe_impossible(
    client: TestClient, compte, identifiant: str, mot_de_passe: str
) -> None:
    reponse = client.post(
        "/api/v1/auth/login",
        data={"username": identifiant, "password": mot_de_passe},
    )
    assert reponse.status_code in (401, 422)
    if mot_de_passe:
        reponse = client.post(
            "/api/v1/auth/login/json",
            json={"username": identifiant, "password": mot_de_passe},
        )
        assert reponse.status_code == 401


def test_reinitialisation_sans_effet(client: TestClient, compte, captured_emails) -> None:
    reponse = client.post(
        "/api/v1/auth/forgot-password", json={"identifiant": USERNAME_TABLETTE}
    )
    assert reponse.status_code == 200
    assert not [m for m in captured_emails if EMAIL_TABLETTE in m.recipients]


def test_role_du_compte_verrouille(
    client_authenticated_as, super_admin_user, compte
) -> None:
    su = client_authenticated_as(super_admin_user)
    reponse = su.patch(f"/api/v1/users/{compte.id}/role", json={"role": "Super Admin"})
    assert reponse.status_code == 403


# ---------------------------------------------------------------------------
# Auteur « Nom (tablette) » : inventaire, cloture, reappro, creation de produit
# ---------------------------------------------------------------------------


def test_auteur_inventaire(client: TestClient, compte) -> None:
    api = _api(_ouvrir(client, "Youssef").json()["access_token"])
    reponse = api.post(f"{API}/inventaires")
    assert reponse.status_code == 201, reponse.text
    assert reponse.json()["cree_par"] == "Youssef (tablette)"


def test_auteur_cloture(client: TestClient, compte) -> None:
    api = _api(_ouvrir(client, "Youssef").json()["access_token"])
    hier = (buvette_crud.aujourd_hui() - timedelta(days=1)).isoformat()
    reponse = api.post(f"{API}/clotures", json={"compte_cents": 0, "debut": hier})
    assert reponse.status_code == 201, reponse.text
    assert reponse.json()["saisi_par"] == "Youssef (tablette)"


def test_auteur_reappro_et_creation(client: TestClient, compte) -> None:
    api = _api(_ouvrir(client, "Youssef").json()["access_token"])
    produit = api.post(
        f"{API}/products",
        json={
            "name": "Jus tablette",
            "price_cents": 150,
            "quantity": 4,
            "seuil_alerte": 2,
            "caisse_category": "boissons",
        },
    )
    assert produit.status_code == 201, produit.text
    reponse = api.post(
        f"{API}/products/{produit.json()['id']}/reappro",
        json={"quantite": 6, "prix_achat_unitaire_cents": 80},
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["reappro"]["fait_par"] == "Youssef (tablette)"
    historique = api.get(f"{API}/reapprovisionnements").json()
    auteurs = {r["fait_par"] for r in historique["reappros"]}
    # Stock initial (creation) ET reappro : tous deux signes par l'operateur.
    assert auteurs == {"Youssef (tablette)"}


def test_auteur_suit_le_refresh(client: TestClient, compte) -> None:
    premier = _ouvrir(client, "Amina").json()
    second = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": premier["refresh_token"]}
    ).json()
    reponse = _api(second["access_token"]).post(f"{API}/inventaires")
    assert reponse.json()["cree_par"] == "Amina (tablette)"


def test_nom_auteur_hors_tablette(admin_stock_user) -> None:
    assert nom_auteur(admin_stock_user) == admin_stock_user.full_name


# ---------------------------------------------------------------------------
# Courriels : le compte n'est jamais destinataire
# ---------------------------------------------------------------------------


def test_compte_exclu_des_destinataires(
    db_session: Session, compte, admin_stock_user
) -> None:
    destinataires = [a.lower() for a in buvette_crud.destinataires_buvette(db_session)]
    assert EMAIL_TABLETTE not in destinataires
    assert admin_stock_user.email.lower() in destinataires
    comptes = buvette_crud.comptes_admin_stock(db_session)
    assert compte.id not in {c.id for c in comptes}
