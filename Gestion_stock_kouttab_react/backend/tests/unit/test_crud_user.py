"""Unit tests for app.crud.user."""

from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import AppException
from app.crud import user as user_crud


pytestmark = pytest.mark.unit


def _u(prefix: str = "u") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def test_create_pending_user_status_pending(db_session) -> None:
    name = _u("p")
    user = user_crud.create_pending_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Benevole",
        email=f"{name}@example.com",
    )
    assert user.id > 0
    assert user.validation_status == "pending"
    assert user.role == "Benevole"


def test_get_user_by_username_found_and_not_found(db_session) -> None:
    name = _u("g")
    user_crud.create_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Benevole",
        email=f"{name}@example.com",
    )
    found = user_crud.get_user_by_username(db_session, name)
    assert found is not None
    assert found.username == name

    assert user_crud.get_user_by_username(db_session, "nope_does_not_exist") is None


def test_update_validation_status_pending_to_active(db_session) -> None:
    name = _u("v")
    user = user_crud.create_pending_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Benevole",
        email=f"{name}@example.com",
    )
    assert user.validation_status == "pending"
    updated = user_crud.update_validation_status(db_session, user.id, "active")
    assert updated.validation_status == "active"


def test_update_user_role_changes_role(db_session) -> None:
    name = _u("r")
    user = user_crud.create_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Benevole",
        email=f"{name}@example.com",
    )
    updated = user_crud.update_role(db_session, user.id, "Compta")
    assert updated.role == "Compta"


def test_delete_user_removes_it(db_session) -> None:
    name = _u("d")
    user = user_crud.create_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Benevole",
        email=f"{name}@example.com",
    )
    user_crud.delete_user(db_session, user.id)
    assert user_crud.get_user(db_session, user.id) is None


def test_create_user_direct_is_active_by_default(db_session) -> None:
    name = _u("a")
    user = user_crud.create_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Super Admin",
        email=f"{name}@example.com",
    )
    assert user.validation_status == "active"
    assert user.role == "Super Admin"


def test_create_user_with_duplicate_username_raises(db_session) -> None:
    name = _u("dup")
    user_crud.create_user(
        db_session,
        username=name,
        password="Strong#Pass1",
        role="Benevole",
        email=f"{name}@example.com",
    )
    with pytest.raises(AppException) as exc_info:
        user_crud.create_user(
            db_session,
            username=name,
            password="Strong#Pass1",
            role="Benevole",
            email=f"{name}-2@example.com",
        )
    assert exc_info.value.code_value == "AUTH_1023"  # USERNAME_TAKEN
