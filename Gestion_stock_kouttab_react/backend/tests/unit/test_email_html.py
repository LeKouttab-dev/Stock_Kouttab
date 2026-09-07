"""La doublure HTML des courriels : ce qui la justifie, et ses limites.

Une URL nue dans un message en texte seul dépend du bon vouloir du client de
messagerie — certains la coupent au retour à la ligne, d'autres ne la détectent
pas — et le lecteur en est réduit à recopier un domaine à la main. La version
HTML en fait un bouton.

Ce qu'elle ne fait PAS, et qu'aucun format de courriel ne permet : forcer le
navigateur du système. L'application Gmail sur mobile ouvre les liens dans sa
vue intégrée, et c'est un réglage du lecteur. `target="_blank"` garantit
seulement qu'un webmail ouvre un onglet plutôt que de remplacer la boîte.
"""

from __future__ import annotations

import pytest

from app.services import email_html, email_layout, liens


pytestmark = pytest.mark.unit


CORPS = email_layout.composer(
    prenom="Yassine",
    introduction="Votre note de frais #12 a ete approuvee.",
    blocs=[("Note de frais", "#12"), ("Montant", "10.37")],
    conclusion=liens.avec_lien(None, "https://stock.lekouttab.fr/expenses"),
)


def test_le_lien_s_ouvre_dans_un_nouvel_onglet():
    """Sans `target`, un webmail remplace la boîte de réception par la page."""
    html = email_html.en_html(CORPS)
    assert 'href="https://stock.lekouttab.fr/expenses"' in html
    assert 'target="_blank"' in html
    # `rel` va avec `target` : sans lui, la page ouverte garde une poignée sur
    # celle qui l'a ouverte.
    assert 'rel="noopener noreferrer"' in html


def test_la_ligne_d_acces_devient_un_bouton():
    """Le geste attendu du lecteur ne doit pas se confondre avec le corps."""
    html = email_html.en_html(CORPS)
    assert ">Acceder a votre espace</a>" in html
    assert "display:inline-block" in html
    # L'URL n'est plus affichée en clair : elle est portée par le bouton.
    assert ">https://stock.lekouttab.fr/expenses</a>" not in html


def test_le_bloc_de_details_devient_un_tableau():
    """`email_layout.details` aligne à coups d'espaces — utile en texte brut,
    absurde en HTML où la police n'est pas à chasse fixe."""
    html = email_html.en_html(CORPS)
    assert "<table" in html
    assert ">Note de frais</td>" in html
    assert ">#12</td>" in html
    assert "  " not in html.replace("\n", "")  # plus de remplissage résiduel


def test_une_phrase_ne_devient_pas_un_tableau():
    """Une ligne du corps peut contenir « : » sans être un bloc de détails ;
    la traiter comme tel produirait un tableau bancal."""
    html = email_html.en_html("Bonjour,\n\nVoici la regle : elle tient en un mot.")
    assert "<table" not in html


def test_le_texte_est_echappe():
    """Un commentaire de la comptabilité finit dans le corps : rien de ce qui
    en vient ne doit pouvoir se refermer en balise."""
    html = email_html.en_html("Commentaire : <script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_l_url_ne_mange_pas_la_ponctuation_finale():
    html = email_html.en_html("Voir https://stock.lekouttab.fr/expenses, puis revenir.")
    assert 'href="https://stock.lekouttab.fr/expenses"' in html


def test_les_sauts_de_ligne_survivent():
    """Le texte brut porte sa mise en page dans ses retours à la ligne ;
    les perdre collerait tout le message en un pavé."""
    html = email_html.en_html("Ligne un\nLigne deux")
    assert "<br>" in html


# ---- Ce qui part vraiment sur le fil ---------------------------------------


def _message(corps: str, **kwargs):
    from app.services import email as email_service

    return email_service.composer_message(
        "Sujet", corps, ["quelqu-un@lekouttab.fr"], **kwargs
    )


def test_le_message_porte_les_deux_versions():
    """`multipart/alternative` : le client choisit. Le texte reste la partie
    principale — c'est lui qu'on relit dans l'ecran « Envois », et celui que
    rendent les clients qui ignorent le HTML."""
    message = _message(CORPS)

    assert message.body == liens.garantir_lien(CORPS)
    assert message.alternative_body is not None
    assert "<a href=" in message.alternative_body
    assert message.multipart_subtype.value == "alternative"


def test_un_envoi_avec_piece_jointe_reste_en_texte_seul(tmp_path):
    """fastapi-mail accroche les pièces au `multipart/related` qui enveloppe
    l'alternative, et non à un `multipart/mixed` : les PDF du circuit comptable
    risqueraient de ne plus s'afficher. C'est l'envoi où la pièce compte plus
    que le lien."""
    piece = tmp_path / "Frais generaux_Courses_2026-08-12.pdf"
    piece.write_bytes(b"%PDF-1.4\n")

    message = _message(CORPS, attachments=[piece])

    assert message.alternative_body is None
    # fastapi-mail a bien pris la pièce (il la remplace par un UploadFile).
    assert len(message.attachments) == 1
    assert message.attachments[0][0].filename == piece.name


def test_le_filet_pose_le_lien_dans_les_deux_versions():
    message = _message("Connectez-vous a l'application.")

    assert liens.contient_un_lien(message.body)
    assert "<a href=" in message.alternative_body
