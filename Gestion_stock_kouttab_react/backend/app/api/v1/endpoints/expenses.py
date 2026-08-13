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
from fastapi import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import expense as expense_crud
from app.crud import rattachement as rattachement_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.expense import (
    ExpenseOut,
    ExpenseUpdate,
    ExpenseValidate,
    SuppressionDefinitiveIn,
)
from app.services import compta_dispatch, email_layout, outbox
from app.services import email as email_service
from app.services.files import contenu_du_fichier, save_upload_file


router = APIRouter(prefix="/expenses", tags=["expenses"])


_ACCOUNTANT_ROLES = ("Compta", "Super Admin")


# Ce que le changement de statut signifie pour le deposant, et ce qu'il doit en
# attendre. Un courriel qui annonce « Refusee » sans dire quoi faire ensuite
# oblige a ecrire a la comptabilite pour comprendre.
_INTRO_STATUT = {
    "Approuvee": "Votre note de frais a ete approuvee par la comptabilite.",
    "Approuvée": "Votre note de frais a ete approuvee par la comptabilite.",
    "Refusee": "Votre note de frais n'a pas ete retenue par la comptabilite.",
    "Refusée": "Votre note de frais n'a pas ete retenue par la comptabilite.",
    "Remboursee": "Votre note de frais a ete remboursee.",
    "Remboursée": "Votre note de frais a ete remboursee.",
    "En attente": "Votre note de frais est de nouveau en attente de traitement.",
}

_SUITE_STATUT = {
    "Approuvee": "Le versement suivra ; vous recevrez le justificatif de remboursement.",
    "Approuvée": "Le versement suivra ; vous recevrez le justificatif de remboursement.",
    "Refusee": "Le motif figure ci-dessus. Vous pouvez deposer une nouvelle note corrigee.",
    "Refusée": "Le motif figure ci-dessus. Vous pouvez deposer une nouvelle note corrigee.",
    "Remboursee": "Verifiez la reception sur votre compte dans les prochains jours.",
    "Remboursée": "Verifiez la reception sur votre compte dans les prochains jours.",
}


def _to_out(row: dict[str, Any], *, requester: Admin) -> ExpenseOut:
    if not _can_see_rib(requester, row["id_user"]):
        row = dict(row)
        row["user_rib"] = None
        row["user_rib_document_nom"] = None
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
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    rows = expense_crud.list_all_expenses(db, include_archived=include_archived)
    return [_to_out(r, requester=current_user) for r in rows]


# ---- Create ----------------------------------------------------------------


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    background: BackgroundTasks,
    date_depense: str = Form(...),
    montant: str = Form(...),
    fournisseur: str = Form(...),
    id_pole: int = Form(...),
    # Optionnelle depuis l'introduction des poles sans evenement : sous « Local »
    # il n'y a pas d'evenement, donc pas de date d'evenement. L'obligation est
    # portee par la resolution du rattachement, qui sait ce que le pole attend.
    date_evenement: str | None = Form(default=None),
    rattachement: str | None = Form(default=None),
    nature_charge: str | None = Form(default=None),
    commentaires: str | None = Form(default=None),
    remboursement_deja_emis: str | None = Form(default=None),
    remise: str | None = Form(default=None),
    id_event: int | None = Form(default=None),
    evenement_libre: str | None = Form(default=None),
    id_categorie: int | None = Form(default=None),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    # Le rattachement compose le nom du ticket envoye au comptable : il est
    # exige, au meme titre que sur les factures. Une note deposee sans lui
    # arrivait chez le comptable sous un nom incomplet, impossible a imputer.
    # Selon le pole, ce rattachement est un evenement ou une categorie.
    # `rattachement` reste accepte en entree sans etre requis : les notes
    # anterieures le portent, et le champ subsiste en base.
    if not fournisseur.strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Le fournisseur est obligatoire."
        )
    rattachement_resolu = rattachement_crud.resoudre(
        db,
        id_pole=id_pole,
        id_event=id_event,
        evenement_libre=evenement_libre,
        id_categorie=id_categorie,
        date_evenement=(
            _parse_date(date_evenement, field="date_evenement")
            if date_evenement
            else None
        ),
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
        id_pole=rattachement_resolu.id_pole,
        pole=rattachement_resolu.pole,
        id_event=rattachement_resolu.id_event,
        evenement=rattachement_resolu.evenement,
        id_categorie=rattachement_resolu.id_categorie,
        categorie=rattachement_resolu.categorie,
        date_evenement=rattachement_resolu.date_evenement,
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
                contenu=meta.get("contenu"),  # type: ignore[arg-type]
            )
    background.add_task(
        _notify_new_expense_safe,
        current_user.full_name,
        float(expense.montant),
        # Ce que la comptabilite lit d'abord : à quoi la dépense se rattache.
        rattachement_resolu.libelle_document or expense.rattachement,
        current_user.email,
        expense.fournisseur,
        expense.date_depense,
        expense.nature_charge,
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
            auteur_email=current_user.email,
            recipient=out["user_email"],
            subject=f"Votre note de frais #{expense.id} — {payload.status}",
            body=email_layout.composer(
                prenom=out.get("user_prenom"),
                introduction=_INTRO_STATUT.get(
                    payload.status,
                    f"Votre note de frais #{expense.id} a ete mise a jour.",
                ),
                blocs=[
                    ("Note de frais", f"#{expense.id}"),
                    ("Date de depense", expense.date_depense),
                    ("Fournisseur", expense.fournisseur),
                    ("Montant", expense.montant),
                    ("Nouveau statut", payload.status),
                    ("Commentaire", payload.commentaires_compta),
                ],
                conclusion=_SUITE_STATUT.get(payload.status),
            ),
        )
    return _to_out(out or {}, requester=current_user)


# ---- Archivage --------------------------------------------------------------
#
# `DELETE` conserve son verbe : c'est le geste du comptable, « je range cette
# note », et le front l'appelle deja ainsi. Ce qui change est ce qu'il fait —
# plus rien n'est detruit, ni la ligne ni les justificatifs.


@router.delete("/{expense_id}", response_model=MessageOut)
def archive_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense_crud.archive_expense(db, expense_id, user=current_user)
    return MessageOut(message="Note archivee.")


@router.delete("/{expense_id}/definitif", response_model=MessageOut)
def supprimer_definitivement(
    expense_id: int,
    payload: SuppressionDefinitiveIn,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Efface la note pour de bon. **Super Admin uniquement.**

    Existe pour le menage — notes de test, saisies fautives —, pas pour le
    travail courant : une piece comptable reelle s'archive. Le CRUD porte les
    garde-fous (role, motif obligatoire, journalisation).
    """
    expense_crud.supprimer_definitivement(
        db, expense_id, user=current_user, motif=payload.motif
    )
    return MessageOut(message="Note supprimee definitivement.")


@router.post("/{expense_id}/restore", response_model=MessageOut)
def restore_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    expense_crud.restore_expense(db, expense_id, role=current_user.role)
    return MessageOut(message="Note restauree.")


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
    return _servir(file_row)



def _servir(file_row) -> Response:
    """Sert un justificatif depuis la base, ou depuis le disque a defaut.

    La base fait autorite : c'est la seule copie sauvegardee. Le repli disque
    couvre les pieces deposees avant la migration.

    `Response` et non `FileResponse` : le contenu vient de la base, il n'y a pas
    toujours de fichier a pointer. `Content-Disposition` reprend le nom
    d'origine, comme avant.
    """
    contenu = contenu_du_fichier(file_row)
    if contenu is None:
        raise AppException(ErrorCode.FILE_PHYSICALLY_MISSING)
    nom = (file_row.nom_fichier or "justificatif").replace('"', "")
    return Response(
        content=contenu,
        media_type=file_row.type_fichier or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


# ---- Background tasks ------------------------------------------------------


async def _notify_new_expense_safe(
    user_full_name: str,
    amount: float,
    rattachement: str | None,
    auteur_email: str | None = None,
    fournisseur: str | None = None,
    date_depense: object = None,
    nature_charge: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        await email_service.send_new_expense_notification(
            db,
            user_full_name=user_full_name,
            amount=amount,
            rattachement=rattachement,
            auteur_email=auteur_email,
            fournisseur=fournisseur,
            date_depense=date_depense,
            nature_charge=nature_charge,
        )
    finally:
        db.close()
