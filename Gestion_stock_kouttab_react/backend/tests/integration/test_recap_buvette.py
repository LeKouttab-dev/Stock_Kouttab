"""Recap du soir de la buvette : une fois par jour a partir de 23 h (Paris).

Greffe sur l'outbox-worker, qui passe toutes les dix minutes : sans la date du
dernier envoi en base, chaque passage apres 23 h renverrait le meme courriel.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, time

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.errors import ErrorCode
from app.crud import buvette as buvette_crud
from app.crud import buvette_cloture as cloture_crud
from app.crud.buvette_inventaire import paris_vers_utc
from app.schemas.buvette import BuvetteProductCreate, CaisseEtatIn, CaisseVenteIn
from app.services import recap_buvette


pytestmark = pytest.mark.integration

JOUR = date(2026, 10, 5)
A_23H05 = datetime.combine(JOUR, time(23, 5), tzinfo=buvette_crud.PARIS)


def _produit(db: Session, nom: str, *, prix: int, quantite: int = 10, seuil: int = 5):
    return buvette_crud.create_product(
        db,
        BuvetteProductCreate(
            name=nom, price_cents=prix, quantity=quantite, seuil_alerte=seuil,
            caisse_category="boissons",
        ),
    )


def _vente(
    db: Session, produit, quantite: int, *, carte: bool = True, heure: int = 15, minute: int = 0
) -> None:
    buvette_crud.record_caisse_sale(
        db,
        CaisseVenteIn(
            transaction_id=str(uuid.uuid4()),
            sumup_tx_code="TXRECAP1" if carte else None,
            total_cents=quantite * produit.price_cents,
            sold_at=datetime.combine(JOUR, time(heure, minute)),
            lines=[{
                "product_id": produit.id, "name": produit.name,
                "quantity": quantite, "unit_price_cents": produit.price_cents,
            }],
        ),
    )


def _recaps(captured_emails) -> list:
    return [m for m in captured_emails if m.subject.startswith("Buvette : récapitulatif")]


def _cloturer(db: Session, *, heure: int, compte: int, saisi_par: str = "Yusuf"):
    """Cloture faite le JOUR a `heure` (Paris) ; premier comptage : depuis le JOUR."""
    instant = paris_vers_utc(datetime.combine(JOUR, time(heure, 0))).replace(tzinfo=None)
    return cloture_crud.cloturer(
        db, compte_cents=compte, commentaire=None, debut=JOUR, saisi_par=saisi_par,
        instant=instant,
    )


@pytest.fixture()
def journee(db_session: Session):
    the = _produit(db_session, "Thé à la menthe", prix=150)
    cookie = _produit(db_session, "Cookie", prix=200, quantite=4, seuil=5)
    _vente(db_session, the, 3)
    _vente(db_session, cookie, 1, carte=False)
    _cloturer(db_session, heure=22, compte=150, saisi_par="Yusuf")
    buvette_crud.enregistrer_etat(
        db_session,
        CaisseEtatIn(
            batterie_pct=64, en_charge=False, version_code=7, version_name="0.7.0",
            sumup_connecte=True, lecteur_connecte=True, lecteur_batterie_pct=80,
            ventes_en_attente=0, ventes_rejetees=0, ecran="accueil",
        ),
    )


def test_le_recap_dit_l_essentiel_de_la_journee(db_session: Session, journee) -> None:
    sujet, corps = recap_buvette.composer(recap_buvette.donnees_du_jour(db_session, JOUR))

    assert sujet == "Buvette : récapitulatif du 05/10/2026"
    assert "lundi 5 octobre 2026" in corps
    assert "Total : 6,50 € (2 vente(s))" in corps
    assert "Carte : 4,50 €" in corps
    assert "Espèces : 2,00 €" in corps
    assert "HelloAsso : 0,00 €" in corps
    assert "Thé à la menthe : 3 vendu(s), 4,50 €" in corps
    assert "Cookie : il en reste 3 (seuil : 5)" in corps  # sous le seuil
    assert "À 22 h 00, par Yusuf : attendu 2,00 €, compté 1,50 €, manque de 0,50 €." in corps
    # Aucune vente especes depuis : pas de ligne sur la boite.
    assert "Depuis la dernière clôture" not in corps
    assert "dernier contact il y a moins d'une minute" in corps
    assert "batterie 64 %" in corps
    assert "—" not in corps and "—" not in sujet


def test_sans_cloture_ni_tablette_le_recap_le_dit(db_session: Session) -> None:
    _, corps = recap_buvette.composer(recap_buvette.donnees_du_jour(db_session, JOUR))
    assert "Aucun comptage des espèces enregistré" in corps
    assert "Aucun signal reçu de la tablette" in corps
    assert "Aucune vente aujourd'hui" in corps


def test_rien_avant_23_heures(db_session: Session, captured_emails) -> None:
    a_22h59 = datetime.combine(JOUR, time(22, 59), tzinfo=buvette_crud.PARIS)
    assert asyncio.run(recap_buvette.envoyer_recap_si_l_heure(db_session, a_22h59)) is False
    assert _recaps(captured_emails) == []


def test_un_seul_recap_par_jour(db_session: Session, journee, captured_emails) -> None:
    assert asyncio.run(recap_buvette.envoyer_recap_si_l_heure(db_session, A_23H05)) is True
    a_23h55 = datetime.combine(JOUR, time(23, 55), tzinfo=buvette_crud.PARIS)
    assert asyncio.run(recap_buvette.envoyer_recap_si_l_heure(db_session, a_23h55)) is False

    assert len(_recaps(captured_emails)) == 1
    assert buvette_crud.lire_reglage(db_session, buvette_crud.REGLAGE_DERNIER_RECAP) == "2026-10-05"


def test_l_heure_est_celle_de_paris_et_non_du_serveur(db_session: Session, captured_emails) -> None:
    """21 h 30 UTC en octobre = 23 h 30 a Paris : le recap part."""
    from datetime import timezone

    utc = datetime(2026, 10, 5, 21, 30, tzinfo=timezone.utc)
    assert asyncio.run(recap_buvette.envoyer_recap_si_l_heure(db_session, utc)) is True


def test_les_destinataires_sont_lus_en_base(
    db_session: Session, admin_stock_user, admin_benevoles_user, captured_emails
) -> None:
    buvette_crud.enregistrer_destinataires(db_session, ["tresorier@exemple.fr"])

    asyncio.run(recap_buvette.envoyer_recap_si_l_heure(db_session, A_23H05))

    (recap,) = _recaps(captured_emails)
    assert recap.recipients == [admin_stock_user.email, "tresorier@exemple.fr"]


def test_un_echec_d_envoi_laisse_le_passage_suivant_reessayer(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _panne(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AppException(ErrorCode.EMAIL_SEND_FAILED)

    monkeypatch.setattr("app.services.email._send_raw", _panne)
    with pytest.raises(AppException):
        asyncio.run(recap_buvette.envoyer_recap_si_l_heure(db_session, A_23H05))
    assert buvette_crud.lire_reglage(db_session, buvette_crud.REGLAGE_DERNIER_RECAP) is None


def test_l_essai_manuel_n_ecrit_qu_a_l_adresse_donnee(
    db_session: Session, journee, captured_emails
) -> None:
    envoyes = asyncio.run(recap_buvette.envoyer_recap(db_session, JOUR, ["omar@exemple.fr"]))

    assert envoyes == ["omar@exemple.fr"]
    (recap,) = _recaps(captured_emails)
    assert recap.recipients == ["omar@exemple.fr"]
    # L'essai ne compte pas comme l'envoi du soir.
    assert buvette_crud.lire_reglage(db_session, buvette_crud.REGLAGE_DERNIER_RECAP) is None


def test_deux_clotures_du_jour_et_la_boite_depuis_la_derniere(db_session: Session) -> None:
    cookie = _produit(db_session, "Cookie", prix=200)
    _vente(db_session, cookie, 1, carte=False, heure=10)
    _cloturer(db_session, heure=12, compte=200, saisi_par="Yusuf")
    _vente(db_session, cookie, 2, carte=False, heure=14)
    _cloturer(db_session, heure=18, compte=450, saisi_par="Bilal")
    _vente(db_session, cookie, 1, carte=False, heure=21, minute=30)

    _, corps = recap_buvette.composer(recap_buvette.donnees_du_jour(db_session, JOUR))
    assert "À 12 h 00, par Yusuf : attendu 2,00 €, compté 2,00 €, aucun écart." in corps
    assert "À 18 h 00, par Bilal : attendu 4,00 €, compté 4,50 €, excédent de 0,50 €." in corps
    assert "Depuis la dernière clôture, espèces attendues dans la boîte : 2,00 €." in corps
    assert "—" not in corps


def test_sans_cloture_du_jour_le_recap_donne_le_dernier_comptage(db_session: Session) -> None:
    cookie = _produit(db_session, "Cookie", prix=200)
    _vente(db_session, cookie, 1, carte=False, heure=10)
    _cloturer(db_session, heure=12, compte=200)
    _vente(db_session, cookie, 3, carte=False, heure=16)

    lendemain = date(2026, 10, 6)
    _, corps = recap_buvette.composer(recap_buvette.donnees_du_jour(db_session, lendemain))
    assert (
        "Aucune clôture aujourd'hui. Dernier comptage le 05/10/2026 à 12 h 00 (clôture) ; "
        "espèces attendues dans la boîte : 6,00 €."
    ) in corps
