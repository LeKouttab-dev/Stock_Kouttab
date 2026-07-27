"""End-to-end tests for /admin database endpoints."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def test_database_status_as_super_admin(
    client: TestClient, super_admin_user, auth_headers
) -> None:
    resp = client.get(
        "/api/v1/admin/database/status", headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert "tables" in body
    assert "row_counts" in body


def test_database_export_streams_zip(
    client: TestClient, super_admin_user, auth_headers
) -> None:
    resp = client.post(
        "/api/v1/admin/database/export", headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    # Body looks like a zip (magic bytes "PK").
    assert resp.content[:2] == b"PK"


def test_database_import_without_confirm_returns_validation_error(
    client: TestClient, super_admin_user, auth_headers
) -> None:
    files = {"files": ("Stock.csv", io.BytesIO(b"id,nom\n"), "text/csv")}
    resp = client.post(
        "/api/v1/admin/database/import",
        files=files,
        headers=auth_headers(super_admin_user),
    )
    # confirm=False (default) -> ValidationError -> code VAL_5001 / status 422.
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "VAL_5001"


def test_database_import_with_confirm_processes_files(
    client: TestClient, super_admin_user, auth_headers
) -> None:
    # Provide a minimal valid Categories.csv (table = Categories, model = Category).
    csv_body = b"nom,is_default\nTestCatImport,0\n"
    files = {"files": ("Categories.csv", io.BytesIO(csv_body), "text/csv")}
    resp = client.post(
        "/api/v1/admin/database/import?confirm=true",
        files=files,
        headers=auth_headers(super_admin_user),
    )
    # Successful import returns 200 with a French message.
    assert resp.status_code == 200, resp.text
    assert "Import" in resp.json()["message"]
