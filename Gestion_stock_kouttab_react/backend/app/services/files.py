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


logger = get_logger("files")


# (mime, extension) whitelist.
# NB : ``image/webp`` a ete retire — il etait accepte ici alors que l'extension
# ``webp`` n'a jamais figure dans EXTENSIONS_ALLOWED. Un fichier WEBP renomme en
# .jpg passait donc la validation de type puis etait stocke en .webp, hors du
# jeu d'extensions autorisees.
IMAGE_MIMES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}
INVOICE_MIMES: dict[str, str] = {**IMAGE_MIMES, "application/pdf": "pdf"}

EXTENSIONS_ALLOWED: dict[str, set[str]] = {
    # Le PDF est accepte sur les tickets de caisse depuis que le scanner rend
    # un PDF pret a partir chez le comptable. Le refuser obligeait a deposer une
    # photo brute que la chaine reconvertissait ensuite.
    "expenses": {"png", "jpg", "jpeg", "pdf"},
    "invoices": {"png", "jpg", "jpeg", "pdf"},
}

# Magic byte signatures (read first bytes from file).
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"%PDF", "application/pdf"),
]


def _detect_mime(prefix: bytes) -> str | None:
    for sig, mime in _MAGIC:
        if prefix.startswith(sig):
            return mime
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
            ErrorCode.INVALID_FILE_TYPE, detail="Type de fichier non reconnu."
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
    canonical_ext = INVOICE_MIMES.get(detected, IMAGE_MIMES.get(detected, extension))
    return detected, canonical_ext


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_target_dir(subdir: str) -> Path:
    now = datetime.utcnow()
    target = settings.upload_path / subdir / f"{now.year:04d}" / f"{now.month:02d}"
    _ensure_directory(target)
    return target


async def save_upload_file(upload: UploadFile, subdir: str) -> dict[str, object]:
    """Persist a single upload to disk after validation. Returns metadata."""
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

    logger.info("Fichier sauvegarde : %s (%d octets)", target_path, total)
    return {
        "filename": upload.filename or new_name,
        "stored_name": new_name,
        "path": str(target_path),
        "size": total,
        "mime": mime,
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
