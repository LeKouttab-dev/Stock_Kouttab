"""Ce qui attend l'utilisateur connecte, en un seul appel.

Sert deux usages du meme chiffre : la pastille posee sur l'entree de menu, et
le rappel affiche a la connexion. Un endpoint plutot que des comptages faits
cote client, parce que ces derniers auraient impose de telecharger les listes
completes de notes et de factures a chaque chargement de page — pour n'en
afficher qu'un nombre.

Chaque compteur est **filtre par les droits du demandeur** : un benevole
n'apprend pas combien de comptes attendent une validation. Le compteur vaut 0,
comme s'il n'y avait rien, et non l'information masquee a l'affichage.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Admin, Expense, Invoice, Stock, StockModification
from app.db.session import get_db
from app.schemas.notification import PendingSummaryOut


router = APIRouter(prefix="/notifications", tags=["notifications"])


_ACCOUNTANT_ROLES = {"Compta", "Super Admin"}
_STOCK_ADMIN_ROLES = {"AdminBenevoles", "Super Admin"}

# Statuts qui demandent encore une action de la comptabilite. « En cours de
# traitement » en fait partie : la facture est prise en main, pas encore soldee.
_FACTURES_A_TRAITER = ("En attente", "En cours de traitement")


def _compter(db: Session, modele: Any, condition: Any) -> int:
    return int(
        db.execute(select(func.count()).select_from(modele).where(condition)).scalar_one()
    )


@router.get("/summary", response_model=PendingSummaryOut)
def pending_summary(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Nombre de dossiers en attente, selon ce que le demandeur peut traiter."""
    est_comptable = current_user.role in _ACCOUNTANT_ROLES
    est_admin_stock = current_user.role in _STOCK_ADMIN_ROLES
    est_super_admin = current_user.role == "Super Admin"

    return PendingSummaryOut(
        notes_a_valider=(
            _compter(db, Expense, Expense.status == "En attente") if est_comptable else 0
        ),
        factures_a_traiter=(
            _compter(db, Invoice, Invoice.status.in_(_FACTURES_A_TRAITER))
            if est_comptable
            else 0
        ),
        modifications_stock=(
            _compter(db, StockModification, StockModification.status == "En attente")
            if est_admin_stock
            else 0
        ),
        comptes_a_valider=(
            _compter(db, Admin, Admin.validation_status == "pending")
            if est_super_admin
            else 0
        ),
        articles_en_alerte=(
            _compter(db, Stock, Stock.quantite < Stock.seuil_alerte)
            if est_admin_stock
            else 0
        ),
    )
