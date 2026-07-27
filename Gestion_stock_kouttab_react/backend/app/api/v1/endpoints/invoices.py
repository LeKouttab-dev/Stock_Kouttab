"""Invoice (factures) endpoints."""

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
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import event as event_crud
from app.crud import invoice as invoice_crud
from app.crud import pole as pole_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.invoice import InvoiceOut, InvoiceStatusUpdate
from app.services import compta_dispatch, outbox
from app.services import email as email_service
from app.services.files import delete_file, get_file_path, save_upload_file


router = APIRouter(prefix="/invoices", tags=["invoices"])

_ACCOUNTANT_ROLES = ("Compta", "Super Admin")


def _parse_optional_date(value: str | None) -> date_type | None:
    if not value:
        return None
    try:
        return date_type.fromisoformat(value)
    except ValueError as exc:
        raise AppException(
            ErrorCode.INVALID_DATE, detail="Date invalide (format YYYY-MM-DD)."
        ) from exc


def _parse_required_date(value: str) -> date_type:
    parsed = _parse_optional_date(value)
    if parsed is None:
        raise AppException(
            ErrorCode.REQUIRED_FIELD_MISSING,
            detail="La date de l'evenement est obligatoire.",
        )
    return parsed


def _parse_optional_decimal(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise AppException(
            ErrorCode.INVALID_AMOUNT, detail="Montant invalide."
        ) from exc


# ---- Read ------------------------------------------------------------------


@router.get("/me", response_model=list[InvoiceOut])
def list_my_invoices(
    db: Session = Depends(get_db), current_user: Admin = Depends(get_current_user)
) -> Any:
    return [InvoiceOut(**r) for r in invoice_crud.list_invoices_for_user(db, current_user.id)]


@router.get(
    "",
    response_model=list[InvoiceOut],
)
def list_invoices(
    status: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=0),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    if current_user.role in _ACCOUNTANT_ROLES:
        rows = invoice_crud.list_invoices(db, status=status, days=days, search=search)
    else:
        rows = invoice_crud.list_invoices_for_user(db, current_user.id)
    return [InvoiceOut(**r) for r in rows]


# ---- Create ----------------------------------------------------------------


@router.post("", response_model=InvoiceOut, status_code=201)
async def create_invoice(
    background: BackgroundTasks,
    id_pole: int = Form(...),
    date_evenement: str = Form(...),
    id_event: int | None = Form(default=None),
    evenement_libre: str | None = Form(default=None),
    fournisseur: str | None = Form(default=None),
    montant: str | None = Form(default=None),
    commentaire: str | None = Form(default=None),
    date_depot: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    if not files:
        raise AppException(
            ErrorCode.REQUIRED_FIELD_MISSING, detail="Au moins un fichier est requis."
        )
    if len(files) > 10:
        raise AppException(
            ErrorCode.TOO_MANY_FILES, detail="Maximum 10 fichiers par depot."
        )

    # Le pole et l'evenement sont resolus AVANT toute ecriture : ils composent le
    # nom du fichier envoye au comptable, une erreur ici doit etre signalee au
    # deposant plutot que produire une piece mal nommee.
    pole = pole_crud.get_pole_or_404(db, id_pole)
    event_id, event_label = event_crud.resolve_event(
        db, event_id=id_event, evenement_libre=evenement_libre
    )
    date_event = _parse_required_date(date_evenement)

    invoice = invoice_crud.create_invoice(
        db,
        user_id=current_user.id,
        commentaire=commentaire,
        date_depot=_parse_optional_date(date_depot),
        id_pole=pole.id,
        pole=pole.nom,
        id_event=event_id,
        evenement=event_label,
        date_evenement=date_event,
        fournisseur=fournisseur,
        montant=_parse_optional_decimal(montant),
    )

    for upload in files:
        if not upload or not upload.filename:
            continue
        meta = await save_upload_file(upload, "invoices")
        invoice_crud.attach_file(
            db,
            invoice_id=invoice.id,
            nom_fichier=str(meta["filename"]),
            chemin_fichier=str(meta["path"]),
            taille_fichier=int(meta["size"]),
            type_fichier=str(meta["mime"]),
        )

    inv = invoice_crud.get_invoice(db, invoice.id)
    if inv is None:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)

    # Conversion PDF et mise en file : synchrone et dans la transaction. Si la
    # conversion echoue, le deposant le voit immediatement au lieu de croire sa
    # piece partie. Seul l'envoi SMTP part en tache de fond.
    outbound = compta_dispatch.prepare_invoice_dispatch(
        db, inv, triggered_by=current_user.id
    )
    background.add_task(_notify_new_invoice_safe, current_user.full_name, commentaire)
    for row in outbound:
        background.add_task(outbox.try_send_now, row.id)

    return InvoiceOut(**_serialize_invoice(inv))


@router.post(
    "/{invoice_id}/resend-compta-email",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def resend_compta_email(
    invoice_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Relance l'envoi au comptable (nouvelle ligne, l'historique est conserve)."""
    invoice = invoice_crud.get_invoice(db, invoice_id)
    if invoice is None:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)
    rows = compta_dispatch.prepare_invoice_dispatch(
        db, invoice, triggered_by=current_user.id
    )
    for row in rows:
        background.add_task(outbox.try_send_now, row.id)
    return MessageOut(message="Envoi au service comptable relance.")


# ---- Update status ---------------------------------------------------------


@router.patch(
    "/{invoice_id}/status",
    response_model=InvoiceOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def update_invoice_status(
    invoice_id: int,
    payload: InvoiceStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    invoice = invoice_crud.update_status(
        db, invoice_id, payload.status, validated_by=current_user.id
    )
    return InvoiceOut(**_serialize_invoice(invoice))


# ---- File access -----------------------------------------------------------


@router.get("/{invoice_id}/files/{file_id}")
def download_invoice_file(
    invoice_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    invoice = invoice_crud.get_invoice(db, invoice_id)
    if not invoice:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)
    if invoice.id_user != current_user.id and current_user.role not in _ACCOUNTANT_ROLES:
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Acces refuse a ce fichier."
        )
    file_row = invoice_crud.get_file(db, file_id)
    if not file_row or file_row.id_facture != invoice_id:
        raise AppException(ErrorCode.FILE_NOT_FOUND)
    path = get_file_path(file_row.chemin_fichier)
    if not path:
        raise AppException(ErrorCode.FILE_PHYSICALLY_MISSING)
    return FileResponse(
        path,
        media_type=file_row.type_fichier or "application/octet-stream",
        filename=file_row.nom_fichier,
    )


@router.delete("/{invoice_id}", response_model=MessageOut)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    invoice = invoice_crud.get_invoice(db, invoice_id)
    if not invoice:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)
    is_accountant = current_user.role in _ACCOUNTANT_ROLES
    if invoice.id_user != current_user.id and not is_accountant:
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Vous ne pouvez pas supprimer cette facture."
        )
    # Une facture prise en charge par la comptabilite est une piece comptable :
    # son deposant ne peut plus la faire disparaitre.
    if not is_accountant and invoice.status != "En attente":
        raise AppException(
            ErrorCode.FORBIDDEN,
            detail=(
                "Cette facture est deja traitee par la comptabilite et ne peut "
                "plus etre supprimee. Contactez le service comptable."
            ),
            extras={"status": invoice.status},
        )
    files = list(invoice.files)
    db.delete(invoice)
    db.commit()
    for f in files:
        delete_file(f.chemin_fichier)
    return MessageOut(message="Facture supprimee.")


# ---- Helpers ---------------------------------------------------------------


def _serialize_invoice(invoice) -> dict[str, Any]:
    # Delegue au CRUD : ce module en avait une copie, qui divergeait des que le
    # modele gagnait un champ.
    return invoice_crud.serialize_invoice(invoice)


async def _notify_new_invoice_safe(user_full_name: str, comment: str | None) -> None:
    db = SessionLocal()
    try:
        await email_service.send_invoice_notification(
            db, user_full_name=user_full_name, comment=comment
        )
    finally:
        db.close()
