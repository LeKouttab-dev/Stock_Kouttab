"""Unit tests for app.crud.expense."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppException
from app.crud import expense as expense_crud
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


def _create_expense(db, user, *, status: str | None = None):
    expense = expense_crud.create_expense(
        db,
        user_id=user.id,
        date_depense=date(2024, 1, 15),
        rattachement="Cuisine",
        fournisseur="Carrefour",
        nature_charge="Achat",
        montant=Decimal("12.34"),
        commentaires=None,
        remboursement_deja_emis=Decimal("0"),
        remise=Decimal("0"),
    )
    if status and status != "En attente":
        expense.status = status
        db.commit()
        db.refresh(expense)
    return expense


def test_create_expense_then_attach_file(db_session) -> None:
    user = _make_user(db_session)
    expense = _create_expense(db_session, user)
    assert expense.id > 0
    assert expense.status == "En attente"

    f = expense_crud.attach_file(
        db_session,
        expense_id=expense.id,
        nom_fichier="ticket.png",
        chemin_fichier="/tmp/ticket.png",
        taille_fichier=1234,
        type_fichier="image/png",
    )
    assert f.id > 0
    assert f.id_note_de_frais == expense.id


def test_get_my_expenses_filtered_by_user(db_session) -> None:
    u1 = _make_user(db_session)
    u2 = _make_user(db_session)
    _create_expense(db_session, u1)
    _create_expense(db_session, u1)
    _create_expense(db_session, u2)

    own = expense_crud.list_expenses_for_user(db_session, u1.id)
    assert len(own) == 2
    other = expense_crud.list_expenses_for_user(db_session, u2.id)
    assert len(other) == 1


def test_update_by_owner_when_pending_works(db_session) -> None:
    user = _make_user(db_session)
    expense = _create_expense(db_session, user)
    updated = expense_crud.update_expense_details(
        db_session,
        expense.id,
        user_id=user.id,
        role=user.role,
        montant=Decimal("99.99"),
    )
    assert updated.montant == Decimal("99.99")


def test_update_blocked_when_status_not_pending(db_session) -> None:
    user = _make_user(db_session)
    expense = _create_expense(db_session, user, status="Approuvée")
    with pytest.raises(AppException) as exc_info:
        expense_crud.update_expense_details(
            db_session,
            expense.id,
            user_id=user.id,
            role=user.role,
            montant=Decimal("1.00"),
        )
    assert exc_info.value.code_value == "CONF_4005"  # EXPENSE_NOT_EDITABLE


def test_validate_by_accountant_changes_status_and_comment(db_session) -> None:
    user = _make_user(db_session)
    expense = _create_expense(db_session, user)
    validated = expense_crud.validate_expense(
        db_session,
        expense.id,
        new_status="Approuvée",
        comment="OK pour moi.",
    )
    assert validated.status == "Approuvée"
    assert validated.commentaires_compta == "OK pour moi."


def test_archive_blocked_when_status_not_remboursee(db_session) -> None:
    """Ranger une note en cours de traitement la sortirait des listes alors que
    le benevole attend encore son argent."""
    user = _make_user(db_session)
    comptable = _make_user(db_session, role="Compta")
    expense = _create_expense(db_session, user, status="Approuvée")
    with pytest.raises(AppException) as exc_info:
        expense_crud.archive_expense(db_session, expense.id, user=comptable)
    assert exc_info.value.code_value == "CONF_4006"  # EXPENSE_NOT_DELETABLE
