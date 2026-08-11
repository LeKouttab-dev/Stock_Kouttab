"""Transitions de statut des factures et notes de frais."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.core.workflow import check_expense_transition, check_invoice_transition


pytestmark = pytest.mark.unit


# ---- Factures ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "new"),
    [
        ("En attente", "En cours de traitement"),
        ("En attente", "Validée"),
        ("En attente", "Refusée"),
        ("En cours de traitement", "Validée"),
        ("En cours de traitement", "En attente"),
        ("Refusée", "En attente"),
    ],
)
def test_invoice_allowed_transitions(current: str, new: str) -> None:
    check_invoice_transition(current, new)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        ("Validée", "En attente"),
        ("Validée", "Refusée"),
        ("Validée", "En cours de traitement"),
        ("Refusée", "Validée"),
    ],
)
def test_invoice_forbidden_transitions(current: str, new: str) -> None:
    with pytest.raises(AppException):
        check_invoice_transition(current, new)


def test_invoice_same_status_is_a_noop() -> None:
    """Reenregistrer le meme statut ne doit pas lever."""
    check_invoice_transition("Validée", "Validée")


def test_unknown_current_status_is_tolerated() -> None:
    """Une ligne legacy au statut inconnu ne doit pas bloquer l'utilisateur."""
    check_invoice_transition("Statut historique bizarre", "Validée")


# ---- Notes de frais ---------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "new"),
    [
        ("En attente", "Approuvée"),
        ("En attente", "Refusée"),
        ("Approuvée", "Remboursée"),
        ("Approuvée", "En attente"),
        ("Refusée", "En attente"),
    ],
)
def test_expense_allowed_transitions(current: str, new: str) -> None:
    check_expense_transition(current, new)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        # Le virement est parti : on ne revient pas en arriere.
        ("Remboursée", "En attente"),
        ("Remboursée", "Approuvée"),
        ("Remboursée", "Refusée"),
        # On ne rembourse pas une note jamais approuvee.
        ("En attente", "Remboursée"),
        ("Refusée", "Remboursée"),
    ],
)
def test_expense_forbidden_transitions(current: str, new: str) -> None:
    with pytest.raises(AppException):
        check_expense_transition(current, new)
