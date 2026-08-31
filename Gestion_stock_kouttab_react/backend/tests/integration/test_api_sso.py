"""Passage signe depuis gestion.lekouttab.fr (POST /auth/sso/exchange).

Le jeton atteste une identite (email), jamais un droit : le compte existant
garde son role, le compte cree a la volee naît « BenevoleFrais ». Chaque jeton
est a usage unique (jti consomme en base), signe d'un secret dedie, et vit
60 secondes.
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Admin


pytestmark = pytest.mark.integration

SECRET_TEST = "secret-partage-de-test-suffisamment-long-1234"
URL = "/api/v1/auth/sso/exchange"


@pytest.fixture()
def sso_actif(monkeypatch):
    monkeypatch.setattr(settings, "sso_shared_secret", SECRET_TEST)
    return SECRET_TEST


def _jeton(
    secret: str = SECRET_TEST,
    *,
    email: str = "nora.benfdila@example.com",
    prenom: str = "Nora",
    nom: str = "Benfdila",
    typ: str = "sso",
    aud: str = "stock.lekouttab.fr",
    iss: str = "gestion.lekouttab.fr",
    vie: int = 45,
    jti: str | None = None,
) -> str:
    maintenant = int(time.time())
    charge = {
        "iss": iss,
        "aud": aud,
        "typ": typ,
        "jti": jti or uuid.uuid4().hex,
        "iat": maintenant,
        "exp": maintenant + vie,
        "email": email,
        "prenom": prenom,
        "nom": nom,
    }
    return jose_jwt.encode(charge, secret, algorithm="HS256")


def _echanger(client: TestClient, token: str):
    return client.post(URL, json={"token": token})


# ---- Fonctionnalite coupee -------------------------------------------------


def test_sans_secret_configure_l_echange_n_existe_pas(client: TestClient) -> None:
    # settings.sso_shared_secret vaut "" par defaut : la porte n'existe pas.
    resp = _echanger(client, _jeton())
    assert resp.status_code == 404, resp.text


# ---- Creation a la volee ---------------------------------------------------


def test_cree_un_compte_benevole_frais_actif_et_ouvre_la_session(
    client: TestClient, db_session: Session, sso_actif: str
) -> None:
    resp = _echanger(client, _jeton())
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["user"]["role"] == "BenevoleFrais"
    assert body["user"]["validation_status"] == "active"
    assert body["user"]["prenom"] == "Nora"

    # La session ouverte est une vraie session : /me repond.
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200, me.text

    cree = db_session.execute(
        select(Admin).where(Admin.email == "nora.benfdila@example.com")
    ).scalar_one()
    assert cree.role == "BenevoleFrais"
    assert cree.password_hash  # un hachage existe, mais personne ne connait le mot de passe


def test_le_username_genere_evite_les_collisions(
    client: TestClient, db_session: Session, sso_actif: str
) -> None:
    from app.crud import user as user_crud

    existant = user_crud.create_user(
        db_session,
        username="norabenfdila",
        password="Strong#Pass1",
        role="Benevole",
        email="autre@example.com",
    )

    resp = _echanger(client, _jeton(email="nora.benfdila@exemple.fr"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["username"] != existant.username


# ---- Rapprochement d'un compte existant ------------------------------------


def test_un_compte_existant_garde_son_role(
    client: TestClient, compta_user, sso_actif: str
) -> None:
    resp = _echanger(client, _jeton(email=compta_user.email.upper()))  # casse ignoree
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["id"] == compta_user.id
    assert resp.json()["user"]["role"] == "Compta"


def test_un_compte_en_attente_est_refuse(
    client: TestClient, pending_user, sso_actif: str
) -> None:
    resp = _echanger(client, _jeton(email=pending_user.email))
    assert resp.status_code != 200
    assert resp.json()["code"] == "AUTH_1002"


def test_deux_comptes_sur_le_meme_email_font_refuser(
    client: TestClient, db_session: Session, sso_actif: str
) -> None:
    from app.crud import user as user_crud

    for username in ("doublona", "doublonb"):
        user_crud.create_user(
            db_session,
            username=username,
            password="Strong#Pass1",
            role="Benevole",
            email="partage@example.com",
        )

    resp = _echanger(client, _jeton(email="partage@example.com"))
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "AUTH_1040"


# ---- Surete du jeton -------------------------------------------------------


def test_un_jeton_ne_sert_qu_une_fois(client: TestClient, sso_actif: str) -> None:
    token = _jeton()
    assert _echanger(client, token).status_code == 200
    rejoue = _echanger(client, token)
    assert rejoue.status_code == 401, rejoue.text


def test_un_jeton_expire_est_refuse(client: TestClient, sso_actif: str) -> None:
    resp = _echanger(client, _jeton(vie=-10))
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_1010"


def test_une_duree_de_vie_excessive_est_refusee(client: TestClient, sso_actif: str) -> None:
    # Un emetteur mal configure qui signerait des jetons d'une heure ne doit
    # pas elargir la fenetre de rejeu : la borne est verifiee cote stock aussi.
    resp = _echanger(client, _jeton(vie=3600))
    assert resp.status_code == 401


def test_une_mauvaise_audience_est_refusee(client: TestClient, sso_actif: str) -> None:
    assert _echanger(client, _jeton(aud="autre.example.com")).status_code == 401


def test_une_mauvaise_signature_est_refusee(client: TestClient, sso_actif: str) -> None:
    assert _echanger(client, _jeton(secret="un-autre-secret-tout-aussi-long-99")).status_code == 401


def test_un_jeton_d_un_autre_type_est_refuse(client: TestClient, sso_actif: str) -> None:
    # Meme bien signe, un jeton qui n'est pas de type "sso" n'ouvre rien.
    assert _echanger(client, _jeton(typ="access")).status_code == 401


def test_un_jeton_sans_email_est_refuse(client: TestClient, sso_actif: str) -> None:
    maintenant = int(time.time())
    charge = {
        "iss": "gestion.lekouttab.fr",
        "aud": "stock.lekouttab.fr",
        "typ": "sso",
        "jti": uuid.uuid4().hex,
        "iat": maintenant,
        "exp": maintenant + 45,
    }
    token = jose_jwt.encode(charge, SECRET_TEST, algorithm="HS256")
    assert _echanger(client, token).status_code == 401


# ---- Pastille inter-applications -------------------------------------------
#
# L'outil de gestion demande, serveur a serveur, ce que son utilisateur a
# « a lire » cote stock — pour afficher la pastille sur SON entree
# « Notes de frais ». Jeton dedie (typ 'sso-pastille'), 60 s, lecture seule.


def _jeton_pastille(secret: str = SECRET_TEST, **surcharges) -> str:
    surcharges.setdefault("typ", "sso-pastille")
    return _jeton(secret, **surcharges)


def test_pastille_rend_les_compteurs_du_compte(
    client: TestClient, db_session, benevole_user, sso_actif: str
) -> None:
    from datetime import date
    from decimal import Decimal
    from app.crud import expense as expense_crud

    note = expense_crud.create_expense(
        db_session,
        user_id=benevole_user.id,
        date_depense=date(2026, 8, 12),
        rattachement="Frais",
        fournisseur="Action",
        nature_charge="Courses",
        montant=Decimal("5.00"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
    )
    note.non_lu_demandeur = True
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/sso/pastille",
        json={"token": _jeton_pastille(email=benevole_user.email)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"notes_suivies": 1, "factures_suivies": 0}


def test_pastille_compte_inconnu_rend_zero_pas_une_erreur(
    client: TestClient, sso_actif: str
) -> None:
    # Distinguer « inconnu » de « rien a lire » ferait de l'endpoint un test
    # d'existence de compte pour qui tient le secret. Zero dans les deux cas.
    resp = client.post(
        "/api/v1/auth/sso/pastille",
        json={"token": _jeton_pastille(email="personne@example.com")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"notes_suivies": 0, "factures_suivies": 0}


def test_pastille_refuse_un_jeton_de_session(client: TestClient, sso_actif: str) -> None:
    # Le jeton d'echange (typ 'sso') ouvre une session ; il ne doit pas servir
    # ici, ni l'inverse — chaque porte a son type.
    resp = client.post(
        "/api/v1/auth/sso/pastille", json={"token": _jeton(email="x@example.com")}
    )
    assert resp.status_code == 401


def test_pastille_refuse_une_mauvaise_signature(client: TestClient, sso_actif: str) -> None:
    resp = client.post(
        "/api/v1/auth/sso/pastille",
        json={"token": _jeton_pastille(secret="un-autre-secret-tout-aussi-long-99")},
    )
    assert resp.status_code == 401


def test_pastille_sans_secret_configure_n_existe_pas(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/sso/pastille", json={"token": _jeton_pastille()})
    assert resp.status_code == 404
