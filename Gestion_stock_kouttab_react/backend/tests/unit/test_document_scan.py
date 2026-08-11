"""Tests du redressement de documents photographies."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.document_scan import (
    detect_document_quad,
    order_corners,
    scan_document,
)


pytestmark = pytest.mark.unit


def _photo_de_document(
    *,
    quad: list[tuple[int, int]] | None = None,
    taille: tuple[int, int] = (900, 700),
) -> tuple[bytes, list[tuple[int, int]]]:
    """Fabrique une photo : feuille blanche imprimee, posee sur un fond sombre.

    ``quad`` place les coins de la feuille dans l'image ; par defaut elle est
    de travers, comme une photo prise a main levee.
    """
    largeur, hauteur = taille
    fond = np.full((hauteur, largeur, 3), 40, dtype=np.uint8)

    if quad is None:
        quad = [(140, 90), (760, 150), (720, 610), (180, 540)]

    # Feuille blanche.
    cv2.fillConvexPoly(fond, np.array(quad, dtype=np.int32), (245, 245, 245))
    # Quelques lignes de texte, pour que le contenu ne soit pas uniforme.
    for i in range(6):
        y = 160 + i * 55
        cv2.line(fond, (240, y), (640, y), (30, 30, 30), 6)

    ok, encoded = cv2.imencode(".jpg", fond)
    assert ok
    return encoded.tobytes(), quad


def test_order_corners_normalise_l_ordre_des_sommets() -> None:
    # Fournis dans le desordre : bas-droit, haut-gauche, bas-gauche, haut-droit.
    desordre = [(90.0, 80.0), (10.0, 10.0), (10.0, 80.0), (90.0, 10.0)]

    assert order_corners(desordre) == [
        (10.0, 10.0),
        (90.0, 10.0),
        (90.0, 80.0),
        (10.0, 80.0),
    ]


def test_order_corners_refuse_autre_chose_qu_un_quadrilatere() -> None:
    with pytest.raises(ValueError):
        order_corners([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])


def test_detect_document_quad_retrouve_les_coins_de_la_feuille() -> None:
    image, attendu = _photo_de_document()

    detecte = detect_document_quad(image)

    assert detecte is not None
    # Tolerance de 25 px : Canny suit le bord du a-plat blanc, pas le pixel
    # exact du polygone dessine.
    for (x, y), (ax, ay) in zip(detecte, order_corners(attendu)):
        assert abs(x - ax) <= 25, f"x={x} attendu {ax}"
        assert abs(y - ay) <= 25, f"y={y} attendu {ay}"


def test_detect_document_quad_rend_none_sans_document() -> None:
    # Bruit uniforme : aucun quadrilatere ne s'en detache.
    rng = np.random.default_rng(seed=1234)
    bruit = rng.integers(0, 255, size=(400, 400, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", bruit)
    assert ok

    assert detect_document_quad(encoded.tobytes()) is None


def test_scan_document_redresse_et_recadre() -> None:
    image, _ = _photo_de_document(taille=(900, 700))

    resultat = scan_document(image)

    decode = cv2.imdecode(np.frombuffer(resultat, np.uint8), cv2.IMREAD_GRAYSCALE)
    hauteur, largeur = decode.shape[:2]
    # Le fond sombre a disparu : l'image ne contient plus que la feuille.
    assert largeur < 900 and hauteur < 700
    # Une feuille redressee est claire dans son ensemble.
    assert decode.mean() > 120


def test_scan_document_respecte_un_cadrage_impose() -> None:
    """Le cadrage corrige a la main prime sur la detection automatique."""
    image, _ = _photo_de_document()
    impose = [(100.0, 100.0), (300.0, 100.0), (300.0, 250.0), (100.0, 250.0)]

    resultat = scan_document(image, quad=impose, enhance=False)

    decode = cv2.imdecode(np.frombuffer(resultat, np.uint8), cv2.IMREAD_COLOR)
    hauteur, largeur = decode.shape[:2]
    assert abs(largeur - 200) <= 2
    assert abs(hauteur - 150) <= 2


def test_scan_document_rend_l_image_entiere_quand_rien_n_est_detecte() -> None:
    """Une detection en echec ne doit pas bloquer le depot."""
    rng = np.random.default_rng(seed=99)
    bruit = rng.integers(0, 255, size=(300, 400, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", bruit)
    assert ok

    resultat = scan_document(encoded.tobytes(), enhance=False)

    decode = cv2.imdecode(np.frombuffer(resultat, np.uint8), cv2.IMREAD_COLOR)
    assert decode.shape[:2] == (300, 400)


def test_scan_document_preserve_les_couleurs() -> None:
    """Le rattrapage d'eclairage ne doit pas decolorer le document.

    Une version anterieure convertissait en niveaux de gris : les mentions
    surlignees, logos et tampons d'une facture perdaient leur couleur, alors
    qu'elle porte de l'information.
    """
    largeur, hauteur = 900, 700
    fond = np.full((hauteur, largeur, 3), 40, dtype=np.uint8)
    quad = np.array([(140, 90), (760, 150), (720, 610), (180, 540)], dtype=np.int32)
    cv2.fillConvexPoly(fond, quad, (245, 245, 245))
    # Un aplat rouge franc au milieu de la feuille (BGR).
    cv2.rectangle(fond, (300, 250), (560, 400), (40, 40, 220), -1)
    ok, encoded = cv2.imencode(".jpg", fond)
    assert ok

    resultat = scan_document(encoded.tobytes(), enhance=True)

    decode = cv2.imdecode(np.frombuffer(resultat, np.uint8), cv2.IMREAD_COLOR)
    assert decode.ndim == 3 and decode.shape[2] == 3, "la sortie doit rester en couleur"
    bleu, vert, rouge = cv2.split(decode.astype(int))
    # Le rouge domine encore largement : l'aplat n'a pas ete transforme en gris.
    assert (rouge - vert).max() > 80
    assert (rouge - bleu).max() > 80


def test_scan_document_refuse_des_octets_illisibles() -> None:
    from app.core.exceptions import AppException

    with pytest.raises(AppException):
        scan_document(b"ceci n'est pas une image")
