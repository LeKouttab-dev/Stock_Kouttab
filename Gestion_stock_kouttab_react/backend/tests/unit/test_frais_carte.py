"""Frais SumUp des paiements par carte : une seule fonction, en centimes entiers.

SumUp preleve un pourcentage sur chaque transaction, arrondi au centime le plus
proche (demi vers le haut). Ecran, Excel et recap passent tous par
`crud.buvette.frais_carte_cents`.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.crud import buvette as buvette_crud
from app.db.models import BuvetteSale


@pytest.mark.parametrize(
    ("total", "taux", "attendu"),
    [
        (0, 170, 0),
        (100, 170, 2),  # 1,7 -> 2
        (450, 170, 8),  # 7,65 -> 8
        (200, 170, 3),  # 3,4 -> 3
        (250, 170, 4),  # 4,25 -> 4
        (5000, 170, 85),  # exact
        (2500, 170, 43),  # 42,5 : demi vers le haut
        (29, 170, 0),  # 0,493 -> 0
        (30, 170, 1),  # 0,51 -> 1
        (450, 0, 0),
        (450, 250, 11),  # 11,25 -> 11
        (-450, 170, -8),  # symetrique (remboursement)
    ],
)
def test_frais_arrondis_au_centime_le_plus_proche(total: int, taux: int, attendu: int) -> None:
    resultat = buvette_crud.frais_carte_cents(total, taux)
    assert resultat == attendu
    assert isinstance(resultat, int)


def _ligne(id_: int, tx: str, montant: int, *, code: str | None = "TX1", ligne: int = 0) -> BuvetteSale:
    return BuvetteSale(
        id=id_,
        source="caisse",
        caisse_tx_id=tx,
        caisse_line=ligne,
        sumup_tx_code=code,
        product_name_snapshot=f"p{id_}",
        quantity_sold=1,
        amount_cents=montant,
        sold_at=datetime(2026, 10, 5, 10, id_),
    )


def test_les_frais_portent_sur_la_transaction_entiere() -> None:
    # Deux articles a 2,00 et 2,50 : par article 3 + 4 = 7 cts, par transaction 8.
    lignes = [_ligne(1, "a", 200, ligne=0), _ligne(2, "a", 250, ligne=1)]
    (vente,) = buvette_crud.ventes_regroupees(lignes, None, 170)
    assert (vente["total_cents"], vente["frais_cents"], vente["net_cents"]) == (450, 8, 442)


def test_aucun_frais_hors_carte_et_resume() -> None:
    lignes = [
        _ligne(1, "a", 450),
        _ligne(2, "b", 300, code=None),  # especes
        _ligne(3, "c", 100),
    ]
    ventes = buvette_crud.ventes_regroupees(lignes, None, 170)
    especes = next(v for v in ventes if v["moyen"] == "especes")
    assert (especes["frais_cents"], especes["net_cents"]) == (None, 300)
    assert buvette_crud.resume_carte(ventes) == {
        "nb": 2, "brut_cents": 550, "frais_cents": 10, "net_cents": 540,
    }
