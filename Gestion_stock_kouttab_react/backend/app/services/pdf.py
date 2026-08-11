"""Normalisation des justificatifs en PDF avant envoi au comptable.

Choix de ``img2pdf`` plutot que Pillow seul : il embarque le flux JPEG **tel
quel** dans le conteneur PDF, sans re-encodage. Un ticket de caisse photographie
est deja compresse ; le repasser dans Pillow le recompresserait une seconde fois
et degraderait la lisibilite des montants — exactement ce qu'un comptable a
besoin de lire.

Pur Python, sans binaire systeme : compatible avec l'hebergement mutualise
O2Switch.
"""

from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import img2pdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger


logger = get_logger("pdf")


PDF_MAGIC = b"%PDF"

# Gabarit A4. Sans contrainte explicite, img2pdf deduit les dimensions physiques
# des DPI de l'image : les photos de smartphone n'en declarent souvent pas, ce
# qui produit des pages de plusieurs metres, illisibles a l'impression.
_A4_LAYOUT = img2pdf.get_layout_fun(
    pagesize=(img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297)),
    fit=img2pdf.FitMode.into,
)


def is_pdf(path: Path) -> bool:
    """Detection par magic bytes uniquement — jamais par l'extension."""
    try:
        with open(path, "rb") as handle:
            return handle.read(len(PDF_MAGIC)) == PDF_MAGIC
    except OSError:
        return False


_EXIF_ORIENTATION_TAG = 274
_DIRECT_MODES = ("RGB", "L")


def _normalise_image(source: Path) -> bytes:
    """Retourne les octets d'image prets pour img2pdf.

    Le chemin nominal ne touche a rien : les octets d'origine sont transmis tels
    quels a img2pdf, qui embarque un JPEG sans le re-encoder. C'est tout
    l'interet du choix de la bibliotheque, et il faut donc eviter tout aller-
    retour par Pillow quand il n'apporte rien.

    Deux situations imposent malgre tout un re-encodage :
    - **EXIF Orientation** : img2pdf l'ignore, une photo prise en portrait
      ressortirait couchee dans le PDF ;
    - **modes de couleur non geres** (RGBA, palette, CMYK), qui font echouer
      img2pdf ; on les aplatit sur fond blanc.

    NB : ``ImageOps.exif_transpose`` retourne *toujours* une nouvelle instance,
    y compris sans EXIF. On teste donc explicitement le tag plutot que l'identite
    de l'objet, sinon chaque JPEG serait recompresse inutilement.
    """
    with Image.open(source) as image:
        try:
            orientation = image.getexif().get(_EXIF_ORIENTATION_TAG, 1)
        except Exception:  # noqa: BLE001 — EXIF corrompu : on l'ignore
            orientation = 1

        if orientation in (1, None) and image.mode in _DIRECT_MODES:
            return source.read_bytes()

        oriented = ImageOps.exif_transpose(image) or image
        if oriented.mode in ("RGBA", "LA", "P"):
            converted = oriented.convert("RGBA")
            background = Image.new("RGB", converted.size, (255, 255, 255))
            background.paste(converted, mask=converted.split()[-1])
            oriented = background
        elif oriented.mode not in _DIRECT_MODES:
            oriented = oriented.convert("RGB")

        buffer = BytesIO()
        oriented.save(buffer, format="PNG")
        return buffer.getvalue()


def image_bytes_to_pdf(payload: bytes) -> bytes:
    """Enveloppe des octets JPEG/PNG deja en memoire dans un PDF A4.

    Meme mise en page que :func:`convert_image_to_pdf`, sans aller-retour par
    le disque : le scanner produit son image en memoire et la rend directement
    au deposant en PDF.
    """
    try:
        return img2pdf.convert(payload, layout_fun=_A4_LAYOUT)
    except Exception as exc:  # noqa: BLE001 — img2pdf leve des types varies
        logger.exception("Echec de conversion PDF depuis la memoire : %s", exc)
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="La conversion du document scanne en PDF a echoue.",
        ) from exc


def convert_image_to_pdf(source: Path, target: Path) -> Path:
    """Convertit une image en PDF A4 d'une page."""
    try:
        payload = _normalise_image(source)
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("Image illisible, conversion PDF impossible : %s", source)
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="Ce justificatif n'a pas pu etre lu comme une image.",
            extras={"file": source.name},
        ) from exc

    try:
        pdf_bytes = img2pdf.convert(payload, layout_fun=_A4_LAYOUT)
    except Exception as exc:  # noqa: BLE001 — img2pdf leve des types varies
        logger.exception("Echec de conversion PDF pour %s : %s", source, exc)
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="La conversion de ce justificatif en PDF a echoue.",
            extras={"file": source.name},
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(pdf_bytes)
    return target


def ensure_pdf(source: Path, *, target_dir: Path, target_stem: str) -> tuple[Path, bool]:
    """Produit ``target_dir/target_stem.pdf`` a partir de ``source``.

    Retourne ``(chemin, a_ete_converti)``. La source n'est jamais modifiee ni
    supprimee : les originaux deposes restent intacts dans ``uploads/``.

    La copie est systematique meme quand la source est deja un PDF, car la piece
    jointe doit porter son nom definitif sur le disque — fastapi-mail nomme
    l'attachement d'apres le fichier, et nos uploads sont des ``{uuid}.pdf``.
    """
    source = Path(source)
    if not source.exists():
        raise AppException(
            ErrorCode.FILE_PHYSICALLY_MISSING,
            detail="Le justificatif est introuvable sur le disque.",
            extras={"file": source.name},
        )

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{target_stem}.pdf"

    if is_pdf(source):
        shutil.copyfile(source, target)
        return target, False

    convert_image_to_pdf(source, target)
    return target, True
