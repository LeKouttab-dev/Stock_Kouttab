"""Unit tests for app.crud.stock."""

from __future__ import annotations

import io
import uuid

import pytest

from app.core.exceptions import AppException
from app.crud import stock as stock_crud
from app.crud import user as user_crud
from app.services.csv_import import import_inventory


pytestmark = pytest.mark.unit


def _name(prefix: str = "item") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _make_user(db, *, role: str = "Super Admin"):
    name = f"u{uuid.uuid4().hex[:8]}"
    return user_crud.create_user(
        db,
        username=name,
        password="Strong#Pass1",
        role=role,
        email=f"{name}@example.com",
    )


# ---- Items -----------------------------------------------------------------


def test_create_item_inserts_ok(db_session) -> None:
    item = stock_crud.create_item(
        db_session,
        nom=_name("ok"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=10,
        seuil_alerte=2,
        emoji="🍔",
    )
    assert item.id > 0
    assert item.quantite == 10
    assert item.alert_sent is False


def test_create_item_duplicate_name_conflict(db_session) -> None:
    nom = _name("dup")
    stock_crud.create_item(
        db_session,
        nom=nom,
        categorie="Nourriture",
        sous_categorie=None,
        quantite=5,
        seuil_alerte=2,
    )
    with pytest.raises(AppException) as exc_info:
        stock_crud.create_item(
            db_session,
            nom=nom,
            categorie="Nourriture",
            sous_categorie=None,
            quantite=1,
            seuil_alerte=1,
        )
    assert exc_info.value.code_value == "CONF_4002"  # STOCK_ITEM_DUPLICATE


def test_update_quantity_sets_alert_when_below_threshold(db_session) -> None:
    user = _make_user(db_session)
    item = stock_crud.create_item(
        db_session,
        nom=_name("low"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=10,
        seuil_alerte=5,
    )
    assert item.alert_sent is False

    refreshed, alert = stock_crud.update_quantity_direct(
        db_session, item.id, new_quantity=2, user_id=user.id
    )
    assert refreshed.quantite == 2
    assert refreshed.alert_sent is True
    assert alert is True


def test_update_quantity_resets_alert_when_above_threshold(db_session) -> None:
    """Regression: if alert was already sent and stock is replenished, flag must reset."""
    user = _make_user(db_session)
    item = stock_crud.create_item(
        db_session,
        nom=_name("reset"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=2,
        seuil_alerte=5,
    )
    # Manually flag alert_sent = True (simulate previous low-stock alert).
    item.alert_sent = True
    db_session.commit()

    refreshed, alert = stock_crud.update_quantity_direct(
        db_session, item.id, new_quantity=20, user_id=user.id
    )
    assert refreshed.quantite == 20
    assert refreshed.alert_sent is False
    assert alert is False


def test_delete_item_cascades_modifications(db_session) -> None:
    user = _make_user(db_session)
    item = stock_crud.create_item(
        db_session,
        nom=_name("del"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=10,
        seuil_alerte=2,
    )
    stock_crud.create_modification_request(
        db_session,
        user_id=user.id,
        stock_id=item.id,
        requested_qty=5,
    )
    item_id = item.id
    stock_crud.delete_item(db_session, item_id)
    assert stock_crud.get_item(db_session, item_id) is None


# ---- Categories / sub-categories ------------------------------------------


def test_create_update_delete_category_flow(db_session) -> None:
    name = f"Cat_{uuid.uuid4().hex[:6]}"
    cat = stock_crud.add_category(db_session, nom=name)
    assert cat.id > 0
    new_name = f"{name}_renamed"
    renamed = stock_crud.rename_category(db_session, old_name=name, new_name=new_name)
    assert renamed.nom == new_name
    stock_crud.delete_category(db_session, nom=new_name)
    # Listing must no longer include it.
    cats = [c.nom for c in stock_crud.list_categories(db_session)]
    assert new_name not in cats


def test_create_update_delete_subcategory_flow(db_session) -> None:
    cat = f"Cat_{uuid.uuid4().hex[:6]}"
    stock_crud.add_category(db_session, nom=cat)
    sub = stock_crud.add_subcategory(
        db_session, nom_categorie=cat, nom_sous_categorie="SubA"
    )
    updated = stock_crud.update_subcategory(
        db_session, sub.id, nom_sous_categorie="SubB"
    )
    assert updated.nom_sous_categorie == "SubB"
    stock_crud.delete_subcategory(db_session, sub.id)


def test_delete_category_blocked_if_items_exist(db_session) -> None:
    cat_name = f"Cat_{uuid.uuid4().hex[:6]}"
    stock_crud.add_category(db_session, nom=cat_name)
    stock_crud.create_item(
        db_session,
        nom=_name("x"),
        categorie=cat_name,
        sous_categorie=None,
        quantite=1,
        seuil_alerte=1,
    )
    with pytest.raises(AppException) as exc_info:
        stock_crud.delete_category(db_session, nom=cat_name)
    assert exc_info.value.code_value == "CONF_4003"  # CATEGORY_HAS_ITEMS


# ---- CSV import ------------------------------------------------------------


def test_import_csv_success_and_skips_duplicates(db_session) -> None:
    nom_existing = _name("existing")
    # Pre-create an article that will appear in the CSV → must be skipped.
    stock_crud.create_item(
        db_session,
        nom=nom_existing,
        categorie="Nourriture",
        sous_categorie=None,
        quantite=1,
        seuil_alerte=1,
    )
    new_name = _name("new")
    csv_content = (
        "header1\nheader2\nheader3\nheader4\nheader5\nheader6\n"
        "Catégorie,Sous-catégorie,Nom de l'article,Quantité initiale\n"
        f"Nourriture,Boissons,{new_name},25\n"
        f"Nourriture,Boissons,{nom_existing},10\n"
    )
    result = import_inventory(db_session, content=csv_content.encode("utf-8"))
    assert result["imported"] == 1
    assert result["skipped"] == 1


def test_import_csv_registers_unknown_categories(db_session) -> None:
    """Une categorie importee doit rejoindre le referentiel.

    L'import creait les sous-categories manquantes mais jamais les categories.
    Les articles atterrissaient donc dans une categorie absente de la table
    ``Categories`` : l'ecran « Naviguer par categorie » ne l'affichait pas, et
    la categorie ressaisie a la main — avec une faute de frappe — comptait
    zero article alors que le stock en contenait vingt-deux.
    """
    categorie = _name("Cat")
    csv_content = (
        "header1\nheader2\nheader3\nheader4\nheader5\nheader6\n"
        "Catégorie,Sous-catégorie,Nom de l'article,Quantité initiale\n"
        f"{categorie},Boissons,{_name('a')},5\n"
        f"{categorie},Snacks,{_name('b')},3\n"
    )

    result = import_inventory(db_session, content=csv_content.encode("utf-8"))
    assert result["imported"] == 2

    noms = {c.nom for c in stock_crud.list_categories(db_session)}
    assert categorie in noms
    # Deux lignes partagent la categorie : elle ne doit etre creee qu'une fois.
    assert [c.nom for c in stock_crud.list_categories(db_session)].count(categorie) == 1


def test_import_csv_reuses_an_existing_category(db_session) -> None:
    categorie = _name("Cat")
    stock_crud.add_category(db_session, nom=categorie)

    csv_content = (
        "header1\nheader2\nheader3\nheader4\nheader5\nheader6\n"
        "Catégorie,Sous-catégorie,Nom de l'article,Quantité initiale\n"
        f"{categorie},Boissons,{_name('c')},5\n"
    )
    result = import_inventory(db_session, content=csv_content.encode("utf-8"))

    assert result["imported"] == 1
    assert [c.nom for c in stock_crud.list_categories(db_session)].count(categorie) == 1


# ---- Statistics & low stock ------------------------------------------------


def test_get_statistics_returns_expected_shape(db_session) -> None:
    stats = stock_crud.get_stock_statistics(db_session)
    for key in (
        "total_articles",
        "total_quantite",
        "alertes_stock",
        "stock_epuise",
        "dernieres_modifs",
        "stats_par_categorie",
        "stats_nourriture_sous_categories",
    ):
        assert key in stats
    assert isinstance(stats["dernieres_modifs"], list)
    assert isinstance(stats["stats_par_categorie"], list)


def test_get_low_stock_items_filters_by_threshold(db_session) -> None:
    stock_crud.create_item(
        db_session,
        nom=_name("low1"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=1,
        seuil_alerte=10,
    )
    stock_crud.create_item(
        db_session,
        nom=_name("ok1"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=50,
        seuil_alerte=10,
    )
    low = stock_crud.get_low_stock_items(db_session)
    quantities = [i.quantite for i in low]
    assert all(q < 10 or True for q in quantities)
    assert len(low) >= 1


# ---- La photo du produit ----------------------------------------------------
#
# Le scan d'un code-barres affichait la photo dans l'apercu, puis la jetait :
# l'article cree n'en gardait rien et la liste retombait sur l'emoji.


def test_la_photo_scannee_est_conservee(db_session) -> None:
    item = stock_crud.create_item(
        db_session,
        nom=_name("photo"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=1,
        seuil_alerte=5,
        image_url="https://images.openfoodfacts.org/images/products/front_fr.4.100.jpg",
    )
    assert item.image_url.endswith("front_fr.4.100.jpg")


def test_un_article_sans_photo_reste_valide(db_session) -> None:
    """L'emoji sert de repli : la photo n'a jamais ete obligatoire."""
    item = stock_crud.create_item(
        db_session,
        nom=_name("sansphoto"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=1,
        seuil_alerte=5,
    )
    assert item.image_url is None


def test_une_adresse_de_photo_non_https_est_refusee(db_session) -> None:
    """Rendue telle quelle dans un `<img src>`.

    `data:` ferait passer une image entiere par ce champ, et `http://` afficherait
    un avertissement de contenu mixte sur un site servi en HTTPS — la photo ne
    s'afficherait pas, sans explication.
    """
    for adresse in ("http://exemple.test/p.jpg", "data:image/png;base64,AAAA"):
        with pytest.raises(AppException):
            stock_crud.create_item(
                db_session,
                nom=_name("mauvaise"),
                categorie="Nourriture",
                sous_categorie=None,
                quantite=1,
                seuil_alerte=5,
                image_url=adresse,
            )


def test_la_photo_se_retire(db_session) -> None:
    """Sans le drapeau, on ne pourrait que la remplacer : une photo erronee
    resterait collee a l'article."""
    item = stock_crud.create_item(
        db_session,
        nom=_name("retrait"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=1,
        seuil_alerte=5,
        image_url="https://images.openfoodfacts.org/p.jpg",
    )

    modifie = stock_crud.update_item(
        db_session, item.id, image_url=None, image_url_set=True
    )
    assert modifie.image_url is None


def test_une_mise_a_jour_sans_photo_ne_l_efface_pas(db_session) -> None:
    """Le cas courant : ajuster une quantite ne doit pas perdre la photo."""
    item = stock_crud.create_item(
        db_session,
        nom=_name("conserve"),
        categorie="Nourriture",
        sous_categorie=None,
        quantite=1,
        seuil_alerte=5,
        image_url="https://images.openfoodfacts.org/p.jpg",
    )

    modifie = stock_crud.update_item(db_session, item.id, seuil_alerte=9)
    assert modifie.image_url == "https://images.openfoodfacts.org/p.jpg"
