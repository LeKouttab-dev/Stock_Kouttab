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


# (mime, extension) whitelist
IMAGE_MIMES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}
INVOICE_MIMES: dict[str, str] = {**IMAGE_MIMES, "application/pdf": "pdf"}

EXTENSIONS_ALLOWED: dict[str, set[str]] = {
    "expenses": {"png", "jpg", "jpeg"},
    "invoices": {"png", "jpg", "jpeg", "pdf"},
}

# Magic byte signatures (read first bytes from file).
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"%PDF", "application/pdf"),
    (b"RIFF", "image/webp"),  # WEBP files start with RIFF then ...WEBP
]


def _detect_mime(prefix: bytes) -> str | None:
    for sig, mime in _MAGIC:
        if prefix.startswith(sig):
            if mime == "image/webp" and b"WEBP" not in prefix[:16]:
                continue
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
        # Some browsers send valid JPEG without our extra signature variants — fall
        # back to the client mime if at least it is in the whitelist.
        if mime_from_client in INVOICE_MIMES:
            detected = mime_from_client
        else:
            raise AppException(
                ErrorCode.INVALID_FILE_TYPE, detail="Type de fichier non reconnu."
            )
    if allowed_subdir == "expenses" and detected not in IMAGE_MIMES:
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="Seules les images sont autorisees pour les notes de frais.",
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


def delete_file(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("Impossible de supprimer %s : %s", path, exc)
        return False


def get_file_path(stored_path: str) -> Path | None:
    p = Path(stored_path)
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
