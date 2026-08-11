"""Detection et redressement d'un document photographie.

Le deposant photographie son ticket de caisse ou sa facture a main levee : la
feuille est de travers, l'appareil n'est jamais parfaitement au-dessus, et le
plan de travail occupe la moitie du cadre. Ce module retrouve les quatre coins
de la feuille, redresse la perspective et rend une image cadree sur le seul
document — le resultat qu'on attend d'un scanner.

Le traitement est volontairement en deux temps, comme dans les scanners mobiles
(cf. OSS-DocumentScanner) :

1. :func:`detect_document_quad` propose un cadrage. Le client l'affiche en
   surimpression sur la photo pour que le deposant le corrige si besoin.
2. :func:`scan_document` applique le cadrage — celui propose ou celui corrige a
   la main — et produit l'image finale.

Separer les deux compte : une detection automatique se trompe (nappe a motifs,
ticket blanc sur table blanche, coin plie). Sans reprise manuelle, l'echec est
sans recours et le deposant renvoie une photo de travers.

La conversion en PDF n'est pas faite ici : :mod:`app.services.pdf` s'en charge
deja pour tous les justificatifs, avec sa mise en page A4.
"""

from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger


logger = get_logger("document_scan")


Point = tuple[float, float]
Quad = list[Point]


# Au-dela, la detection travaille pour rien : les contours d'une feuille sont
# larges, et redimensionner divise le cout par vingt sur une photo de 12 Mpx.
_DETECTION_MAX_SIDE = 900

# Un quadrilatere plus petit que ce ratio de l'image est un detail du decor
# (etiquette, carrelage), pas la feuille que le deposant cadre.
_MIN_AREA_RATIO = 0.15

# A l'inverse, un quadrilatere qui epouse le cadre entier n'est pas une feuille
# detectee : c'est le bord de la photo, que la dilatation des contours ferme
# toujours. Le seuil est volontairement bas — au-dela, le recadrage ne gagnerait
# que quelques pour cent de surface, pour le risque de rogner un bord reel de
# travers. Un document qui remplit deja le cadre se passe tres bien d'etre
# recadre ; il reste redresse si le deposant corrige les coins a la main.
_MAX_AREA_RATIO = 0.92

# Marge de tolerance sur la convexite du contour, en fraction du perimetre.
_APPROX_EPSILON_RATIO = 0.02


def _decode(image_bytes: bytes) -> np.ndarray:
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Image illisible : formats acceptes JPEG et PNG.",
        )
    return image


def order_corners(points: Sequence[Point]) -> Quad:
    """Ordonne quatre points en haut-gauche, haut-droit, bas-droit, bas-gauche.

    ``cv2.approxPolyDP`` rend les sommets dans l'ordre du contour, qui depend de
    l'orientation de la feuille. Sans normalisation, la transformation de
    perspective produit une image pivotee ou miroir selon la photo.

    La somme des coordonnees est minimale en haut a gauche et maximale en bas a
    droite ; leur difference separe les deux autres.
    """
    if len(points) != 4:
        raise ValueError("Un quadrilatere doit avoir exactement quatre points.")

    array = np.array(points, dtype="float32")
    ordered = np.zeros((4, 2), dtype="float32")

    somme = array.sum(axis=1)
    ordered[0] = array[np.argmin(somme)]
    ordered[2] = array[np.argmax(somme)]

    diff = np.diff(array, axis=1)
    ordered[1] = array[np.argmin(diff)]
    ordered[3] = array[np.argmax(diff)]

    return [(float(x), float(y)) for x, y in ordered]


def detect_document_quad(image_bytes: bytes) -> Quad | None:
    """Retrouve les quatre coins du document, en pixels de l'image d'origine.

    Rend ``None`` quand aucun contour ne se detache — feuille sans marge visible
    ou photo trop floue. L'appelant propose alors la photo entiere, que le
    deposant recadre a la main.
    """
    image = _decode(image_bytes)
    height, width = image.shape[:2]

    # La detection tourne sur une version reduite ; les coins sont remis a
    # l'echelle a la fin, pour ne jamais decouper dans une image degradee.
    scale = min(1.0, _DETECTION_MAX_SIDE / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale) if scale < 1.0 else image

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    # Le flou gomme le grain du papier et la trame d'impression, qui produisent
    # sinon une nuee de petits contours ou se perd celui de la feuille.
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 60, 180)
    # Les bords d'une feuille eclairee de biais sont interrompus ; la dilatation
    # les recolle pour que le contour se ferme.
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    small_area = small.shape[0] * small.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, _APPROX_EPSILON_RATIO * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        aire = cv2.contourArea(approx)
        if aire < _MIN_AREA_RATIO * small_area or aire > _MAX_AREA_RATIO * small_area:
            continue

        points = [(float(p[0][0]), float(p[0][1])) for p in approx]
        ordered = order_corners(points)
        if scale < 1.0:
            ordered = [(x / scale, y / scale) for x, y in ordered]
        logger.info("Document detecte : %s", [(round(x), round(y)) for x, y in ordered])
        return ordered

    logger.info("Aucun contour de document exploitable.")
    return None


def _output_size(quad: Quad) -> tuple[int, int]:
    """Dimensions cibles : les plus grands cotes opposes du quadrilatere.

    Prendre le plus grand des deux cotes opposes evite d'ecraser le document
    quand la photo est prise de biais — le cote le plus proche de l'objectif est
    le moins deforme.
    """
    (tl, tr, br, bl) = quad
    largeur = max(np.linalg.norm(np.array(br) - np.array(bl)),
                  np.linalg.norm(np.array(tr) - np.array(tl)))
    hauteur = max(np.linalg.norm(np.array(tr) - np.array(br)),
                  np.linalg.norm(np.array(tl) - np.array(bl)))
    return max(int(round(largeur)), 1), max(int(round(hauteur)), 1)


def scan_document(
    image_bytes: bytes,
    *,
    quad: Sequence[Point] | None = None,
    enhance: bool = True,
    # 96 et non 92 : le justificatif traverse deja trois etapes destructrices —
    # capture JPEG, redressement, encapsulation PDF — avant d'arriver chez le
    # comptable par courriel. Chacune coute du detail sur des montants ecrits
    # petit. Le gain de poids d'un reglage plus bas ne justifie pas le risque
    # d'un ticket illisible.
    jpeg_quality: int = 96,
) -> bytes:
    """Redresse le document et rend un JPEG cadre sur lui seul.

    ``quad`` : les quatre coins, en pixels de l'image d'origine. Absent, la
    detection automatique s'en charge ; si elle echoue, l'image est rendue
    entiere plutot que rejetee — une photo lisible mais non recadree vaut mieux
    qu'un depot bloque.

    ``enhance`` egalise l'eclairage sans toucher aux couleurs. Un ticket
    photographie a une ombre d'un cote ; sans correction, le montant s'y perd.
    Aucune binarisation : elle efface les tampons palis et les impressions
    thermiques faibles, frequents sur les tickets de caisse.
    """
    image = _decode(image_bytes)

    if quad is None:
        quad = detect_document_quad(image_bytes)

    if quad is not None:
        ordered = order_corners(list(quad))
        largeur, hauteur = _output_size(ordered)
        destination = np.array(
            [[0, 0], [largeur - 1, 0], [largeur - 1, hauteur - 1], [0, hauteur - 1]],
            dtype="float32",
        )
        matrice = cv2.getPerspectiveTransform(np.array(ordered, dtype="float32"), destination)
        image = cv2.warpPerspective(image, matrice, (largeur, hauteur))

    if enhance:
        # Le rattrapage d'eclairage s'applique a la seule *luminance*, dans
        # l'espace LAB : les canaux a et b portent la couleur et ne sont pas
        # touches. Une version anterieure passait par un niveau de gris, ce qui
        # decolorait des factures ou la couleur porte de l'information (mentions
        # surlignees, logos, tampons, cachets).
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        luminance, a, b = cv2.split(lab)
        # CLAHE plutot qu'une egalisation globale : un histogramme unique sur
        # toute la page ecrase les zones deja correctes pour rattraper l'ombre.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        image = cv2.cvtColor(cv2.merge((clahe.apply(luminance), a, b)), cv2.COLOR_LAB2BGR)

    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Le document scanne n'a pas pu etre encode.",
        )
    return encoded.tobytes()
