"""Les notes de frais d'un evenement, lues par gestion.lekouttab.fr.

POST /api/v1/auth/sso/depenses — lecture serveur a serveur, jeton dedie
(typ 'sso-depenses', 60 s), signe du secret partage. L'outil de gestion s'en
sert pour afficher le bilan d'un evenement : ce qu'il a rapporte, ce qu'il a
coute, et le resultat.

Trois proprietes sont verrouillees ici :

 1. **L'identifiant de l'evenement est DANS le jeton signe**, jamais dans le
    corps. Sans cela, quiconque tient le secret partage balaierait tous les
    evenements en changeant un parametre.
 2. **Une note rattachee en saisie libre compte autant qu'une note rattachee au
    referentiel.** Les deux coexistent en base (`crud.event.resolve_event` le
    dit explicitement) : ne filtrer que sur `id_event` ferait disparaitre du
    total toutes les notes deposees avant que la synchro HelloAsso ait cree la
    ligne d'evenement.
 3. **Un evenement inconnu rend une liste vide, jamais une erreur.** Distinguer
    ferait de l'endpoint un test d'existence pour qui tient le secret — meme
    doctrine que la pastille.
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.core.config import settings
from app.crud import expense as expense_crud
from app.db.models import Event


pytestmark = pytest.mark.integration

SECRET_TEST = "secret-partage-de-test-suffisamment-long-1234"
URL = "/api/v1/auth/sso/depenses"
TITRE = "Soiree cinema Bilal (J)"
SLUG = "soiree-bilal"


@pytest.fixture()
def sso_actif(monkeypatch):
    monkeypatch.setattr(settings, "sso_shared_secret", SECRET_TEST)
    return SECRET_TEST


@pytest.fixture()
def evenement(db_session) -> Event:
    ev = Event(
        nom=TITRE,
        helloasso_form_slug=SLUG,
        helloasso_form_type="Event",
        date_evenement=date(2026, 8, 30),
        source="helloasso",
        type_ev="J",
    )
    db_session.add(ev)
    db_session.commit()
    db_session.refresh(ev)
    return ev


def _jeton(
    secret: str = SECRET_TEST,
    *,
    email: str = "staff@example.com",
    typ: str = "sso-depenses",
    slug: str | None = SLUG,
    titre: str | None = TITRE,
    aud: str = "stock.lekouttab.fr",
    iss: str = "gestion.lekouttab.fr",
    vie: int = 45,
) -> str:
    maintenant = int(time.time())
    charge = {
        "iss": iss,
        "aud": aud,
        "typ": typ,
        "jti": uuid.uuid4().hex,
        "iat": maintenant,
        "exp": maintenant + vie,
        "email": email,
        "slug": slug,
        "titre": titre,
    }
    return jose_jwt.encode(charge, secret, algorithm="HS256")


def _note(db_session, user, **surcharges):
    """Une note de frais, rattachee a l'evenement sauf indication contraire."""
    parametres = {
        "date_depense": date(2026, 8, 30),
        "rattachement": "Frais",
        "fournisseur": "SNCF",
        "nature_charge": "Billets de train",
        "montant": Decimal("84.60"),
        "commentaires": None,
        "remboursement_deja_emis": Decimal("0"),
        "remise": Decimal("0"),
        "evenement": TITRE,
        "categorie": "Transport",
    }
    parametres.update(surcharges)
    return expense_crud.create_expense(db_session, user_id=user.id, **parametres)


# ---- Fonctionnalite coupee -------------------------------------------------


def test_sans_secret_configure_la_porte_n_existe_pas(client: TestClient) -> None:
    resp = client.post(URL, json={"token": _jeton()})
    assert resp.status_code == 404


# ---- Contrat du jeton ------------------------------------------------------


def test_refuse_un_jeton_de_session(client: TestClient, sso_actif: str) -> None:
    # Chaque porte a son type : un jeton d'echange n'ouvre pas cette lecture.
    resp = client.post(URL, json={"token": _jeton(typ="sso")})
    assert resp.status_code == 401


def test_refuse_un_jeton_de_pastille(client: TestClient, sso_actif: str) -> None:
    resp = client.post(URL, json={"token": _jeton(typ="sso-pastille")})
    assert resp.status_code == 401


def test_refuse_une_mauvaise_signature(client: TestClient, sso_actif: str) -> None:
    resp = client.post(URL, json={"token": _jeton("un-autre-secret-tout-aussi-long-1234")})
    assert resp.status_code == 401


def test_refuse_une_mauvaise_audience(client: TestClient, sso_actif: str) -> None:
    resp = client.post(URL, json={"token": _jeton(aud="ailleurs.example.com")})
    assert resp.status_code == 401


def test_refuse_un_emetteur_inconnu(client: TestClient, sso_actif: str) -> None:
    resp = client.post(URL, json={"token": _jeton(iss="attaquant.example.com")})
    assert resp.status_code == 401


def test_refuse_un_jeton_de_longue_duree(client: TestClient, sso_actif: str) -> None:
    # Un emetteur mal configure qui signerait des jetons d'une heure ne doit pas
    # elargir la fenetre de rejeu.
    resp = client.post(URL, json={"token": _jeton(vie=3600)})
    assert resp.status_code == 401


# ---- La lecture ------------------------------------------------------------


def test_rend_les_notes_rattachees_par_identifiant(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    note = _note(db_session, benevole_user, id_event=evenement.id)

    resp = client.post(URL, json={"token": _jeton()})

    assert resp.status_code == 200, resp.text
    corps = resp.json()
    assert corps["evenement_trouve"] is True
    assert len(corps["lignes"]) == 1
    ligne = corps["lignes"][0]
    assert ligne["id"] == note.id
    # Montants en chaine : un float perdrait des centimes en route.
    assert ligne["montant"] == "84.60"
    assert ligne["remise"] == "0.00"
    assert ligne["statut"] == "En attente"
    assert ligne["categorie"] == "Transport"
    assert ligne["date_depense"] == "2026-08-30"


def test_rend_aussi_les_notes_rattachees_en_saisie_libre(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    # Note deposee avant que la synchro HelloAsso cree la ligne d'evenement :
    # `id_event` est nul, seul le libelle porte le rattachement. C'est un cas
    # nominal, pas une degradation — l'ignorer amputerait le bilan.
    _note(db_session, benevole_user, id_event=None, evenement=TITRE)

    resp = client.post(URL, json={"token": _jeton()})

    assert resp.status_code == 200
    assert len(resp.json()["lignes"]) == 1


def test_ne_compte_pas_deux_fois_une_note_rattachee_des_deux_facons(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    _note(db_session, benevole_user, id_event=evenement.id, evenement=TITRE)

    resp = client.post(URL, json={"token": _jeton()})

    assert len(resp.json()["lignes"]) == 1


def test_retrouve_l_evenement_par_son_nom_quand_le_slug_est_absent(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    # Un evenement cree a la main dans l'outil de gestion n'a pas de formulaire
    # HelloAsso : le titre est alors la seule clef disponible.
    _note(db_session, benevole_user, id_event=evenement.id)

    resp = client.post(URL, json={"token": _jeton(slug=None)})

    assert resp.status_code == 200
    assert len(resp.json()["lignes"]) == 1


def test_ecarte_une_note_refusee(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    note = _note(db_session, benevole_user, id_event=evenement.id)
    note.status = "Refusée"
    db_session.commit()

    resp = client.post(URL, json={"token": _jeton()})

    assert resp.json()["lignes"] == []


def test_ecarte_une_note_archivee(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    from datetime import datetime

    note = _note(db_session, benevole_user, id_event=evenement.id)
    note.archived_at = datetime(2026, 9, 1, 10, 0, 0)
    db_session.commit()

    resp = client.post(URL, json={"token": _jeton()})

    assert resp.json()["lignes"] == []


def test_ne_rend_pas_les_notes_d_un_autre_evenement(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    _note(db_session, benevole_user, id_event=None, evenement="Kermesse (G)")

    resp = client.post(URL, json={"token": _jeton()})

    assert resp.json()["lignes"] == []


def test_evenement_inconnu_rend_une_liste_vide_pas_une_erreur(
    client: TestClient, sso_actif: str
) -> None:
    resp = client.post(
        URL, json={"token": _jeton(slug="inexistant", titre="Rien de connu")}
    )

    assert resp.status_code == 200
    assert resp.json() == {"evenement_trouve": False, "lignes": []}


def test_jeton_sans_evenement_rend_une_liste_vide(
    client: TestClient, sso_actif: str
) -> None:
    resp = client.post(URL, json={"token": _jeton(slug=None, titre=None)})

    assert resp.status_code == 200
    assert resp.json() == {"evenement_trouve": False, "lignes": []}


def test_nomme_le_demandeur_sans_exposer_son_email(
    client: TestClient, db_session, benevole_user, evenement, sso_actif: str
) -> None:
    # Le bilan affiche qui a engage la depense. Son email n'y sert a rien, et
    # l'outil de gestion n'a pas besoin de le connaitre pour cela.
    _note(db_session, benevole_user, id_event=evenement.id)

    ligne = client.post(URL, json={"token": _jeton()}).json()["lignes"][0]

    assert "email" not in ligne
    assert "demandeur" in ligne
