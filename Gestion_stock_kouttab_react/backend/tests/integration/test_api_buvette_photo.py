"""La photo d'un produit de la buvette, et ce qu'elle protege.

Trois proprietes sont verrouillees ici :

 1. **La photo est servie sans authentification, sous un jeton NEUF a chaque
    depot.** La tablette charge les images avec son propre chargeur, qui ne porte
    ni session ni cle de caisse : exiger un en-tete n'afficherait aucune photo en
    caisse. Et comme elle ignore les en-tetes de cache, reutiliser la meme
    adresse y laisserait l'ancienne image, parfois des jours.
 2. **La photo est reduite avant d'entrer en base.** Une photo de telephone fait
    plusieurs mega-octets ; la tablette les precharge toutes d'un coup, et la
    base est sauvegardee chaque nuit.
 3. **La synchronisation HelloAsso n'ecrase plus ce qui a ete modifie a la
    main.** Sans ce garde-fou, rendre les produits modifiables aurait fait
    disparaitre le travail de la personne au premier « Synchroniser ».
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.crud import buvette as buvette_crud
from app.db.models import BuvetteProduct
from app.services import images


pytestmark = pytest.mark.integration


def _photo(largeur: int = 2000, hauteur: int = 1500, couleur=(200, 30, 30)) -> bytes:
    """Une vraie image JPEG, de la taille d'une photo de telephone."""
    tampon = io.BytesIO()
    Image.new("RGB", (largeur, hauteur), couleur).save(tampon, format="JPEG")
    return tampon.getvalue()


@pytest.fixture()
def caisse_key(monkeypatch) -> str:
    """La cle de la tablette. Vide, les routes /caisse repondent 404."""
    cle = "cle-de-caisse-de-test-suffisamment-longue-1234"
    monkeypatch.setattr(settings, "caisse_api_key", cle)
    return cle


@pytest.fixture()
def produit(db_session) -> BuvetteProduct:
    p = BuvetteProduct(
        name="Canette de soda",
        price_cents=150,
        quantity=12,
        seuil_alerte=5,
        emoji="🥤",
        caisse_category="boissons",
        is_active=True,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def test_le_depot_reduit_la_photo_et_la_sert_sans_authentification(
    client: TestClient, admin_benevoles_user, auth_headers, produit
):
    reponse = client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("photo.jpg", _photo(), "image/jpeg")},
        headers=auth_headers(admin_benevoles_user),
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["a_une_photo"] is True
    # L'ecran doit pouvoir dire pourquoi la synchro ne touchera plus ce produit.
    assert corps["edite_manuellement"] is True

    adresse = corps["image_url"]
    assert "/buvette/photos/" in adresse

    chemin = adresse.split("/api", 1)[1].replace("/v1", "/api/v1", 1)
    # Aucun en-tete : c'est exactement ce que fait le chargeur d'images de la
    # tablette.
    image = client.get(chemin)
    assert image.status_code == 200, image.text
    assert image.headers["content-type"] == "image/jpeg"
    assert "immutable" in image.headers["cache-control"]

    with Image.open(io.BytesIO(image.content)) as rendue:
        assert max(rendue.size) <= images.LARGEUR_MAX
    assert len(image.content) < 200_000


def test_un_nouveau_depot_change_l_adresse(
    client: TestClient, admin_benevoles_user, auth_headers, produit
):
    """La tablette met les photos en cache par URL, en ignorant les en-tetes."""
    entetes = auth_headers(admin_benevoles_user)
    premiere = client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("a.jpg", _photo(couleur=(10, 10, 200)), "image/jpeg")},
        headers=entetes,
    ).json()["image_url"]
    seconde = client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("b.jpg", _photo(couleur=(10, 200, 10)), "image/jpeg")},
        headers=entetes,
    ).json()["image_url"]

    assert premiere != seconde


def test_retirer_la_photo_rend_l_emoji(
    client: TestClient, admin_benevoles_user, auth_headers, produit
):
    entetes = auth_headers(admin_benevoles_user)
    client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("a.jpg", _photo(), "image/jpeg")},
        headers=entetes,
    )
    reponse = client.delete(
        f"/api/v1/buvette/products/{produit.id}/photo", headers=entetes
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["a_une_photo"] is False
    assert corps["image_url"] is None
    assert corps["emoji"] == "🥤"


def test_un_jeton_inconnu_ne_dit_rien(client: TestClient):
    assert client.get("/api/v1/buvette/photos/jeton-qui-n-existe-pas").status_code == 404


def test_un_fichier_qui_n_est_pas_une_image_est_refuse(
    client: TestClient, admin_benevoles_user, auth_headers, produit
):
    reponse = client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("virus.exe", b"MZ\x90\x00 pas une image", "application/octet-stream")},
        headers=auth_headers(admin_benevoles_user),
    )
    assert reponse.status_code in (400, 415, 422)


def test_le_catalogue_de_la_tablette_sert_la_photo_deposee(
    client: TestClient, admin_benevoles_user, auth_headers, produit, caisse_key
):
    client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("a.jpg", _photo(), "image/jpeg")},
        headers=auth_headers(admin_benevoles_user),
    )
    catalogue = client.get(
        "/api/v1/buvette/caisse/catalogue", headers={"X-Caisse-Key": caisse_key}
    )
    assert catalogue.status_code == 200, catalogue.text
    ligne = next(p for p in catalogue.json()["products"] if p["id"] == produit.id)
    assert "/buvette/photos/" in ligne["image_url"]


def test_un_benevole_ne_depose_pas_de_photo(
    client: TestClient, benevole_user, auth_headers, produit
):
    reponse = client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("a.jpg", _photo(), "image/jpeg")},
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 403


class TestSynchroHelloAsso:
    """La synchronisation respecte ce qui a ete repris en main."""

    TIER = {"id": 999, "label": "Jus HelloAsso", "description": "Depuis la boutique", "amount": 250}

    def test_elle_alimente_un_produit_non_touche(self, db_session):
        buvette_crud.sync_from_helloasso(db_session, [self.TIER])
        produit = buvette_crud.get_product_by_tier_id(db_session, 999)
        assert produit is not None

        buvette_crud.sync_from_helloasso(
            db_session, [{**self.TIER, "label": "Jus renomme chez HelloAsso"}]
        )
        db_session.refresh(produit)
        assert produit.name == "Jus renomme chez HelloAsso"

    def test_elle_respecte_un_nom_et_un_prix_repris_en_main(self, db_session):
        from app.schemas.buvette import BuvetteProductUpdate

        buvette_crud.sync_from_helloasso(db_session, [self.TIER])
        produit = buvette_crud.get_product_by_tier_id(db_session, 999)
        buvette_crud.update_product(
            db_session,
            produit.id,
            BuvetteProductUpdate(name="Jus de pomme bio", price_cents=300),
        )

        buvette_crud.sync_from_helloasso(
            db_session, [{**self.TIER, "label": "Jus HelloAsso", "amount": 250}]
        )
        db_session.refresh(produit)

        assert produit.name == "Jus de pomme bio"
        assert produit.price_cents == 300

    def test_elle_respecte_une_photo_deposee(self, db_session):
        buvette_crud.sync_from_helloasso(
            db_session, [{**self.TIER, "imageUrl": "https://helloasso.test/jus.jpg"}]
        )
        produit = buvette_crud.get_product_by_tier_id(db_session, 999)
        buvette_crud.enregistrer_photo(db_session, produit.id, _photo())
        jeton = produit.photo_jeton

        buvette_crud.sync_from_helloasso(
            db_session, [{**self.TIER, "imageUrl": "https://helloasso.test/autre.jpg"}]
        )
        db_session.refresh(produit)

        assert produit.photo_jeton == jeton
        assert produit.image_url != "https://helloasso.test/autre.jpg"

    def test_le_stock_continue_de_se_mettre_a_jour(self, db_session):
        """Le garde-fou porte sur le nom, le prix et la photo — pas sur le stock."""
        from app.schemas.buvette import BuvetteProductUpdate

        buvette_crud.sync_from_helloasso(db_session, [self.TIER])
        produit = buvette_crud.get_product_by_tier_id(db_session, 999)
        buvette_crud.update_product(
            db_session, produit.id, BuvetteProductUpdate(name="Repris en main")
        )

        buvette_crud.sync_from_helloasso(db_session, [self.TIER])
        db_session.refresh(produit)
        assert produit.last_synced_at is not None


# ---- Reprendre la photo d'un autre produit --------------------------------


def _autre(db_session, **champs) -> BuvetteProduct:
    p = BuvetteProduct(
        name=champs.pop("name", "2x Expresso"),
        price_cents=200,
        quantity=0,
        caisse_category="cafe",
        is_active=True,
        **champs,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def test_reprendre_une_photo_deposee_la_copie_sous_un_jeton_neuf(
    client: TestClient, admin_benevoles_user, auth_headers, produit, db_session
):
    entetes = auth_headers(admin_benevoles_user)
    source = client.post(
        f"/api/v1/buvette/products/{produit.id}/photo",
        files={"file": ("a.jpg", _photo(), "image/jpeg")},
        headers=entetes,
    ).json()["image_url"]
    cible = _autre(db_session)

    reponse = client.post(
        f"/api/v1/buvette/products/{cible.id}/photo/reprendre",
        json={"source_id": produit.id},
        headers=entetes,
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["a_une_photo"] is True
    assert corps["edite_manuellement"] is True
    # Meme image, autre adresse : retirer l'une ne doit pas casser l'autre.
    assert corps["image_url"] != source
    chemin = corps["image_url"].split("/api", 1)[1].replace("/v1", "/api/v1", 1)
    assert client.get(chemin).status_code == 200


def test_reprendre_une_photo_helloasso_reprend_son_adresse(
    client: TestClient, admin_benevoles_user, auth_headers, db_session
):
    source = _autre(db_session, name="Expresso", image_url="https://cdn.helloasso.com/expresso.jpg")
    cible = _autre(db_session)
    reponse = client.post(
        f"/api/v1/buvette/products/{cible.id}/photo/reprendre",
        json={"source_id": source.id},
        headers=auth_headers(admin_benevoles_user),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["image_url"] == "https://cdn.helloasso.com/expresso.jpg"
    assert reponse.json()["a_une_photo"] is False


def test_reprendre_refuse_un_produit_sans_photo_ou_soi_meme(
    client: TestClient, admin_benevoles_user, auth_headers, produit, db_session
):
    entetes = auth_headers(admin_benevoles_user)
    cible = _autre(db_session)
    sans = client.post(
        f"/api/v1/buvette/products/{cible.id}/photo/reprendre",
        json={"source_id": produit.id},
        headers=entetes,
    )
    assert sans.status_code == 422
    soi = client.post(
        f"/api/v1/buvette/products/{cible.id}/photo/reprendre",
        json={"source_id": cible.id},
        headers=entetes,
    )
    assert soi.status_code == 422


def test_un_benevole_ne_reprend_pas_de_photo(
    client: TestClient, benevole_user, auth_headers, produit, db_session
):
    cible = _autre(db_session)
    reponse = client.post(
        f"/api/v1/buvette/products/{cible.id}/photo/reprendre",
        json={"source_id": produit.id},
        headers=auth_headers(benevole_user),
    )
    assert reponse.status_code == 403


# ---- La synchro rattache au lieu de creer un doublon ----------------------


def _tier(tier_id: int, label: str) -> dict:
    return {"id": tier_id, "label": label, "price": 150}


def test_synchro_rattache_un_produit_cree_a_la_main(db_session):
    """13/10/2026 : « NUTELLA - B READY » cree a la main, puis ajoute a la boutique."""
    manuel = _autre(db_session, name="NUTELLA - B READY")
    manuel.quantity = 58
    db_session.commit()

    resultat = buvette_crud.sync_from_helloasso(db_session, [_tier(24184738, "Nutella - B Ready")])

    assert resultat.created == 0
    db_session.refresh(manuel)
    assert manuel.helloasso_tier_id == 24184738
    assert manuel.quantity == 58


def test_synchro_rattache_un_produit_dont_le_tier_a_disparu(db_session):
    """Article recree dans la boutique HelloAsso : nouveau tier, meme produit."""
    vico = _autre(db_session, name="VICO - CHIPS", helloasso_tier_id=23053043)

    resultat = buvette_crud.sync_from_helloasso(db_session, [_tier(23118849, "VICO - CHIPS")])

    assert resultat.created == 0
    db_session.refresh(vico)
    assert vico.helloasso_tier_id == 23118849


def test_synchro_ne_devine_pas_entre_deux_candidats(db_session):
    _autre(db_session, name="Miel")
    _autre(db_session, name="MIEL")
    resultat = buvette_crud.sync_from_helloasso(db_session, [_tier(999001, "Miel")])
    assert resultat.created == 1


def test_synchro_ne_prend_pas_le_produit_d_un_tier_encore_en_boutique(db_session):
    _autre(db_session, name="Orangina", helloasso_tier_id=999010)
    resultat = buvette_crud.sync_from_helloasso(
        db_session, [_tier(999010, "Orangina"), _tier(999011, "Orangina")]
    )
    assert resultat.created == 1


def test_synchro_cree_un_produit_de_nom_inconnu(db_session):
    _autre(db_session, name="Expresso")
    resultat = buvette_crud.sync_from_helloasso(db_session, [_tier(999020, "Capri-Sun")])
    assert resultat.created == 1
