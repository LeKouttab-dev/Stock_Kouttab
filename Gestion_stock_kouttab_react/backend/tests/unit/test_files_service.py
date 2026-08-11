"""Securite du service d'upload : validation de type et confinement des chemins.

``app/services/files.py`` n'avait aucun test alors qu'il porte la validation de
tout ce qui entre sur le disque et sort vers les telechargements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import files as files_service


pytestmark = pytest.mark.unit


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PDF_HEADER = b"%PDF-1.7\n" + b"\x00" * 32


# ---- Validation de type -----------------------------------------------------


def test_accepts_png_for_expenses() -> None:
    mime, ext = files_service.validate_file_type(
        "ticket.png", "image/png", PNG_HEADER, allowed_subdir="expenses"
    )
    assert (mime, ext) == ("image/png", "png")


def test_accepts_pdf_for_invoices() -> None:
    mime, ext = files_service.validate_file_type(
        "facture.pdf", "application/pdf", PDF_HEADER, allowed_subdir="invoices"
    )
    assert (mime, ext) == ("application/pdf", "pdf")


def test_accepts_pdf_for_expenses() -> None:
    """Les notes de frais acceptent le PDF depuis l'arrivee du scanner.

    Le scanner rend un PDF pret a partir chez le comptable ; le refuser
    obligeait le deposant a joindre une photo brute, que la chaine comptable
    reconvertissait ensuite.
    """
    mime, ext = files_service.validate_file_type(
        "ticket.pdf", "application/pdf", PDF_HEADER, allowed_subdir="expenses"
    )
    assert (mime, ext) == ("application/pdf", "pdf")


def test_rejects_disallowed_extension() -> None:
    with pytest.raises(AppException):
        files_service.validate_file_type(
            "payload.exe", "application/pdf", PDF_HEADER, allowed_subdir="invoices"
        )


def test_does_not_trust_the_client_content_type() -> None:
    """Le coeur du correctif : un contenu arbitraire annonce comme JPEG.

    L'extension est autorisee et l'en-tete ``Content-Type`` est credible, mais
    les octets ne correspondent a aucune signature connue. Le fichier doit etre
    refuse, alors qu'il etait auparavant accepte sur la foi du seul en-tete.
    """
    payload = b"<?php system($_GET['c']); ?>" + b"\x00" * 32
    with pytest.raises(AppException):
        files_service.validate_file_type(
            "innocent.jpg", "image/jpeg", payload, allowed_subdir="invoices"
        )


def test_extension_mismatch_still_uses_the_real_signature() -> None:
    """Un PDF renomme en .jpg est stocke selon son vrai type."""
    mime, ext = files_service.validate_file_type(
        "facture.jpg", "image/jpeg", PDF_HEADER, allowed_subdir="invoices"
    )
    assert (mime, ext) == ("application/pdf", "pdf")


def test_webp_is_no_longer_accepted() -> None:
    """WEBP etait accepte cote MIME mais jamais cote extension."""
    riff_webp = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16
    with pytest.raises(AppException):
        files_service.validate_file_type(
            "photo.jpg", "image/webp", riff_webp, allowed_subdir="invoices"
        )


# ---- Confinement des chemins ------------------------------------------------


def test_get_file_path_refuses_a_path_outside_uploads(tmp_path: Path) -> None:
    """Chemin arbitraire en base -> aucun fichier servi.

    Scenario reel : ``POST /admin/database/import`` insere des lignes
    ``FichiersFactures`` depuis un CSV fourni par l'utilisateur, avec un
    ``chemin_fichier`` libre. Sans confinement, le fichier vise etait renvoye
    tel quel par ``FileResponse``.
    """
    outsider = tmp_path / "secrets.env"
    outsider.write_text("JWT_SECRET_KEY=leaked", encoding="utf-8")
    assert files_service.get_file_path(str(outsider)) is None


def test_get_file_path_refuses_traversal_from_uploads() -> None:
    traversal = str(settings.upload_path / ".." / ".." / ".env")
    assert files_service.get_file_path(traversal) is None


def test_get_file_path_accepts_a_file_inside_uploads() -> None:
    target = settings.upload_path / "invoices" / "unit-test-sample.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(PDF_HEADER)
    try:
        assert files_service.get_file_path(str(target)) == target
    finally:
        target.unlink(missing_ok=True)


def test_get_file_path_returns_none_for_a_missing_file() -> None:
    missing = settings.upload_path / "invoices" / "does-not-exist.pdf"
    assert files_service.get_file_path(str(missing)) is None


def test_delete_file_refuses_a_path_outside_uploads(tmp_path: Path) -> None:
    outsider = tmp_path / "important.txt"
    outsider.write_text("ne pas supprimer", encoding="utf-8")
    assert files_service.delete_file(str(outsider)) is False
    assert outsider.exists(), "le fichier hors uploads ne doit pas etre supprime"
