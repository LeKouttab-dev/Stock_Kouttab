"""Preparation des photos de produits, avant enregistrement en base.

Ce qui arrive ici vient d'un telephone ou d'un ordinateur : une photo de
4 000 px, parfois en HEIC, parfois couchee sur le cote. Ce qui en sort est une
vignette JPEG de 600 px de large au plus.

**Pourquoi reduire.** La photo est servie a la tablette de caisse, qui l'affiche
dans une fiche de 168 dp — 400 a 600 px suffisent, c'est le chiffre donne par
l'application Android. Sans reduction, chaque photo peserait quelques
mega-octets : autant en base (sauvegardee chaque nuit), autant sur le reseau du
local a chaque nouveau catalogue, et la tablette les precharge toutes d'un coup.

**Pourquoi JPEG.** Un format unique evite de deviner a la lecture, et il est le
seul que tous les chargeurs d'image affichent sans discuter. La transparence
d'un PNG est aplatie sur du blanc : la tablette affiche justement les photos sur
fond blanc.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger


logger = get_logger("images")

try:  # pragma: no cover - dependance optionnelle a l'import
    import pillow_heif

    # Les photos prises depuis « Fichiers » sur iOS arrivent en HEIC, que
    # Pillow ne sait pas ouvrir seul. Meme enregistrement que dans `pdf.py`.
    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pillow_heif = None

# Cote le plus long de la vignette servie a la tablette.
LARGEUR_MAX = 600
QUALITE_JPEG = 82
TYPE_PHOTO = "image/jpeg"


def preparer_photo(contenu: bytes) -> tuple[bytes, str]:
    """Rend `(octets JPEG, type MIME)` prets a etre enregistres.

    Leve `AppException` si le contenu n'est pas une image que l'on sache lire —
    la validation de signature a deja eu lieu dans `services/files.py`, mais un
    fichier tronque passe cette premiere barriere.
    """
    try:
        with Image.open(io.BytesIO(contenu)) as image:
            # `exif_transpose` rend TOUJOURS une nouvelle instance : sans elle,
            # une photo prise en portrait arrive couchee sur la tablette.
            redresse = ImageOps.exif_transpose(image) or image
            # `thumbnail` conserve le rapport et ne fait que reduire : une
            # petite image n'est jamais etiree.
            redresse.thumbnail((LARGEUR_MAX, LARGEUR_MAX), Image.LANCZOS)
            if redresse.mode in ("RGBA", "LA", "P"):
                fond = Image.new("RGB", redresse.size, (255, 255, 255))
                masque = redresse.convert("RGBA")
                fond.paste(masque, mask=masque.split()[-1])
                redresse = fond
            elif redresse.mode != "RGB":
                redresse = redresse.convert("RGB")

            sortie = io.BytesIO()
            redresse.save(sortie, format="JPEG", quality=QUALITE_JPEG, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.warning("Photo de produit illisible : %s", exc)
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Image illisible. Deposez une photo JPEG, PNG, WEBP ou HEIC.",
        ) from exc

    return sortie.getvalue(), TYPE_PHOTO


__all__ = ["LARGEUR_MAX", "TYPE_PHOTO", "preparer_photo"]
