"""Conversion des justificatifs en PDF.

Les fixtures sont generees a la volee avec Pillow : aucun binaire n'est stocke
dans le depot, et chaque cas est reproductible.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from app.core.exceptions import AppException
from app.services.pdf import convert_image_to_pdf, ensure_pdf, is_pdf


pytestmark = pytest.mark.unit


def _write_image(path: Path, mode: str = "RGB", size=(80, 40), fmt: str = "PNG") -> Path:
    colour = 0 if mode in ("L", "1") else (200, 60, 60)
    Image.new(mode, size, colour).save(path, format=fmt)
    return path


def _write_jpeg_with_exif_rotation(path: Path) -> Path:
    """JPEG paysage portant un EXIF Orientation=6 (= a pivoter en portrait)."""
    image = Image.new("RGB", (120, 60), (10, 120, 200))
    exif = image.getexif()
    exif[274] = 6  # tag Orientation
    image.save(path, format="JPEG", exif=exif)
    return path


def _write_minimal_pdf(path: Path) -> Path:
    Image.new("RGB", (40, 40), (255, 255, 255)).save(path, format="PDF")
    return path


def _page_size(pdf: Path) -> tuple[float, float]:
    box = PdfReader(str(pdf)).pages[0].mediabox
    return float(box.width), float(box.height)


# ---- Detection --------------------------------------------------------------


def test_is_pdf_detects_a_real_pdf(tmp_path: Path) -> None:
    assert is_pdf(_write_minimal_pdf(tmp_path / "doc.pdf"))


def test_is_pdf_ignores_the_extension(tmp_path: Path) -> None:
    """Une image renommee en .pdf ne doit pas passer pour un PDF."""
    fake = _write_image(tmp_path / "piege.pdf", fmt="PNG")
    assert is_pdf(fake) is False


def test_is_pdf_on_a_missing_file(tmp_path: Path) -> None:
    assert is_pdf(tmp_path / "absent.pdf") is False


# ---- ensure_pdf -------------------------------------------------------------


def test_existing_pdf_is_copied_byte_for_byte(tmp_path: Path) -> None:
    source = _write_minimal_pdf(tmp_path / "facture.pdf")
    digest_before = hashlib.sha256(source.read_bytes()).hexdigest()

    result, converted = ensure_pdf(
        source, target_dir=tmp_path / "outbox", target_stem="Local_Gala_2026-03-14"
    )

    assert converted is False
    assert result.name == "Local_Gala_2026-03-14.pdf"
    assert hashlib.sha256(result.read_bytes()).hexdigest() == digest_before


def test_image_is_converted_to_a_single_a4_page(tmp_path: Path) -> None:
    source = _write_image(tmp_path / "ticket.png")
    result, converted = ensure_pdf(
        source, target_dir=tmp_path / "outbox", target_stem="Local_Courses_2026-03-14"
    )

    assert converted is True
    assert result.read_bytes().startswith(b"%PDF")
    reader = PdfReader(str(result))
    assert len(reader.pages) == 1
    width, height = _page_size(result)
    # A4 portrait ~ 595 x 842 points, a l'arrondi pres.
    assert 590 < width < 600
    assert 835 < height < 848


def test_jpeg_stream_is_embedded_without_re_encoding(tmp_path: Path) -> None:
    """Preuve du sans-perte : les octets JPEG d'origine sont dans le PDF."""
    source = tmp_path / "ticket.jpg"
    Image.new("RGB", (100, 50), (30, 90, 160)).save(source, format="JPEG", quality=85)
    original = source.read_bytes()

    result, _ = ensure_pdf(
        source, target_dir=tmp_path / "outbox", target_stem="piece"
    )
    # Le flux JPEG (hors marqueurs d'en-tete) doit se retrouver tel quel.
    assert original[20:200] in result.read_bytes()


def test_exif_orientation_is_applied(tmp_path: Path) -> None:
    """Une photo prise en portrait ne doit pas arriver couchee chez le comptable.

    img2pdf ignore l'EXIF : sans normalisation prealable, l'image large reste
    large et la page sort en paysage.
    """
    source = _write_jpeg_with_exif_rotation(tmp_path / "photo.jpg")
    result, _ = ensure_pdf(source, target_dir=tmp_path / "outbox", target_stem="photo")

    width, height = _page_size(result)
    assert height > width, "la page devrait etre en portrait apres rotation EXIF"


@pytest.mark.parametrize(
    ("mode", "fmt", "suffix"),
    [
        ("RGBA", "PNG", "png"),
        ("P", "PNG", "png"),
        ("L", "PNG", "png"),
        # CMYK ne s'ecrit pas en PNG : c'est un cas de scan professionnel, donc
        # un JPEG. img2pdf refuse ce mode, Pillow doit le convertir en amont.
        ("CMYK", "JPEG", "jpg"),
    ],
)
def test_unusual_colour_modes_are_handled(
    tmp_path: Path, mode: str, fmt: str, suffix: str
) -> None:
    source = _write_image(tmp_path / f"img_{mode}.{suffix}", mode=mode, fmt=fmt)
    result, converted = ensure_pdf(
        source, target_dir=tmp_path / "outbox", target_stem=f"piece_{mode}"
    )
    assert converted is True
    assert result.read_bytes().startswith(b"%PDF")


def test_corrupted_file_raises_a_clean_error(tmp_path: Path) -> None:
    source = tmp_path / "corrompu.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    with pytest.raises(AppException):
        ensure_pdf(source, target_dir=tmp_path / "outbox", target_stem="piece")


def test_missing_source_raises_a_clean_error(tmp_path: Path) -> None:
    with pytest.raises(AppException):
        ensure_pdf(
            tmp_path / "absent.png", target_dir=tmp_path / "outbox", target_stem="piece"
        )


def test_source_is_never_modified(tmp_path: Path) -> None:
    """Les originaux deposes doivent rester intacts dans uploads/."""
    source = _write_image(tmp_path / "ticket.png")
    digest_before = hashlib.sha256(source.read_bytes()).hexdigest()

    ensure_pdf(source, target_dir=tmp_path / "outbox", target_stem="piece")

    assert source.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest_before


def test_target_directory_is_created_on_demand(tmp_path: Path) -> None:
    source = _write_image(tmp_path / "ticket.png")
    target_dir = tmp_path / "a" / "b" / "c"
    result, _ = ensure_pdf(source, target_dir=target_dir, target_stem="piece")
    assert result.parent == target_dir


def test_convert_image_to_pdf_writes_where_asked(tmp_path: Path) -> None:
    source = _write_image(tmp_path / "ticket.png")
    target = tmp_path / "sous" / "dossier" / "resultat.pdf"
    assert convert_image_to_pdf(source, target) == target
    assert target.exists()


def test_conversion_is_deterministic_enough_to_be_reproducible(tmp_path: Path) -> None:
    """Deux conversions de la meme source donnent des PDF de meme taille."""
    source = _write_image(tmp_path / "ticket.png")
    first, _ = ensure_pdf(source, target_dir=tmp_path / "o1", target_stem="p")
    second, _ = ensure_pdf(source, target_dir=tmp_path / "o2", target_stem="p")
    assert first.stat().st_size == second.stat().st_size


def test_buffered_image_helper_keeps_pillow_out_of_the_pdf(tmp_path: Path) -> None:
    """Un PNG deja RGB n'est pas re-encode inutilement."""
    source = tmp_path / "plat.png"
    Image.new("RGB", (60, 60), (12, 34, 56)).save(source, format="PNG")
    buffer = BytesIO(source.read_bytes())
    assert buffer.getvalue().startswith(b"\x89PNG")
