"""Scan de justificatifs : detection des bords puis redressement.

Deux routes, pour les deux temps du scanner cote client :

- ``POST /scan/detect`` rend les quatre coins proposes, que l'ecran affiche en
  surimpression sur la photo.
- ``POST /scan/apply`` rend l'image redressee, cadree sur le seul document.

Le decoupage en deux appels laisse le deposant corriger un cadrage errone avant
que le fichier ne parte au comptable. Cf. ``app.services.document_scan``.

Le resultat est une image : la conversion en PDF et la nomenclature comptable
restent dans le flux de depot existant (``services/pdf.py``, ``services/
naming.py``), pour que le fichier scanne suive exactement le meme chemin qu'un
fichier televerse.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Admin
from app.schemas.scan import ScanDetectOut
from app.services.document_scan import detect_document_quad, scan_document
from app.services.pdf import image_bytes_to_pdf


logger = get_logger("api.scan")
router = APIRouter(prefix="/scan", tags=["scan"])


_ACCEPTED_TYPES = {"image/jpeg", "image/jpg", "image/png"}


async def _read_image(file: UploadFile) -> bytes:
    if file.content_type not in _ACCEPTED_TYPES:
        raise AppException(
            ErrorCode.INVALID_FILE_TYPE,
            detail="Le scan accepte une photo JPEG ou PNG.",
        )
    content = await file.read()
    # La limite d'upload s'applique ici aussi : une photo de 12 Mpx pese 5 Mo,
    # et rien n'oblige un client a respecter la contrainte cote navigateur.
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise AppException(
            ErrorCode.FILE_TOO_LARGE,
            detail=f"Photo trop lourde (max {settings.max_upload_mb} Mo).",
        )
    if not content:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Photo vide.")
    return content


@router.post("/detect", response_model=ScanDetectOut)
async def detect(
    file: UploadFile = File(...),
    _: Admin = Depends(get_current_user),
) -> Any:
    """Propose un cadrage. ``corners`` vaut ``null`` si rien ne se detache."""
    content = await _read_image(file)
    quad = detect_document_quad(content)
    return ScanDetectOut(
        detected=quad is not None,
        corners=[{"x": x, "y": y} for x, y in quad] if quad else None,
    )


@router.post("/apply")
async def apply(
    file: UploadFile = File(...),
    corners: str | None = Form(default=None),
    enhance: bool = Form(default=True),
    output: str = Form(default="pdf"),
    _: Admin = Depends(get_current_user),
) -> Response:
    """Rend le document redresse, en PDF par defaut.

    ``corners`` : JSON ``[{"x": .., "y": ..} x4]`` en pixels de la photo
    d'origine. Absent, la detection automatique s'applique.

    ``output`` : ``pdf`` (defaut) ou ``jpeg``. Le PDF est ce qui part chez le
    comptable ; le JPEG ne sert qu'a afficher un apercu.
    """
    content = await _read_image(file)

    quad = None
    if corners:
        try:
            points = json.loads(corners)
            quad = [(float(p["x"]), float(p["y"])) for p in points]
        except (ValueError, TypeError, KeyError) as exc:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                detail="Cadrage invalide : attendu une liste de 4 points {x, y}.",
            ) from exc
        if len(quad) != 4:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                detail="Cadrage invalide : il faut exactement 4 points.",
            )

    scanned = scan_document(content, quad=quad, enhance=enhance)

    if output.lower() == "jpeg":
        logger.info("Scan applique (apercu JPEG) : %d octets", len(scanned))
        return Response(content=scanned, media_type="image/jpeg")

    pdf_bytes = image_bytes_to_pdf(scanned)
    logger.info(
        "Scan applique : %d octets en entree, %d en PDF", len(content), len(pdf_bytes)
    )
    return Response(content=pdf_bytes, media_type="application/pdf")
