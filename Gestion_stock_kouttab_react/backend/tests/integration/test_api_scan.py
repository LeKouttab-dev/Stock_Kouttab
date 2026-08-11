"""Tests des routes /scan."""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest


pytestmark = pytest.mark.integration


def _photo(taille: tuple[int, int] = (900, 700)) -> bytes:
    """Feuille blanche de travers sur fond sombre, comme une photo a main levee."""
    largeur, hauteur = taille
    fond = np.full((hauteur, largeur, 3), 40, dtype=np.uint8)
    quad = np.array([(140, 90), (760, 150), (720, 610), (180, 540)], dtype=np.int32)
    cv2.fillConvexPoly(fond, quad, (245, 245, 245))
    for i in range(5):
        y = 180 + i * 60
        cv2.line(fond, (240, y), (640, y), (30, 30, 30), 6)
    ok, encoded = cv2.imencode(".jpg", fond)
    assert ok
    return encoded.tobytes()


def test_detect_rend_quatre_coins(client_authenticated_as, benevole_user) -> None:
    client = client_authenticated_as(benevole_user)

    response = client.post(
        "/api/v1/scan/detect",
        files={"file": ("ticket.jpg", _photo(), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["detected"] is True
    assert len(body["corners"]) == 4
    assert all({"x", "y"} == set(c) for c in body["corners"])


def test_detect_exige_une_authentification(client) -> None:
    response = client.post(
        "/api/v1/scan/detect",
        files={"file": ("ticket.jpg", _photo(), "image/jpeg")},
    )
    assert response.status_code == 401


def test_detect_refuse_un_pdf(client_authenticated_as, benevole_user) -> None:
    client = client_authenticated_as(benevole_user)

    response = client.post(
        "/api/v1/scan/detect",
        files={"file": ("facture.pdf", b"%PDF-1.4 ...", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json()["code"] == "VAL_5006"


def test_apply_rend_un_pdf_par_defaut(client_authenticated_as, benevole_user) -> None:
    """Le scan produit directement la piece comptable, pas une photo."""
    client = client_authenticated_as(benevole_user)

    response = client.post(
        "/api/v1/scan/apply",
        files={"file": ("ticket.jpg", _photo(), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_apply_rend_une_image_recadree(client_authenticated_as, benevole_user) -> None:
    client = client_authenticated_as(benevole_user)
    photo = _photo()

    response = client.post(
        "/api/v1/scan/apply",
        files={"file": ("ticket.jpg", photo, "image/jpeg")},
        data={"output": "jpeg"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    decode = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_GRAYSCALE)
    # Le fond sombre a disparu : l'image ne porte plus que la feuille.
    assert decode.shape[1] < 900
    assert decode.mean() > 120


def test_apply_respecte_un_cadrage_manuel(client_authenticated_as, benevole_user) -> None:
    client = client_authenticated_as(benevole_user)
    corners = [
        {"x": 100, "y": 100},
        {"x": 300, "y": 100},
        {"x": 300, "y": 250},
        {"x": 100, "y": 250},
    ]

    response = client.post(
        "/api/v1/scan/apply",
        files={"file": ("ticket.jpg", _photo(), "image/jpeg")},
        data={"corners": json.dumps(corners), "enhance": "false", "output": "jpeg"},
    )

    assert response.status_code == 200
    decode = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    hauteur, largeur = decode.shape[:2]
    assert abs(largeur - 200) <= 2
    assert abs(hauteur - 150) <= 2


def test_apply_refuse_un_cadrage_incomplet(client_authenticated_as, benevole_user) -> None:
    client = client_authenticated_as(benevole_user)

    response = client.post(
        "/api/v1/scan/apply",
        files={"file": ("ticket.jpg", _photo(), "image/jpeg")},
        data={"corners": json.dumps([{"x": 1, "y": 2}, {"x": 3, "y": 4}])},
    )

    assert response.status_code == 422
