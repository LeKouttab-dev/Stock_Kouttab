"""Invoice (factures) CRUD."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.db.models import Invoice, InvoiceFile


def _serialize(invoice: Invoice) -> dict[str, Any]:
    user = invoice.user
    return {
        "id": invoice.id,
        "id_user": invoice.id_user,
        "commentaire": invoice.commentaire,
        "date_depot": invoice.date_depot,
        "status": invoice.status,
        "created_at": invoice.created_at,
        "user_full_name": user.full_name if user else None,
        "user_email": user.email if user else None,
        "files": [
            {
                "id": f.id,
                "nom_fichier": f.nom_fichier,
                "taille_fichier": f.taille_fichier,
                "type_fichier": f.type_fichier,
                "date_upload": f.date_upload,
            }
            for f in invoice.files
        ],
    }


def list_invoices_for_user(db: Session, user_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.files), selectinload(Invoice.user))
        .where(Invoice.id_user == user_id)
        .order_by(Invoice.date_depot.desc())
    )
    return [_serialize(e) for e in db.execute(stmt).scalars().all()]


def list_invoices(
    db: Session,
    *,
    status: str | None = None,
    days: int | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.files), selectinload(Invoice.user))
        .order_by(Invoice.date_depot.desc())
    )
    if status:
        stmt = stmt.where(Invoice.status == status)
    if days is not None and days > 0:
        threshold = datetime.now(timezone.utc).date() - timedelta(days=days)
        stmt = stmt.where(Invoice.date_depot >= threshold)
    invoices = list(db.execute(stmt).scalars().all())

    if search:
        search_lower = search.lower()
        invoices = [
            inv
            for inv in invoices
            if any(search_lower in (f.nom_fichier or "").lower() for f in inv.files)
            or search_lower in (inv.commentaire or "").lower()
        ]
    return [_serialize(inv) for inv in invoices]


def get_invoice(db: Session, invoice_id: int) -> Invoice | None:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.files), selectinload(Invoice.user))
        .where(Invoice.id == invoice_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def create_invoice(
    db: Session,
    *,
    user_id: int,
    commentaire: str | None,
    date_depot: date | None,
) -> Invoice:
    invoice = Invoice(
        id_user=user_id,
        commentaire=commentaire,
        date_depot=date_depot or datetime.now(timezone.utc).date(),
        status="En attente",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def attach_file(
    db: Session,
    *,
    invoice_id: int,
    nom_fichier: str,
    chemin_fichier: str,
    taille_fichier: int | None,
    type_fichier: str | None,
) -> InvoiceFile:
    f = InvoiceFile(
        id_facture=invoice_id,
        nom_fichier=nom_fichier,
        chemin_fichier=chemin_fichier,
        taille_fichier=taille_fichier,
        type_fichier=type_fichier,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def update_status(db: Session, invoice_id: int, new_status: str) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)
    invoice.status = new_status
    db.commit()
    db.refresh(invoice)
    return invoice


def get_file(db: Session, file_id: int) -> InvoiceFile | None:
    return db.get(InvoiceFile, file_id)
