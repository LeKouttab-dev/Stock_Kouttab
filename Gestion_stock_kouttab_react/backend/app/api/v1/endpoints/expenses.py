"""Expenses (notes de frais) endpoints."""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import event as event_crud
from app.crud import expense as expense_crud
from app.crud import pole as pole_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.expense import ExpenseOut, ExpenseUpdate, ExpenseValidate
from app.services import compta_dispatch, outbox
from app.services import email as email_service
from app.services.files import delete_file, get_file_path, save_upload_file


router = APIRouter(prefix="/expenses", tags=["expenses"])


_ACCOUNTANT_ROLES = ("Compta", "Super Admin")


def _to_out(row: dict[str, Any], *, requester: Admin) -> ExpenseOut:
    if not _can_see_rib(requester, row["id_user"]):
        row = dict(row)
        row["user_rib"] = None
    return ExpenseOut(**row)


def _can_see_rib(requester: Admin, owner_id: int) -> bool:
    if requester.role in _ACCOUNTANT_ROLES:
        return True
    return requester.id == owner_id


def _parse_decimal(value: str | None, *, field: str, default: Decimal | None = None) -> Decimal:
    if value is None or value == "":
        if default is not None:
            return default
        raise AppException(
            ErrorCode.REQUIRED_FIELD_MISSING,
            detail=f"Champ '{field}' requis.",
            extras={"field": field},
        )
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise AppException(
            ErrorCode.INVALID_AMOUNT,
            detail=f"Valeur decimale invalide pour '{field}'.",
            extras={"field": field},
        ) from exc


def _parse_date(value: str | None, *, field: str) -> date_type:
    if not value:
        raise AppException(
            ErrorCode.REQUIRED_FIELD_MISSING,
            detail=f"Champ '{field}' requis.",
            extras={"field": field},
        )
    try:
        return date_type.fromisoformat(value)
    except ValueError as exc:
        raise AppException(
            ErrorCode.INVALID_DATE,
            detail=f"Date invalide pour '{field}', format attendu YYYY-MM-DD.",
            extras={"field": field},
        ) from exc


# ---- Read ------------------------------------------------------------------


@router.get("/me", response_model=list[ExpenseOut])
def list_my_expenses(
    db: Session = Depends(get_db), current_user: Admin = Depends(get_current_user)
) -> Any:
    rows = expense_crud.list_expenses_for_user(db, current_user.id)
    return [_to_out(r, requester=current_user) for r in rows]


@router.get(
    "",
    response_model=list[ExpenseOut],
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def list_all_expenses(
    db: Session = Depends(get_db), current_user: Admin = Depends(get_current_user)
) -> Any:
    rows = expense_crud.list_all_expenses(db)
    return [_to_out(r, requester=current_user) for r in rows]


# ---- Create ----------------------------------------------------------------


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    background: BackgroundTasks,
    date_depense: str = Form(...),
    montant: str = Form(...),
    fournisseur: str = Form(...),
    id_pole: int = Form(...),
    date_evenement: str = Form(...),
    rattachement: str | None = Form(default=None),
    nature_charge: str | None = Form(default=None),
    commentaires: str | None = Form(default=None),
    remboursement_deja_emis: str | None = Form(default=None),
    remise: str | None = Form(default=None),
    id_event: int | None = Form(default=None),
    evenement_libre: str | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    # Pole, evenement et date composent le nom du ticket envoye au comptable :
    # ils sont exiges, au meme titre que sur les factures. Une note deposee sans
    # eux arrivait chez le comptable sous un nom incomplet, impossible a imputer.
    # `rattachement` reste accepte en entree sans etre requis : les notes
    # anterieures le portent, et le champ subsiste en base.
    if not fournisseur.strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Le fournisseur est obligatoire."
        )
    pole = pole_crud.get_pole_or_404(db, id_pole)
    if id_event is None and not (evenement_libre or "").strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="L'evenement est obligatoire : choisissez-en un ou saisissez son nom.",
        )
    event_id, event_label = event_crud.resolve_event(
        db, event_id=id_event, evenement_libre=evenement_libre
    )

    expense = expense_crud.create_expense(
        db,
        user_id=current_user.id,
        date_depense=_parse_date(date_depense, field="date_depense"),
        rattachement=rattachement,
        fournisseur=fournisseur,
        nature_charge=nature_charge,
        montant=_parse_decimal(montant, field="montant"),
        commentaires=commentaires,
        remboursement_deja_emis=_parse_decimal(
            remboursement_deja_emis, field="remboursement_deja_emis", default=Decimal("0")
        ),
        remise=_parse_decimal(remise, field="remise", default=Decimal("0")),
        id_pole=pole.id,
        pole=pole.nom,
        id_event=event_id,
        evenement=event_label,
        date_evenement=_parse_date(date_evenement, field="date_evenement"),
    )
    if files:
        if len(files) > 5:
            raise AppException(ErrorCode.TOO_MANY_FILES)
        for upload in files:
            if not upload or not upload.filename:
                continue
            meta = await save_upload_file(upload, "expenses")
            expense_crud.attach_file(
                db,
                expense_id=expense.id,
                nom_fichier=str(meta["filename"]),
                chemin_fichier=str(meta["path"]),
                taille_fichier=int(meta["size"]),
                type_fichier=str(meta["mime"]),
            )
    background.add_task(
        _notify_new_expense_safe,
        current_user.full_name,
        float(expense.montant),
        expense.rattachement,
    )

    # Envoi des tickets au comptable, meme chaine que les factures. Synchrone
    # jusqu'a la mise en file : une conversion PDF ratee doit remonter au
    # deposant, pas disparaitre dans une tache de fond.
    full_expense = expense_crud.get_expense(db, expense.id)
    if full_expense is not None and full_expense.files:
        for row in compta_dispatch.prepare_expense_dispatch(
            db, full_expense, triggered_by=current_user.id
        ):
            background.add_task(outbox.try_send_now, row.id)

    out = expense_crud.get_expense_dict(db, expense.id)
    if out is None:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    return _to_out(out, requester=current_user)


@router.post(
    "/{expense_id}/resend-compta-email",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def resend_expense_compta_email(
    expense_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense = expense_crud.get_expense(db, expense_id)
    if expense is None:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    for row in compta_dispatch.prepare_expense_dispatch(
        db, expense, triggered_by=current_user.id
    ):
        background.add_task(outbox.try_send_now, row.id)
    return MessageOut(message="Envoi au service comptable relance.")


# ---- Edit ------------------------------------------------------------------


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    data = payload.model_dump(exclude_unset=True)
    expense = expense_crud.update_expense_details(
        db,
        expense_id,
        user_id=current_user.id,
        role=current_user.role,
        **data,
    )
    out = expense_crud.get_expense_dict(db, expense.id)
    return _to_out(out or {}, requester=current_user)


@router.patch(
    "/{expense_id}/validate",
    response_model=ExpenseOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def validate_expense(
    expense_id: int,
    payload: ExpenseValidate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense = expense_crud.validate_expense(
        db,
        expense_id,
        new_status=payload.status,
        comment=payload.commentaires_compta,
        validated_by=current_user.id,
    )
    out = expense_crud.get_expense_dict(db, expense.id)
    if out and out.get("user_email"):
        background.add_task(
            email_service.send_status_change,
            recipient=out["user_email"],
            subject=f"Mise a jour de votre note de frais #{expense.id}",
            body=(
                f"Bonjour,\n\nVotre note de frais #{expense.id} a ete mise a jour.\n"
                f"Nouveau statut : {payload.status}\n"
                f"Commentaire compta : {payload.commentaires_compta or '-'}\n\n"
                "Cordialement,\nLe Kouttab."
            ),
        )
    return _to_out(out or {}, requester=current_user)


# ---- Delete ----------------------------------------------------------------


@router.delete("/{expense_id}", response_model=MessageOut)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense = expense_crud.get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    files = list(expense.files)
    expense_crud.delete_expense(db, expense_id, role=current_user.role)
    for f in files:
        delete_file(f.chemin_fichier)
    return MessageOut(message="Note supprimee.")


# ---- Files -----------------------------------------------------------------


@router.get("/{expense_id}/files")
def list_expense_files(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense = expense_crud.get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    if expense.id_user != current_user.id and current_user.role not in _ACCOUNTANT_ROLES:
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Acces refuse a ces fichiers."
        )
    return [
        {
            "id": f.id,
            "nom_fichier": f.nom_fichier,
            "taille_fichier": f.taille_fichier,
            "type_fichier": f.type_fichier,
            "date_upload": f.date_upload,
        }
        for f in expense.files
    ]


@router.get("/{expense_id}/files/{file_id}")
def download_expense_file(
    expense_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense = expense_crud.get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    if expense.id_user != current_user.id and current_user.role not in _ACCOUNTANT_ROLES:
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Acces refuse a ce fichier."
        )
    file_row = expense_crud.get_file(db, file_id)
    if not file_row or file_row.id_note_de_frais != expense_id:
        raise AppException(ErrorCode.FILE_NOT_FOUND)
    path = get_file_path(file_row.chemin_fichier)
    if not path:
        raise AppException(ErrorCode.FILE_PHYSICALLY_MISSING)
    return FileResponse(path, media_type=file_row.type_fichier or "application/octet-stream", filename=file_row.nom_fichier)


# ---- Background tasks ------------------------------------------------------


async def _notify_new_expense_safe(user_full_name: str, amount: float, rattachement: str | None) -> None:
    db = SessionLocal()
    try:
        await email_service.send_new_expense_notification(
            db,
            user_full_name=user_full_name,
            amount=amount,
            rattachement=rattachement,
        )
    finally:
        db.close()
