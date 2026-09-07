"""Le filet qui garantit une adresse d'application dans chaque courriel.

Les gabarits qui savent où envoyer leur lecteur posent leur propre lien — et le
bon selon le compte (cf. `test_liens_dans_les_emails.py`). Tous ne le savaient
pas : l'alerte de stock, l'avis de dépôt, la demande de compte partaient avec
« connectez-vous à l'application » et rien de plus, à charge pour le
destinataire de retrouver le domaine de mémoire.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import email_layout, liens


pytestmark = pytest.mark.unit


def test_un_corps_sans_lien_en_recoit_un():
    corps = email_layout.composer(introduction="Une alerte de stock.")
    assert not liens.contient_un_lien(corps)
    assert settings.frontend_url.rstrip("/") in liens.garantir_lien(corps)


def test_un_corps_qui_porte_deja_un_lien_n_est_pas_touche():
    """Le gabarit qui a choisi sa destination fait autorité : un second lien,
    générique, ferait douter de celui qui vise juste."""
    corps = email_layout.composer(
        introduction="Votre note a ete approuvee.",
        conclusion=liens.avec_lien(None, "https://gestion.lekouttab.fr/benevole"),
    )
    assert liens.garantir_lien(corps) == corps


def test_le_lien_se_glisse_avant_la_signature():
    """Posé après « L'institut Le Kouttâb », il se lirait comme une pièce
    rapportée au bas d'un message déjà terminé."""
    corps = email_layout.composer(introduction="Une alerte de stock.")
    complete = liens.garantir_lien(corps)
    assert complete.index(liens.LIBELLE_ACCES) < complete.index(email_layout.SIGNATURE)
    assert complete.endswith(email_layout.SIGNATURE)


def test_un_corps_sans_signature_recoit_le_lien_a_la_fin():
    """Les envois comptables signent autrement ; le filet ne doit pas les
    laisser sans adresse pour autant."""
    complete = liens.garantir_lien("Une piece est jointe.\n\nCordialement,")
    assert liens.contient_un_lien(complete)


def test_le_filet_est_idempotent():
    corps = liens.garantir_lien(email_layout.composer(introduction="Une alerte."))
    assert liens.garantir_lien(corps) == corps
