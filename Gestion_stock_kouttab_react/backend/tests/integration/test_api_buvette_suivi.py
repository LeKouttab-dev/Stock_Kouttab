"""Suivi de la buvette (09/10/2026) : paiements, statistiques,
etat de la tablette, reappro atomique, reglages, role AdminStock, courriels.

Contrat d'API commun backend / frontend / tablette : montants en centimes,
moyen de paiement DEDUIT (carte = tablette + code SumUp, especes = tablette
sans code, helloasso = boutique), jour d'une vente = date de `sold_at`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct, BuvetteSale, CaisseEtat
from app.schemas.buvette import BuvetteProductCreate, CaisseVenteIn


pytestmark = pytest.mark.integration

CLE = "cle-de-test-de-la-caisse-au-moins-32-caracteres"
API = "/api/v1/buvette"
JOUR = date(2026, 10, 5)


@pytest.fixture(autouse=True)
def _caisse_activee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caisse_api_key", CLE)


def _entetes(cle: str = CLE) -> dict[str, str]:
    return {"X-Caisse-Key": cle}


def _produit(
    db: Session, *, nom: str | None = None, quantite: int = 10, seuil: int = 5, prix: int = 150
) -> BuvetteProduct:
    return buvette_crud.create_product(
        db,
        BuvetteProductCreate(
            name=nom or f"Produit_{uuid.uuid4().hex[:6]}",
            price_cents=prix,
            quantity=quantite,
            seuil_alerte=seuil,
            caisse_category="sucre_sale",
        ),
    )


def _vente_caisse(
    client: TestClient,
    lignes: list[tuple[BuvetteProduct, int]],
    *,
    carte: bool = True,
    quand: datetime | None = None,
) -> str:
    tx = str(uuid.uuid4())
    corps = {
        "transaction_id": tx,
        "sumup_tx_code": f"TX{uuid.uuid4().hex[:8]}" if carte else None,
        "total_cents": sum(q * p.price_cents for p, q in lignes),
        "sold_at": (quand or datetime.combine(JOUR, time(10, 0))).isoformat() + "+02:00",
        "lines": [
            {"product_id": p.id, "name": p.name, "quantity": q, "unit_price_cents": p.price_cents}
            for p, q in lignes
        ],
    }
    reponse = client.post(f"{API}/caisse/ventes", json=corps, headers=_entetes())
    assert reponse.status_code == 201, reponse.text
    return tx


def _vente_helloasso(
    db: Session, *, order_id: int, item_id: int, nom: str, montant: int, quand: datetime
) -> None:
    buvette_crud.record_sale_and_decrement(
        db,
        order_id=order_id,
        payment_id=order_id * 10,
        item_id=item_id,
        tier_id=None,
        name=nom,
        quantity_sold=1,
        amount_cents=montant,
        customer={"firstName": "Yusuf", "lastName": "Martin"},
        sold_at=quand,
        raw_event=None,
    )


def _quantite(db: Session, produit_id: int) -> int:
    db.expire_all()
    return db.get(BuvetteProduct, produit_id).quantity


# ---------------------------------------------------------------------------
# Moyen de paiement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "code", "attendu"),
    [("caisse", "TX123", "carte"), ("caisse", None, "especes"), ("helloasso", None, "helloasso")],
)
def test_le_moyen_de_paiement_se_deduit_sans_colonne(source, code, attendu) -> None:
    vente = BuvetteSale(source=source, sumup_tx_code=code, product_name_snapshot="x")
    assert buvette_crud.moyen_de_paiement(vente) == attendu


# ---------------------------------------------------------------------------
# Paiements
# ---------------------------------------------------------------------------


@pytest.fixture()
def journee(client: TestClient, db_session: Session) -> dict[str, Any]:
    """Une journee type : un panier carte de deux articles, une vente especes,
    une commande HelloAsso de deux articles, et une vente la veille."""
    the = _produit(db_session, nom="The", prix=100)
    gateau = _produit(db_session, nom="Gateau", prix=250)
    carte = _vente_caisse(client, [(the, 2), (gateau, 1)], quand=datetime.combine(JOUR, time(10, 15)))
    especes = _vente_caisse(client, [(gateau, 2)], carte=False, quand=datetime.combine(JOUR, time(16, 40)))
    _vente_helloasso(db_session, order_id=77, item_id=1, nom="Jus", montant=200,
                     quand=datetime.combine(JOUR, time(12, 5)))
    _vente_helloasso(db_session, order_id=77, item_id=2, nom="The", montant=100,
                     quand=datetime.combine(JOUR, time(12, 5)))
    _vente_caisse(client, [(the, 1)], quand=datetime.combine(JOUR - timedelta(days=1), time(18, 0)))
    return {"carte": carte, "especes": especes, "the": the, "gateau": gateau}


def test_les_paiements_regroupent_les_lignes_par_vente(
    journee, client_authenticated_as, compta_user
) -> None:
    reponse = client_authenticated_as(compta_user).get(
        f"{API}/paiements", params={"debut": JOUR.isoformat(), "fin": JOUR.isoformat()}
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()

    paiements = corps["paiements"]
    assert [p["moyen"] for p in paiements] == ["especes", "helloasso", "carte"]  # recent d'abord
    especes, helloasso, carte = paiements
    assert carte["cle"] == journee["carte"]
    assert carte["total_cents"] == 2 * 100 + 250
    assert carte["sumup_tx_code"].startswith("TX")
    assert [(a["nom"], a["quantite"], a["montant_cents"]) for a in carte["articles"]] == [
        ("The", 2, 200),
        ("Gateau", 1, 250),
    ]
    assert especes["sumup_tx_code"] is None and especes["total_cents"] == 500
    assert helloasso["cle"] == "ha-77"
    assert helloasso["helloasso_order_id"] == 77
    assert helloasso["client"] == "Yusuf Martin"
    assert len(helloasso["articles"]) == 2 and helloasso["total_cents"] == 300

    assert corps["totaux"] == {
        "carte_cents": 450,
        "especes_cents": 500,
        "helloasso_cents": 300,
        "total_cents": 1250,
        # Frais SumUp par transaction : 1,70 % de 4,50 € = 7,65 cts, arrondi a 8.
        "frais_carte_cents": 8,
        "carte_net_cents": 442,
        "net_total_cents": 1242,
        "nb_ventes": 3,
        "taux_frais_carte_pb": 170,
    }
    assert (carte["frais_cents"], carte["net_cents"]) == (8, 442)
    assert (especes["frais_cents"], especes["net_cents"]) == (None, 500)
    assert (helloasso["frais_cents"], helloasso["net_cents"]) == (None, 300)


def test_les_paiements_se_filtrent_par_moyen(journee, client_authenticated_as, admin_stock_user) -> None:
    corps = client_authenticated_as(admin_stock_user).get(
        f"{API}/paiements",
        params={"debut": (JOUR - timedelta(days=1)).isoformat(), "fin": JOUR.isoformat(), "moyen": "carte"},
    ).json()
    assert {p["moyen"] for p in corps["paiements"]} == {"carte"}
    assert corps["totaux"]["nb_ventes"] == 2  # la veille comprise
    assert corps["totaux"]["especes_cents"] == 0


def test_les_paiements_par_defaut_portent_sur_aujourd_hui(
    client: TestClient, db_session: Session, client_authenticated_as, admin_benevoles_user
) -> None:
    produit = _produit(db_session)
    aujourd_hui = buvette_crud.aujourd_hui()
    _vente_caisse(client, [(produit, 1)], quand=datetime.combine(aujourd_hui, time(0, 30)))
    _vente_caisse(client, [(produit, 1)], quand=datetime.combine(aujourd_hui - timedelta(days=3), time(9)))

    corps = client_authenticated_as(admin_benevoles_user).get(f"{API}/paiements").json()
    assert corps["totaux"]["nb_ventes"] == 1


def test_une_periode_a_l_envers_est_refusee(client_authenticated_as, compta_user) -> None:
    reponse = client_authenticated_as(compta_user).get(
        f"{API}/paiements", params={"debut": "2026-10-05", "fin": "2026-10-01"}
    )
    assert reponse.status_code == 422


def test_un_benevole_ne_voit_pas_les_paiements(client_authenticated_as, benevole_user) -> None:
    assert client_authenticated_as(benevole_user).get(f"{API}/paiements").status_code == 403


# ---------------------------------------------------------------------------
# Statistiques
# ---------------------------------------------------------------------------


def test_les_statistiques_comptent_des_ventes_et_non_des_lignes(
    journee, client_authenticated_as, admin_benevoles_user
) -> None:
    debut = JOUR - timedelta(days=2)
    corps = client_authenticated_as(admin_benevoles_user).get(
        f"{API}/stats", params={"debut": debut.isoformat(), "fin": JOUR.isoformat()}
    ).json()

    assert corps["par_jour"] == [
        {"jour": debut.isoformat(), "ca_cents": 0, "ventes": 0, "net_cents": 0},  # jour sans vente
        {"jour": (JOUR - timedelta(days=1)).isoformat(), "ca_cents": 100, "ventes": 1, "net_cents": 98},
        {"jour": JOUR.isoformat(), "ca_cents": 1250, "ventes": 3, "net_cents": 1242},
    ]
    assert corps["totaux"] == {
        "ca_cents": 1350, "frais_carte_cents": 10, "net_cents": 1340, "ventes": 4,
        "taux_frais_carte_pb": 170,
    }
    assert len(corps["par_heure"]) == 24
    heures = {h["heure"]: h for h in corps["par_heure"]}
    assert heures[10] == {"heure": 10, "ca_cents": 450, "ventes": 1, "net_cents": 442}
    assert heures[3]["ventes"] == 0

    assert corps["par_produit"][0] == {"nom": "Gateau", "quantite": 3, "ca_cents": 750}
    the = next(p for p in corps["par_produit"] if p["nom"] == "The")
    assert the == {"nom": "The", "quantite": 4, "ca_cents": 400}

    moyens = {m["moyen"]: m for m in corps["par_moyen"]}
    assert moyens["carte"] == {"moyen": "carte", "ca_cents": 550, "ventes": 2, "net_cents": 540}
    assert moyens["especes"]["ventes"] == 1
    assert moyens["helloasso"]["ca_cents"] == 300


def test_les_statistiques_couvrent_trente_jours_par_defaut(client_authenticated_as, compta_user) -> None:
    corps = client_authenticated_as(compta_user).get(f"{API}/stats").json()
    assert len(corps["par_jour"]) == 30
    assert corps["par_jour"][-1]["jour"] == buvette_crud.aujourd_hui().isoformat()


# ---------------------------------------------------------------------------
# Etat de la tablette
# ---------------------------------------------------------------------------


def _etat(**surcharges: Any) -> dict[str, Any]:
    etat = {
        "batterie_pct": 87,
        "en_charge": True,
        "version_code": 7,
        "version_name": "0.7.0",
        "sumup_connecte": True,
        "lecteur_connecte": False,
        "lecteur_batterie_pct": None,
        "ventes_en_attente": 2,
        "ventes_rejetees": 0,
        "ecran": "accueil",
    }
    etat.update(surcharges)
    return etat


def test_l_etat_de_la_tablette_exige_la_cle(client: TestClient) -> None:
    assert client.post(f"{API}/caisse/etat", json=_etat()).status_code == 401
    assert client.post(f"{API}/caisse/etat", json=_etat(), headers=_entetes("faux")).status_code == 401


def test_le_dernier_etat_recu_est_lisible_par_l_admin(
    client: TestClient, client_authenticated_as, admin_stock_user, db_session: Session
) -> None:
    lecteur = client_authenticated_as(admin_stock_user)
    assert lecteur.get(f"{API}/caisse/etat").json() == {"etat": None}

    assert client.post(f"{API}/caisse/etat", json=_etat(), headers=_entetes()).status_code == 204
    reponse = client.post(
        f"{API}/caisse/etat", json=_etat(ecran="x" * 50, batterie_pct=40), headers=_entetes()
    )
    assert reponse.status_code == 204

    etat = lecteur.get(f"{API}/caisse/etat").json()["etat"]
    assert etat["batterie_pct"] == 40  # le dernier releve remplace le precedent
    assert etat["ecran"] == "x" * 32  # tronque, pas refuse
    assert etat["version_name"] == "0.7.0"
    assert etat["ventes_en_attente"] == 2
    assert 0 <= etat["secondes_depuis"] < 60
    assert etat["recu_at"].endswith(("Z", "+00:00"))
    db_session.expire_all()
    assert db_session.query(CaisseEtat).count() == 1


def test_les_etats_fins_sumup_et_lecteur_sont_relus(
    client: TestClient, client_authenticated_as, admin_stock_user
) -> None:
    lecteur = client_authenticated_as(admin_stock_user)
    reponse = client.post(
        f"{API}/caisse/etat",
        json=_etat(sumup_etat="enregistre", lecteur_etat=" EN_VEILLE "),
        headers=_entetes(),
    )
    assert reponse.status_code == 204

    etat = lecteur.get(f"{API}/caisse/etat").json()["etat"]
    assert etat["sumup_etat"] == "enregistre"
    assert etat["lecteur_etat"] == "en_veille"  # normalise


@pytest.mark.parametrize("inconnu", ["endormi", "", 3, True, ["connecte"]])
def test_un_etat_fin_inconnu_vaut_null_sans_rejeter_le_releve(
    client: TestClient, client_authenticated_as, admin_stock_user, inconnu
) -> None:
    reponse = client.post(
        f"{API}/caisse/etat",
        json=_etat(sumup_etat=inconnu, lecteur_etat=inconnu, batterie_pct=33),
        headers=_entetes(),
    )
    assert reponse.status_code == 204

    etat = client_authenticated_as(admin_stock_user).get(f"{API}/caisse/etat").json()["etat"]
    assert etat["batterie_pct"] == 33  # le releve est bien enregistre
    assert etat["sumup_etat"] is None
    assert etat["lecteur_etat"] is None


def test_une_ancienne_app_sans_etats_fins_remet_null(
    client: TestClient, client_authenticated_as, admin_stock_user
) -> None:
    client.post(
        f"{API}/caisse/etat",
        json=_etat(sumup_etat="connecte", lecteur_etat="connecte"),
        headers=_entetes(),
    )
    # Releve suivant d'une ancienne version : les champs sont absents.
    assert client.post(f"{API}/caisse/etat", json=_etat(), headers=_entetes()).status_code == 204

    etat = client_authenticated_as(admin_stock_user).get(f"{API}/caisse/etat").json()["etat"]
    assert etat["sumup_etat"] is None
    assert etat["lecteur_etat"] is None
    assert etat["sumup_connecte"] is True


def test_un_benevole_ne_lit_pas_l_etat(client_authenticated_as, benevole_user) -> None:
    assert client_authenticated_as(benevole_user).get(f"{API}/caisse/etat").status_code == 403


# ---------------------------------------------------------------------------
# Reappro atomique
# ---------------------------------------------------------------------------


def test_le_reappro_ajoute_au_stock(
    db_session: Session, client_authenticated_as, admin_stock_user
) -> None:
    produit = _produit(db_session, quantite=3, seuil=5)
    produit.alert_sent = True
    db_session.commit()

    reponse = client_authenticated_as(admin_stock_user).post(
        f"{API}/products/{produit.id}/reappro",
        json={"quantite": 10, "prix_achat_unitaire_cents": 80},
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["produit"]["quantity"] == 13
    assert reponse.json()["produit"]["alert_sent"] is False  # repasse au-dessus du seuil


@pytest.mark.parametrize("quantite", [0, -5, 10_001])
def test_un_reappro_hors_bornes_est_refuse(
    db_session: Session, client_authenticated_as, admin_benevoles_user, quantite
) -> None:
    produit = _produit(db_session, quantite=3)
    reponse = client_authenticated_as(admin_benevoles_user).post(
        f"{API}/products/{produit.id}/reappro",
        json={"quantite": quantite, "prix_achat_unitaire_cents": 80},
    )
    assert reponse.status_code == 422
    assert _quantite(db_session, produit.id) == 3


def test_reappro_d_un_produit_inconnu(client_authenticated_as, admin_benevoles_user) -> None:
    reponse = client_authenticated_as(admin_benevoles_user).post(
        f"{API}/products/999999/reappro",
        json={"quantite": 5, "prix_achat_unitaire_cents": 80},
    )
    assert reponse.status_code == 404


def test_la_compta_ne_reapprovisionne_pas(
    db_session: Session, client_authenticated_as, compta_user
) -> None:
    produit = _produit(db_session)
    reponse = client_authenticated_as(compta_user).post(
        f"{API}/products/{produit.id}/reappro",
        json={"quantite": 5, "prix_achat_unitaire_cents": 80},
    )
    assert reponse.status_code == 403


def test_la_tablette_reapprovisionne_avec_sa_cle(client: TestClient, db_session: Session) -> None:
    produit = _produit(db_session, nom="Canette", quantite=4)
    corps = {"product_id": produit.id, "delta": 20}

    assert client.post(f"{API}/caisse/reappro", json=corps).status_code == 401
    reponse = client.post(f"{API}/caisse/reappro", json=corps, headers=_entetes())
    assert reponse.status_code == 200, reponse.text
    assert reponse.json() == {"id": produit.id, "name": "Canette", "quantity": 24}

    assert client.post(
        f"{API}/caisse/reappro", json={"product_id": 999999, "delta": 5}, headers=_entetes()
    ).status_code == 404
    assert client.post(
        f"{API}/caisse/reappro", json={"product_id": produit.id, "delta": 0}, headers=_entetes()
    ).status_code == 422


def test_une_vente_n_efface_pas_un_reappro_concurrent(db_session: Session) -> None:
    """Le defaut que l'increment atomique corrige.

    La session de la vente a deja le produit en memoire (stock lu : 10). Un
    reappro +5 est commite ailleurs entre-temps. L'ancien code ecrivait
    « 10 - 1 = 9 », effacant le reappro ; la base doit dire 14.
    """
    produit = _produit(db_session, quantite=10)
    assert produit.quantity == 10  # charge dans la session de la vente

    autre = Session(bind=db_session.get_bind())
    try:
        buvette_crud.reapprovisionner(autre, produit.id, 5)
    finally:
        autre.close()

    buvette_crud.record_caisse_sale(
        db_session,
        CaisseVenteIn(
            transaction_id=str(uuid.uuid4()),
            sumup_tx_code=None,
            total_cents=150,
            lines=[{"product_id": produit.id, "name": produit.name, "quantity": 1, "unit_price_cents": 150}],
        ),
    )
    assert _quantite(db_session, produit.id) == 14


# ---------------------------------------------------------------------------
# Reglages et destinataires
# ---------------------------------------------------------------------------


def test_les_reglages_listent_destinataires_et_comptes_admin_stock(
    client_authenticated_as, admin_benevoles_user, admin_stock_user
) -> None:
    corps = client_authenticated_as(admin_benevoles_user).get(f"{API}/reglages").json()
    assert corps["recap_destinataires"] == buvette_crud.DESTINATAIRES_PAR_DEFAUT
    assert corps["comptes_admin_stock"] == [
        {"id": admin_stock_user.id, "email": admin_stock_user.email, "nom": admin_stock_user.full_name}
    ]


def test_modifier_les_destinataires(client_authenticated_as, super_admin_user) -> None:
    admin = client_authenticated_as(super_admin_user)
    reponse = admin.put(
        f"{API}/reglages",
        json={"recap_destinataires": [" a@exemple.fr ", "A@Exemple.fr", "b@exemple.fr", ""]},
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["recap_destinataires"] == ["a@exemple.fr", "b@exemple.fr"]
    assert admin.get(f"{API}/reglages").json()["recap_destinataires"] == ["a@exemple.fr", "b@exemple.fr"]

    refus = admin.put(f"{API}/reglages", json={"recap_destinataires": ["pas-une-adresse"]})
    assert refus.status_code == 422
    assert admin.get(f"{API}/reglages").json()["recap_destinataires"] == ["a@exemple.fr", "b@exemple.fr"]


def test_le_taux_des_frais_carte_se_regle_et_s_applique_partout(
    journee, client_authenticated_as, super_admin_user
) -> None:
    admin = client_authenticated_as(super_admin_user)
    assert admin.get(f"{API}/reglages").json()["taux_frais_carte_pb"] == 170  # defaut 1,70 %

    # Changer le taux seul ne touche pas aux destinataires.
    reponse = admin.put(f"{API}/reglages", json={"taux_frais_carte_pb": 250})
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["taux_frais_carte_pb"] == 250
    assert reponse.json()["recap_destinataires"] == buvette_crud.DESTINATAIRES_PAR_DEFAUT

    params = {"debut": JOUR.isoformat(), "fin": JOUR.isoformat()}
    totaux = admin.get(f"{API}/paiements", params=params).json()["totaux"]
    # 2,50 % de 4,50 € = 11,25 cts, arrondi a 11.
    assert (totaux["frais_carte_cents"], totaux["net_total_cents"]) == (11, 1239)
    assert totaux["taux_frais_carte_pb"] == 250
    stats = admin.get(f"{API}/stats", params=params).json()
    assert stats["totaux"]["frais_carte_cents"] == 11 and stats["totaux"]["net_cents"] == 1239

    for invalide in (-1, 1001):
        assert admin.put(f"{API}/reglages", json={"taux_frais_carte_pb": invalide}).status_code == 422
    assert admin.get(f"{API}/reglages").json()["taux_frais_carte_pb"] == 250


def test_les_frais_se_calculent_par_transaction_et_non_par_article(journee, client_authenticated_as, compta_user) -> None:
    """Panier carte : 2,00 € + 2,50 €. Par article : 3 + 4 = 7 cts ; par transaction
    (ce que preleve SumUp) : 1,70 % de 4,50 € = 7,65, soit 8 cts."""
    corps = client_authenticated_as(compta_user).get(
        f"{API}/paiements", params={"debut": JOUR.isoformat(), "fin": JOUR.isoformat(), "moyen": "carte"}
    ).json()
    (carte,) = corps["paiements"]
    assert [a["montant_cents"] for a in carte["articles"]] == [200, 250]
    assert carte["frais_cents"] == 8 == buvette_crud.frais_carte_cents(450, 170)


@pytest.mark.parametrize("role_fixture", ["admin_stock_user", "compta_user"])
def test_les_reglages_restent_aux_administrateurs(
    request: pytest.FixtureRequest, client_authenticated_as, role_fixture
) -> None:
    utilisateur = request.getfixturevalue(role_fixture)
    client = client_authenticated_as(utilisateur)
    assert client.get(f"{API}/reglages").status_code == 403
    assert client.put(f"{API}/reglages", json={"recap_destinataires": []}).status_code == 403


def test_destinataires_admin_stock_actifs_plus_liste_sans_doublon(
    db_session: Session, admin_stock_user, admin_benevoles_user
) -> None:
    from app.crud import user as user_crud

    user_crud.create_user(
        db_session,
        username=f"asp{uuid.uuid4().hex[:8]}",
        password="Strong#Pass1",
        role="AdminStock",
        email="en-attente@exemple.fr",
        validation_status="pending",
    )
    buvette_crud.enregistrer_destinataires(
        db_session, ["chef@exemple.fr", admin_stock_user.email.upper()]
    )

    assert buvette_crud.destinataires_buvette(db_session) == [
        admin_stock_user.email,
        "chef@exemple.fr",
    ]


# ---------------------------------------------------------------------------
# Alertes : un seul courriel par vente
# ---------------------------------------------------------------------------


def test_une_vente_qui_fait_passer_deux_produits_sous_le_seuil_n_envoie_qu_un_courriel(
    client: TestClient, db_session: Session, admin_stock_user, admin_benevoles_user, captured_emails
) -> None:
    a = _produit(db_session, nom="Madeleine", quantite=6, seuil=5)
    b = _produit(db_session, nom="Brownie", quantite=5, seuil=5)

    _vente_caisse(client, [(a, 2), (b, 1)])

    alertes = [m for m in captured_emails if "Alerte stock buvette" in m.subject]
    assert len(alertes) == 1
    assert "Madeleine" in alertes[0].body and "Brownie" in alertes[0].body
    assert "2 produits" in alertes[0].subject
    assert admin_stock_user.email in alertes[0].recipients
    assert "benfdila.omir@gmail.com" in alertes[0].recipients
    assert admin_benevoles_user.email not in alertes[0].recipients
    assert "—" not in alertes[0].body


def test_une_commande_helloasso_de_deux_articles_n_envoie_qu_un_courriel(
    client: TestClient, db_session: Session, captured_emails, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "helloasso_webhook_secret", "")
    for tier, nom in ((5001, "Eau"), (5002, "Soda")):
        db_session.add(
            BuvetteProduct(helloasso_tier_id=tier, name=nom, price_cents=100, quantity=3, seuil_alerte=3)
        )
    db_session.commit()
    commande = {
        "id": 4321,
        "date": "2026-10-05T10:00:00+02:00",
        "formSlug": settings.helloasso_buvette_form_slug,
        "items": [
            {"id": i, "tierId": tier, "paymentId": 99, "quantity": 1, "amount": 100, "name": nom}
            for i, (tier, nom) in enumerate(((5001, "Eau"), (5002, "Soda")), start=1)
        ],
    }
    reponse = client.post(f"{API}/webhook/helloasso", json={"eventType": "Order", "data": commande})
    assert reponse.status_code == 200

    alertes = [m for m in captured_emails if "Alerte stock buvette" in m.subject]
    assert len(alertes) == 1
    assert "Eau" in alertes[0].body and "Soda" in alertes[0].body


# ---------------------------------------------------------------------------
# Role AdminStock : la buvette, et rien d'autre
# ---------------------------------------------------------------------------


def test_admin_stock_voit_et_gere_la_buvette(
    db_session: Session, client_authenticated_as, admin_stock_user
) -> None:
    client = client_authenticated_as(admin_stock_user)
    assert client.get(f"{API}/products").status_code == 200
    assert client.get(f"{API}/sales").status_code == 200
    reponse = client.post(f"{API}/products", json={"name": "Dattes", "price_cents": 200})
    assert reponse.status_code == 201, reponse.text
    assert client.patch(f"{API}/products/{reponse.json()['id']}", json={"seuil_alerte": 9}).status_code == 200


def test_admin_stock_n_a_aucun_autre_droit(client_authenticated_as, admin_stock_user) -> None:
    client = client_authenticated_as(admin_stock_user)
    assert client.get("/api/v1/stock/items").status_code == 403
    assert client.get("/api/v1/invoices").status_code == 403
    assert client.get("/api/v1/users").status_code == 403
    assert client.get(f"{API}/webhook/status").status_code == 403


def test_un_super_admin_peut_attribuer_le_role_admin_stock(
    client: TestClient, super_admin_user, benevole_user, auth_headers
) -> None:
    reponse = client.patch(
        f"/api/v1/users/{benevole_user.id}/role",
        json={"role": "AdminStock"},
        headers=auth_headers(super_admin_user),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["role"] == "AdminStock"
