"""Ce que chaque pole exige au depot d'une piece comptable.

La regle, en une phrase : **toute** piece porte une categorie — la nature de la
depense —, et les poles evenementiels y ajoutent un evenement et sa date. Elle
vaut a l'identique pour les factures et les notes de frais, d'ou sa resolution
commune.

La categorie etait auparavant refusee sous un pole evenementiel. Mais
l'evenement dit a quelle occasion la depense a eu lieu, pas ce qui a ete
achete : le comptable n'avait la nature de la depense que sur la moitie des
pieces.

L'autre cas, celui qui a motive le referentiel : une depense du local — des courses, du gouter —
n'a aucun evenement. En exiger un obligeait le deposant a en inventer, et le
comptable recevait des pieces rattachees a des evenements qui n'existaient pas.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.crud import expense_category as category_crud
from app.crud import rattachement as rattachement_crud
from app.db.models import Pole


pytestmark = pytest.mark.unit


DATE = __import__("datetime").date(2026, 8, 12)


# ---- Pole evenementiel ------------------------------------------------------


def test_evenementiel_porte_les_deux_rattachements(
    db_session: Session, first_pole: Pole, first_category
):
    """L'evenement dit a quelle occasion, la categorie dit ce qui a ete achete."""
    resolu = rattachement_crud.resoudre(
        db_session,
        id_pole=first_pole.id,
        evenement_libre="Gala de fin d'année",
        id_categorie=first_category.id,
        date_evenement=DATE,
    )
    assert resolu.evenement == "Gala de fin d'année"
    assert resolu.categorie == first_category.nom
    assert resolu.date_evenement == DATE


def test_l_evenement_nomme_le_fichier_avant_la_categorie(
    db_session: Session, first_pole: Pole, first_category
):
    """Les deux coexistent, mais un seul nomme la piece envoyee au comptable.

    Si la categorie l'emportait, les pieces d'un meme evenement cesseraient de
    se ranger ensemble dans sa boite — c'est exactement ce que le nommage sert
    a produire.
    """
    resolu = rattachement_crud.resoudre(
        db_session,
        id_pole=first_pole.id,
        evenement_libre="Gala de fin d'année",
        id_categorie=first_category.id,
        date_evenement=DATE,
    )
    assert resolu.libelle_document == "Gala de fin d'année"


def test_evenementiel_exige_aussi_une_categorie(db_session: Session, first_pole: Pole):
    """Le cas signale : la nature de la depense sautait des qu'un evenement
    entrait en jeu."""
    with pytest.raises(AppException) as exc:
        rattachement_crud.resoudre(
            db_session,
            id_pole=first_pole.id,
            evenement_libre="Gala",
            date_evenement=DATE,
        )
    assert "categorie" in str(exc.value.message).lower()


def test_evenementiel_exige_un_evenement(
    db_session: Session, first_pole: Pole, first_category
):
    with pytest.raises(AppException):
        rattachement_crud.resoudre(
            db_session,
            id_pole=first_pole.id,
            id_categorie=first_category.id,
            date_evenement=DATE,
        )


def test_evenementiel_exige_la_date(
    db_session: Session, first_pole: Pole, first_category
):
    with pytest.raises(AppException) as exc:
        rattachement_crud.resoudre(
            db_session,
            id_pole=first_pole.id,
            evenement_libre="Gala",
            id_categorie=first_category.id,
        )
    assert "date" in str(exc.value.message).lower()


# ---- Poles sans evenement ---------------------------------------------------


def test_local_accepte_une_categorie(db_session: Session, local_pole: Pole, first_category):
    resolu = rattachement_crud.resoudre(
        db_session, id_pole=local_pole.id, id_categorie=first_category.id
    )
    assert resolu.categorie == first_category.nom
    assert resolu.evenement is None
    assert resolu.id_event is None
    # Pas d'evenement, donc pas de date d'evenement : la date de la depense fait
    # foi et c'est elle qui datera le fichier envoye au comptable.
    assert resolu.date_evenement is None
    assert resolu.libelle_document == first_category.nom


def test_local_exige_une_categorie(db_session: Session, local_pole: Pole):
    with pytest.raises(AppException) as exc:
        rattachement_crud.resoudre(db_session, id_pole=local_pole.id)
    assert "categorie" in str(exc.value.message).lower()


def test_local_refuse_un_evenement(db_session: Session, local_pole: Pole, first_category):
    """Le formulaire ne le propose plus, mais l'API reste la frontiere : un
    ancien onglet ouvert ne doit pas pouvoir rattacher une depense du local a un
    evenement."""
    with pytest.raises(AppException) as exc:
        rattachement_crud.resoudre(
            db_session,
            id_pole=local_pole.id,
            evenement_libre="Gala",
            id_categorie=first_category.id,
        )
    assert "evenement" in str(exc.value.message).lower()


def test_categorie_desactivee_refusee(db_session: Session, local_pole: Pole, first_category):
    """Desactiver une categorie la retire du formulaire ; l'API doit suivre."""
    category_crud.update_category(db_session, first_category.id, is_active=False)
    with pytest.raises(AppException) as exc:
        rattachement_crud.resoudre(
            db_session, id_pole=local_pole.id, id_categorie=first_category.id
        )
    assert "plus proposee" in str(exc.value.message).lower()


def test_categorie_inconnue_refusee(db_session: Session, local_pole: Pole):
    with pytest.raises(AppException):
        rattachement_crud.resoudre(
            db_session, id_pole=local_pole.id, id_categorie=999_999
        )


def test_pole_inconnu_refuse(db_session: Session, first_category):
    with pytest.raises(AppException):
        rattachement_crud.resoudre(
            db_session, id_pole=999_999, id_categorie=first_category.id
        )


# ---- Referentiel ------------------------------------------------------------


def test_le_referentiel_des_categories_est_celui_arrete_avec_le_client(
    db_session: Session,
):
    noms = [c.nom for c in category_crud.list_categories(db_session)]
    assert noms == [
        "Courses",
        "Stock goûter",
        "Achat buvette",
        "Achat matériel",
        "Mobilier, immobilier et petit équipement",
        "Fournitures administratives",
        "Entretien",
        "Réceptions (repas, déplacements, nourriture)",
        "Autre",
    ]


def test_autre_reste_en_fin_de_liste(db_session: Session):
    """Un fourre-tout offert avant les categories precises se choisit par
    defaut. Son ordre est volontairement tres eleve, pour que les categories
    ajoutees ensuite passent devant sans qu'on ait a y penser."""
    noms = [c.nom for c in category_crud.list_categories(db_session)]
    assert noms[-1] == "Autre"


def test_une_categorie_du_referentiel_de_base_ne_se_supprime_pas(
    db_session: Session, first_category
):
    """Meme garde-fou que les poles : desactiver, pas supprimer."""
    with pytest.raises(AppException):
        category_crud.delete_category(db_session, first_category.id)


def test_une_categorie_utilisee_ne_se_supprime_pas(
    db_session: Session, local_pole: Pole, benevole_user
):
    from decimal import Decimal

    from app.crud import expense as expense_crud

    categorie = category_crud.create_category(db_session, nom="Ponctuelle")
    expense_crud.create_expense(
        db_session,
        user_id=benevole_user.id,
        date_depense=DATE,
        rattachement=None,
        fournisseur="Metro",
        nature_charge=None,
        montant=Decimal("12.50"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
        id_pole=local_pole.id,
        pole=local_pole.nom,
        id_categorie=categorie.id,
        categorie=categorie.nom,
    )

    with pytest.raises(AppException) as exc:
        category_crud.delete_category(db_session, categorie.id)
    assert "1 piece(s)" in str(exc.value.message)


def test_une_categorie_libre_se_supprime(db_session: Session):
    categorie = category_crud.create_category(db_session, nom="Provisoire")
    category_crud.delete_category(db_session, categorie.id)
    assert "Provisoire" not in [c.nom for c in category_crud.list_categories(db_session)]


# ---- Referentiel des poles --------------------------------------------------


def test_le_referentiel_des_poles_est_celui_arrete_avec_le_client(db_session: Session):
    from app.crud import pole as pole_crud

    poles = pole_crud.list_poles(db_session)
    assert [p.nom for p in poles] == [
        "EV(T)",
        "EV(G)",
        "EV(J)",
        "Frais généraux",
        "Institut",
        "Halaqa",
        "Séjour annuel",
        "ESP-VT",
    ]


def test_seuls_les_poles_ev_se_rattachent_a_un_evenement(db_session: Session):
    from app.crud import pole as pole_crud

    poles = {p.nom: p for p in pole_crud.list_poles(db_session)}
    assert [n for n, p in poles.items() if p.requiert_evenement] == [
        "EV(T)",
        "EV(G)",
        "EV(J)",
    ]


def test_chaque_pole_ev_porte_sa_famille(db_session: Session):
    """La famille filtre la liste d'evenements proposee sous le pole."""
    from app.crud import pole as pole_crud

    poles = {p.nom: p.type_evenement for p in pole_crud.list_poles(db_session)}
    assert poles["EV(T)"] == "T"
    assert poles["EV(G)"] == "G"
    assert poles["EV(J)"] == "J"
    # Un pole sans evenement n'a pas de famille : rien a filtrer.
    assert poles["Institut"] is None


def test_les_poles_retires_sont_desactives_et_non_supprimes(db_session: Session):
    """Les factures deja deposees les referencent : leur libelle doit rester
    lisible, meme si le formulaire ne les propose plus."""
    from app.crud import pole as pole_crud

    tous = {p.nom: p for p in pole_crud.list_poles(db_session, include_inactive=True)}
    for retire in ("Pôle événementiel", "Local"):
        if retire in tous:
            assert not tous[retire].is_active
