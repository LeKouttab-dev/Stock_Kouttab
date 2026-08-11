"""Unit tests for app.crud.invoice."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.crud import invoice as invoice_crud
from app.crud import user as user_crud


pytestmark = pytest.mark.unit


def _make_user(db, *, role: str = "Benevole"):
    name = f"u{uuid.uuid4().hex[:8]}"
    return user_crud.create_user(
        db,
        username=name,
        password="Strong#Pass1",
        role=role,
        email=f"{name}@example.com",
    )


def test_create_invoice_then_attach_file(db_session) -> None:
    user = _make_user(db_session)
    invoice = invoice_crud.create_invoice(
        db_session,
        user_id=user.id,
        commentaire="Test facture",
        date_depot=date(2024, 3, 1),
    )
    assert invoice.id > 0
    assert invoice.status == "En attente"

    f = invoice_crud.attach_file(
        db_session,
        invoice_id=invoice.id,
        nom_fichier="facture.pdf",
        chemin_fichier="/tmp/facture.pdf",
        taille_fichier=2048,
        type_fichier="application/pdf",
    )
    assert f.id > 0
    assert f.id_facture == invoice.id


def test_update_status_changes_value(db_session) -> None:
    user = _make_user(db_session)
    invoice = invoice_crud.create_invoice(
        db_session, user_id=user.id, commentaire=None, date_depot=None
    )
    updated = invoice_crud.update_status(db_session, invoice.id, "Validée")
    assert updated.status == "Validée"


def test_list_invoices_with_status_filter(db_session) -> None:
    user = _make_user(db_session)
    inv1 = invoice_crud.create_invoice(
        db_session, user_id=user.id, commentaire="a", date_depot=None
    )
    inv2 = invoice_crud.create_invoice(
        db_session, user_id=user.id, commentaire="b", date_depot=None
    )
    invoice_crud.update_status(db_session, inv2.id, "Validée")

    pending = invoice_crud.list_invoices(db_session, status="En attente")
    validated = invoice_crud.list_invoices(db_session, status="Validée")
    pending_ids = [r["id"] for r in pending]
    validated_ids = [r["id"] for r in validated]
    assert inv1.id in pending_ids
    assert inv2.id in validated_ids


def test_delete_invoice_via_orm(db_session) -> None:
    user = _make_user(db_session)
    invoice = invoice_crud.create_invoice(
        db_session, user_id=user.id, commentaire=None, date_depot=None
    )
    invoice_id = invoice.id
    db_session.delete(invoice)
    db_session.commit()
    assert invoice_crud.get_invoice(db_session, invoice_id) is None
