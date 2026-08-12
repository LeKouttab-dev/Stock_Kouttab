"""Montant du a un benevole : jumeau backend de `frontend/src/lib/money.ts`.

Les deux modules doivent rendre le meme chiffre sur les memes donnees. Le front
l'affiche au benevole et a la comptabilite ; le back le grave dans le
justificatif remis puis dans `Remboursements.montant_total`. Une divergence
produirait un document contredisant l'ecran qui l'a declenche.

Les cas ci-dessous sont ceux de `money.test.ts` — les completer d'un cote
suppose de les completer de l'autre.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.money import montant_du, total_a_rembourser


pytestmark = pytest.mark.unit


def _note(montant: str, avance: str = "0", remise: str = "0"):
    class _Note:
        pass

    n = _Note()
    n.montant = Decimal(montant)
    n.remboursement_deja_emis = Decimal(avance)
    n.remise = Decimal(remise)
    return n


def test_sans_avance_ni_remise():
    assert montant_du(_note("42.50")) == Decimal("42.50")


def test_l_avance_en_especes_est_deduite():
    """Le benevole a deja recu 20 € en liquide : on ne lui doit que le reste."""
    assert montant_du(_note("50.00", avance="20.00")) == Decimal("30.00")


def test_la_remise_est_deduite():
    assert montant_du(_note("50.00", remise="5.50")) == Decimal("44.50")


def test_le_resultat_ne_descend_jamais_sous_zero():
    """Un remboursement negatif s'afficherait comme une dette du benevole
    envers l'association : ce n'est pas ce que la donnee veut dire."""
    assert montant_du(_note("10.00", avance="30.00")) == Decimal("0")


def test_les_centimes_restent_exacts():
    """Decimal et non float : `0.1 + 0.2` en virgule flottante fait 0.30000000000000004,
    et un justificatif comptable ne peut pas se permettre ce genre d'ecart."""
    total = total_a_rembourser([_note("0.10"), _note("0.20")])
    assert total == Decimal("0.30")


def test_valeurs_absentes_traitees_comme_zero():
    note = _note("15.00")
    note.remboursement_deja_emis = None
    note.remise = None
    assert montant_du(note) == Decimal("15.00")


def test_total_d_un_remboursement_groupe():
    notes = [_note("30.00"), _note("20.00", avance="5.00"), _note("10.00", remise="2.00")]
    assert total_a_rembourser(notes) == Decimal("53.00")


def test_total_d_une_liste_vide():
    assert total_a_rembourser([]) == Decimal("0")
