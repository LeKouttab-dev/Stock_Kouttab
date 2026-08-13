"""Upload helpers : MIME validation, deterministic storage and cleanup."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.services import pdf


logger = get_logger("files")


# (mime, extension) whitelist.
#
# WEBP et HEIC ont rejoint la liste, MIME **et** extension cette fois. WEBP en
# avait ete retire faute d'extension correspondante : un fichier renomme en .jpg
# passait la validation puis etait stocke en .webp, hors du jeu autorise.
#
# HEIC est le format par defaut des photos iPhone des qu'on passe par
# « Fichiers » plutot que par la photothèque. Il etait refuse avec
# « Extension 'heic' non autorisee » — de la prose de developpeur servie a un
# benevole, pour le geste le plus courant de l'application.
IMAGE_MIMES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heic",
}
INVOICE_MIMES: dict[str, str] = {**IMAGE_MIMES, "application/pdf": "pdf"}

EXTENSIONS_ALLOWED: dict[str, set[str]] = {
    # Le PDF est accepte sur les tickets de caisse depuis que le scanner rend
    # un PDF pret a partir chez le comptable. Le refuser obligeait a deposer une
    # photo brute que la chaine reconvertissait ensuite.
    "expenses": {"png", "jpg", "jpeg", "pdf", "webp", "heic", "heif"},
    "invoices": {"png", "jpg", "jpeg", "pdf", "webp", "heic", "heif"},
    # Releve d'identite bancaire depose par le benevole : le document de sa
    # banque, en PDF le plus souvent, parfois photographie.
    "rib": {"png", "jpg", "jpeg", "pdf", "webp", "heic", "heif"},
}

# Signatures en TETE de fichier.
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"%PDF", "application/pdf"),
]

# Marques ISO-BMFF des variantes HEIF, aux octets 8 a 12 (juste apres « ftyp »).
_MARQUES_HEIF = (b"heic", b"heix", b"heim", b"heis", b"hevc", b"mif1", b"msf1")


def _detect_mime(prefix: bytes) -> str | None:
    """Type reel, deduit du contenu — jamais de l'extension ni de l'en-tete client.

    Deux formats ne se reconnaissent pas au premier octet, et une entree de plus
    dans `_MAGIC` ne les aurait pas attrapes :

    - **HEIC** est une boite ISO-BMFF : « ftyp » en 4-8, la marque en 8-12 ;
    - **WEBP** porte « RIFF » en 0-4 **et** « WEBP » en 8-12 — tester « RIFF »
      seul accepterait un WAV ou un AVI.
    """
    for sig, mime in _MAGIC:
        if prefix.startswith(sig):
            return mime

    if len(prefix) >= 12:
        if prefix[4:8] == b"ftyp" and prefix[8:12] in _MARQUES_HEIF:
            return "image/heic"
        if prefix[0:4] == b"RIFF" and prefix[8:12] == b"WEBP":
            return "image/webp"
    return None


def _ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _max_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024


def validate_file_type(
    filename: str,
    mime_from_client: str | None,
    head_bytes: bytes,
    *,
    allowed_subdir: str,
) -> tuple[str, str]:
    """Return (canonical_mime, canonical_extension) or raise AppException."""
    extension = _ext(filename)
    allowed_ext = EXTENSIONS_ALLOWED.get(allowed_subdir, set())
    if allowed_ext and extension not in allowed_ext:
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail=(
                f"Extension '{extension}' non autorisee "
                f"(attendu : {', '.join(sorted(allowed_ext))})."
            ),
            extras={"extension": extension, "allowed": sorted(allowed_ext)},
        )
    detected = _detect_mime(head_bytes)
    if detected is None:
        # Pas de repli sur ``mime_from_client`` : il est fourni par le client et
        # se falsifie trivialement. Un fichier arbitraire renomme en .jpg avec un
        # en-tete ``Content-Type: image/jpeg`` etait accepte tel quel.
        logger.warning(
            "Upload rejete : signature inconnue (fichier=%r, mime client=%r)",
            filename,
            mime_from_client,
        )
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail=(
                "Ce fichier n'est pas reconnu comme une photo ou un PDF. "
                "Deposez une photo (JPEG, PNG, HEIC, WEBP) ou un PDF, ou utilisez "
                "le bouton « Scanner » de l'application."
            ),
        )
    if allowed_subdir == "expenses" and detected not in INVOICE_MIMES:
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="Seules les images et PDF sont autorises pour les notes de frais.",
        )
    if allowed_subdir == "invoices" and detected not in INVOICE_MIMES:
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="Seules les images et PDF sont autorisees pour les factures.",
        )
    if allowed_subdir == "rib" and detected not in INVOICE_MIMES:
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="Le releve d'identite bancaire doit etre un PDF ou une image.",
        )
    canonical_ext = INVOICE_MIMES.get(detected, IMAGE_MIMES.get(detected, extension))
    return detected, canonical_ext


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_target_dir(subdir: str) -> Path:
    now = datetime.utcnow()
    target = settings.upload_path / subdir / f"{now.year:04d}" / f"{now.month:02d}"
    _ensure_directory(target)
    return target


async def save_upload_file(
    upload: UploadFile, subdir: str, *, convertir_en_pdf: bool = False
) -> dict[str, object]:
    """Persiste un depot sur disque apres validation. Retourne ses metadonnees.

    ``convertir_en_pdf`` : le contenu enregistre devient un PDF. Le PDF n'existait
    jusqu'ici que dans `OUTBOX_DIR`, pour la piece jointe du courriel, et le cron
    le purgeait a 30 jours ; ce qui restait en base et se retelechargeait depuis
    l'application etait l'image d'origine. D'ou l'ecart visible entre le scanner,
    qui rend deja un PDF, et un fichier choisi depuis le disque.

    Un parametre plutot qu'une fonction dediee facon `lire_en_memoire` : le cycle
    de vie est identique a celui d'un justificatif normal, seul le format change.
    Recopier la validation, l'ecriture par morceaux et le garde-fou de taille les
    ferait diverger.

    La conversion ne degrade rien : `img2pdf` embarque le flux JPEG tel quel.
    """
    if subdir not in EXTENSIONS_ALLOWED:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Sous-dossier d'upload inconnu."
        )

    head = await upload.read(1024)
    mime, ext = validate_file_type(
        upload.filename or "",
        upload.content_type,
        head,
        allowed_subdir=subdir,
    )

    target_dir = _build_target_dir(subdir)
    new_name = f"{uuid.uuid4().hex}.{ext}"
    target_path = target_dir / new_name

    total = len(head)
    max_bytes = _max_bytes()
    with open(target_path, "wb") as out:
        out.write(head)
        while True:
            chunk = await upload.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                try:
                    os.remove(target_path)
                except OSError:
                    pass
                raise AppException(
                    ErrorCode.FILE_TOO_LARGE,
                    detail=f"Fichier trop volumineux (> {settings.max_upload_mb} Mo).",
                    extras={"max_mb": settings.max_upload_mb},
                )
            out.write(chunk)

    # Contenu relu depuis le disque pour etre stocke EN BASE : c'est la seule
    # copie reellement sauvegardee (O2Switch sauvegarde la base, pas le disque
    # du VPS). L'ecriture disque est conservee comme cache local.
    #
    # Relecture plutot qu'accumulation en memoire pendant le transfert :
    # l'ecriture par morceaux ci-dessus protege des fichiers enormes, et la
    # taille est de toute facon bornee par MAX_UPLOAD_MB.
    contenu = target_path.read_bytes()
    nom_affiche = upload.filename or new_name

    if convertir_en_pdf:
        contenu, converti = pdf.octets_en_pdf(contenu)
        if converti:
            # Le fichier disque suit le contenu : sinon `contenu_du_fichier`
            # rendrait une image pour une ligne dont `type_fichier` annonce un
            # PDF, et `materialiser` donnerait cette image a `ensure_pdf`, qui
            # la reconvertirait.
            ancien = target_path
            target_path = target_dir / f"{Path(new_name).stem}.pdf"
            target_path.write_bytes(contenu)
            if ancien != target_path:
                ancien.unlink(missing_ok=True)

            mime = "application/pdf"
            total = len(contenu)
            nom_affiche = f"{Path(nom_affiche).stem}.pdf"
            logger.info("Justificatif converti en PDF : %s", target_path.name)

    return {
        "filename": nom_affiche,
        "stored_name": target_path.name,
        "path": str(target_path),
        "size": total,
        "mime": mime,
        "contenu": contenu,
    }


async def lire_en_memoire(upload: UploadFile, subdir: str) -> dict[str, object]:
    """Valide un fichier et rend son contenu, **sans jamais l'ecrire sur disque**.

    Pour ce qui ne vit qu'en base et n'a pas besoin de cache local : le releve
    d'identite bancaire, notamment. `save_upload_file` laisse une copie dans
    `uploads/`, utile pour un justificatif que la chaine comptable doit joindre
    a un courriel, inutile ici — et une copie de plus d'une donnee bancaire est
    une surface de fuite de plus.

    Meme validation que les autres depots : signature du contenu, extension
    autorisee, taille bornee par ``MAX_UPLOAD_MB``.
    """
    if subdir not in EXTENSIONS_ALLOWED:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Sous-dossier d'upload inconnu.")

    contenu = await upload.read(_max_bytes() + 1)
    if len(contenu) > _max_bytes():
        raise AppException(
            ErrorCode.FILE_TOO_LARGE,
            detail=f"Fichier trop volumineux (> {settings.max_upload_mb} Mo).",
            extras={"max_mb": settings.max_upload_mb},
        )
    if not contenu:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Fichier vide.")

    mime, _ext_canonique = validate_file_type(
        upload.filename or "",
        upload.content_type,
        contenu[:1024],
        allowed_subdir=subdir,
    )
    return {
        "filename": upload.filename or "document",
        "mime": mime,
        "size": len(contenu),
        "contenu": contenu,
    }


def _is_inside_uploads(candidate: Path) -> bool:
    """True si ``candidate`` est bien contenu dans le repertoire d'uploads.

    ``chemin_fichier`` provient de la base, mais la base n'est pas une source de
    confiance : ``POST /admin/database/import`` insere des lignes depuis un CSV
    fourni par l'utilisateur. Sans ce controle, un chemin arbitraire
    (``/home/user/backend/.env``) etait servi tel quel par ``FileResponse``.
    """
    try:
        root = settings.upload_path.resolve(strict=False)
        return candidate.resolve(strict=False).is_relative_to(root)
    except (OSError, ValueError):
        return False


def delete_file(path: str) -> bool:
    candidate = Path(path)
    if not _is_inside_uploads(candidate):
        logger.warning("Suppression refusee, chemin hors uploads : %s", path)
        return False
    try:
        os.remove(candidate)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("Impossible de supprimer %s : %s", path, exc)
        return False


def get_file_path(stored_path: str) -> Path | None:
    p = Path(stored_path)
    if not _is_inside_uploads(p):
        logger.warning("Acces refuse, chemin hors uploads : %s", stored_path)
        return None
    if p.exists() and p.is_file():
        return p
    return None


async def save_many(uploads: Iterable[UploadFile], subdir: str) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for upload in uploads:
        if upload is None or not upload.filename:
            continue
        results.append(await save_upload_file(upload, subdir))
    return results


# ---------------------------------------------------------------------------
# Lecture d'un justificatif
# ---------------------------------------------------------------------------


def contenu_du_fichier(file_row: object) -> bytes | None:
    """Octets d'un justificatif : la base d'abord, le disque en repli.

    La base fait autorite — c'est la seule copie sauvegardee. Le repli disque
    couvre les pieces deposees avant la migration, dont la colonne est vide, et
    disparaitra le jour ou plus aucune ligne ne sera dans ce cas.
    """
    contenu = getattr(file_row, "contenu", None)
    if contenu:
        return bytes(contenu)

    chemin = getattr(file_row, "chemin_fichier", None)
    if not chemin:
        return None
    fichier = get_file_path(str(chemin))
    return fichier.read_bytes() if fichier else None


def materialiser(file_row: object, *, dossier: Path) -> Path | None:
    """Rend le justificatif accessible SUR LE DISQUE, pour ce qui l'exige.

    La conversion en PDF et l'envoi en piece jointe travaillent sur des chemins.
    Si le fichier est deja la, on le sert tel quel ; s'il n'existe qu'en base —
    cas d'une restauration ou l'on n'aurait remonte que la base — on l'ecrit
    dans le repertoire indique.
    """
    chemin = getattr(file_row, "chemin_fichier", None)
    if chemin:
        existant = get_file_path(str(chemin))
        if existant:
            return existant

    contenu = getattr(file_row, "contenu", None)
    if not contenu:
        return None

    dossier.mkdir(parents=True, exist_ok=True)
    nom = Path(str(chemin)).name if chemin else f"{uuid.uuid4().hex}.bin"
    cible = dossier / nom
    cible.write_bytes(bytes(contenu))
    logger.info("Justificatif materialise depuis la base : %s", cible.name)
    return cible
