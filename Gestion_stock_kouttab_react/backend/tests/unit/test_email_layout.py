"""Mise en page des courriels.

Ces messages sont ce que les benevoles voient le plus souvent de
l'application : beaucoup ne s'y connectent qu'apres en avoir recu un. Le
registre compte donc autant que le contenu — d'ou la salutation demandee par le
client, et des details qui evitent d'avoir a ouvrir l'application pour
comprendre de quoi il s'agit.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services import email_layout as L


pytestmark = pytest.mark.unit


def test_la_salutation_reprend_le_prenom():
    assert L.entete("Omar").startswith("Assalamu alaykum")
    assert "Omar" in L.entete("Omar")


def test_la_salutation_reste_correcte_sans_prenom():
    """Beaucoup de comptes n'ont pas de prenom renseigne : le message ne doit
    pas s'ouvrir sur un blanc ni sur une virgule esseulee."""
    entete = L.entete(None)
    assert entete == "Assalamu alaykum wa rahmatullah,"
    assert "  " not in entete


def test_les_champs_vides_disparaissent():
    """Un courriel troue de « - » a l'air d'un envoi automatique mal configure,
    alors qu'il s'agit de champs facultatifs que personne n'a remplis."""
    corps = L.details(
        [("Fournisseur", "Metro"), ("Nature", None), ("Commentaire", "  "), ("Montant", 12)]
    )
    assert "Fournisseur" in corps
    assert "Nature" not in corps
    assert "Commentaire" not in corps


def test_les_montants_sont_formates_en_euros():
    assert "42.50 EUR" in L.details([("Montant", Decimal("42.5"))])
    assert "12.00 EUR" in L.details([("Montant", 12)])


def test_les_dates_sont_en_format_francais():
    assert "03/08/2026" in L.details([("Date", date(2026, 8, 3))])


def test_les_valeurs_sont_alignees():
    """Un bloc de dix lignes se lit d'un coup d'oeil quand les valeurs sont
    alignees ; en colonnes decalees, il faut le parcourir."""
    corps = L.details([("Nom", "A"), ("Fournisseur tres long", "B")])
    colonnes = {ligne.index(":") for ligne in corps.splitlines()}
    assert len(colonnes) == 1


def test_un_message_complet_porte_salutation_details_et_signature():
    message = L.composer(
        prenom="Omar",
        introduction="Une note de frais attend votre validation.",
        blocs=[("Montant", Decimal("42.50"))],
        conclusion="Rendez-vous dans l'application.",
    )
    assert message.startswith("Assalamu alaykum")
    assert "42.50 EUR" in message
    assert "Rendez-vous dans l'application." in message
    assert message.rstrip().endswith("L'institut Le Kouttâb")


def test_un_message_sans_detail_reste_lisible():
    message = L.composer(introduction="Bienvenue.")
    assert "Bienvenue." in message
    # Pas de bloc vide ni de lignes blanches en rafale.
    assert "\n\n\n" not in message
