"""Expense (notes de frais) CRUD."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.workflow import check_expense_transition
from app.db.models import Expense, ExpenseFile


def _serialize(expense: Expense) -> dict[str, Any]:
    user = expense.user
    return {
        "id": expense.id,
        "id_user": expense.id_user,
        "date_depense": expense.date_depense,
        "rattachement": expense.rattachement,
        "id_pole": expense.id_pole,
        "pole": expense.pole,
        "id_event": expense.id_event,
        "evenement": expense.evenement,
        "date_evenement": expense.date_evenement,
        "fournisseur": expense.fournisseur,
        "nature_charge": expense.nature_charge,
        "montant": expense.montant,
        "commentaires": expense.commentaires,
        "remboursement_deja_emis": expense.remboursement_deja_emis,
        "remise": expense.remise,
        "status": expense.status,
        "commentaires_compta": expense.commentaires_compta,
        "validated_by": expense.validated_by,
        "validated_at": expense.validated_at,
        "date_soumission": expense.date_soumission,
        "user_full_name": user.full_name if user else None,
        "user_email": user.email if user else None,
        "user_rib": user.rib if user else None,
        "files": [
            {
                "id": f.id,
                "nom_fichier": f.nom_fichier,
                "taille_fichier": f.taille_fichier,
                "type_fichier": f.type_fichier,
                "date_upload": f.date_upload,
            }
            for f in expense.files
        ],
    }


def list_expenses_for_user(db: Session, user_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(Expense)
        .options(selectinload(Expense.files), selectinload(Expense.user))
        .where(Expense.id_user == user_id)
        .order_by(Expense.date_soumission.desc())
    )
    return [_serialize(e) for e in db.execute(stmt).scalars().all()]


def list_all_expenses(db: Session) -> list[dict[str, Any]]:
    stmt = (
        select(Expense)
        .options(selectinload(Expense.files), selectinload(Expense.user))
        .order_by(Expense.date_soumission.desc())
    )
    return [_serialize(e) for e in db.execute(stmt).scalars().all()]


def get_expense(db: Session, expense_id: int, *, with_user: bool = True) -> Expense | None:
    stmt = select(Expense).options(selectinload(Expense.files))
    if with_user:
        stmt = stmt.options(selectinload(Expense.user))
    stmt = stmt.where(Expense.id == expense_id)
    return db.execute(stmt).scalar_one_or_none()


def get_expense_dict(db: Session, expense_id: int) -> dict[str, Any] | None:
    expense = get_expense(db, expense_id)
    if not expense:
        return None
    return _serialize(expense)


def create_expense(
    db: Session,
    *,
    user_id: int,
    date_depense: date,
    rattachement: str | None,
    fournisseur: str | None,
    nature_charge: str | None,
    montant: Decimal,
    commentaires: str | None,
    # Montant deja rembourse (colonne DECIMAL), pas un booleen malgre le nom.
    remboursement_deja_emis: Decimal,
    remise: Decimal,
    id_pole: int | None = None,
    pole: str | None = None,
    id_event: int | None = None,
    evenement: str | None = None,
    date_evenement: date | None = None,
) -> Expense:
    expense = Expense(
        id_user=user_id,
        date_depense=date_depense,
        rattachement=rattachement,
        fournisseur=fournisseur,
        nature_charge=nature_charge,
        montant=montant,
        commentaires=commentaires,
        remboursement_deja_emis=remboursement_deja_emis,
        remise=remise,
        status="En attente",
        id_pole=id_pole,
        pole=pole,
        id_event=id_event,
        evenement=evenement,
        date_evenement=date_evenement,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def attach_file(
    db: Session,
    *,
    expense_id: int,
    nom_fichier: str,
    chemin_fichier: str,
    taille_fichier: int | None,
    type_fichier: str | None,
) -> ExpenseFile:
    file_row = ExpenseFile(
        id_note_de_frais=expense_id,
        nom_fichier=nom_fichier,
        chemin_fichier=chemin_fichier,
        taille_fichier=taille_fichier,
        type_fichier=type_fichier,
    )
    db.add(file_row)
    db.commit()
    db.refresh(file_row)
    return file_row


def update_expense_details(
    db: Session,
    expense_id: int,
    *,
    user_id: int,
    role: str,
    date_depense: date | None = None,
    rattachement: str | None = None,
    fournisseur: str | None = None,
    nature_charge: str | None = None,
    montant: Decimal | None = None,
    commentaires: str | None = None,
    remboursement_deja_emis: bool | None = None,
    remise: Decimal | None = None,
) -> Expense:
    expense = get_expense(db, expense_id, with_user=False)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    if expense.id_user != user_id and role not in ("Compta", "Super Admin"):
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Vous ne pouvez pas modifier cette note."
        )
    if expense.status != "En attente" and role not in ("Compta", "Super Admin"):
        raise AppException(ErrorCode.EXPENSE_NOT_EDITABLE)
    if date_depense is not None:
        expense.date_depense = date_depense
    if rattachement is not None:
        expense.rattachement = rattachement
    if fournisseur is not None:
        expense.fournisseur = fournisseur
    if nature_charge is not None:
        expense.nature_charge = nature_charge
    if montant is not None:
        expense.montant = montant
    if commentaires is not None:
        expense.commentaires = commentaires
    if remboursement_deja_emis is not None:
        expense.remboursement_deja_emis = remboursement_deja_emis
    if remise is not None:
        expense.remise = remise
    db.commit()
    db.refresh(expense)
    return expense


def validate_expense(
    db: Session,
    expense_id: int,
    *,
    new_status: str,
    comment: str | None,
    validated_by: int | None = None,
) -> Expense:
    expense = get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    check_expense_transition(expense.status, new_status)
    if new_status != expense.status:
        expense.validated_by = validated_by
        expense.validated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    expense.status = new_status
    expense.commentaires_compta = comment
    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, expense_id: int, *, role: str) -> Expense:
    expense = get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    if role not in ("Compta", "Super Admin"):
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Suppression reservee aux comptables."
        )
    if expense.status != "Remboursée":
        raise AppException(ErrorCode.EXPENSE_NOT_DELETABLE)
    db.delete(expense)
    db.commit()
    return expense


def list_files(db: Session, expense_id: int) -> list[ExpenseFile]:
    stmt = select(ExpenseFile).where(ExpenseFile.id_note_de_frais == expense_id)
    return list(db.execute(stmt).scalars().all())


def get_file(db: Session, file_id: int) -> ExpenseFile | None:
    return db.get(ExpenseFile, file_id)
