"""Preparation des envois de pieces comptables.

Assemble les trois briques : nomenclature (``naming``), conversion PDF
(``pdf``) et file d'attente persistante (``outbox``).

Un justificatif = un PDF = une piece jointe, conformement a la demande du
client (pas de fusion, pas d'archive ZIP).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger
from app.db.models import Expense, Invoice, OutboundEmail
from app.services import naming, outbox, pdf


logger = get_logger("compta_dispatch")


KIND_INVOICE = "invoice_compta"
KIND_EXPENSE = "expense_compta"


def _outbox_dir(entity_type: str, entity_id: int) -> Path:
    return settings.outbox_path / entity_type / str(entity_id)


def _format_amount(value: Decimal | None) -> str:
    return f"{value:.2f} EUR" if value is not None else "-"


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "-"


def _prepare_attachments(
    *,
    files: list,
    components: list[str | None],
    date_value: date | None,
    entity_type: str,
    entity_id: int,
) -> list[Path]:
    """Convertit chaque justificatif en PDF nomme selon la nomenclature."""
    target_dir = _outbox_dir(entity_type, entity_id)
    names = [
        naming.build_attachment_filename(components, date_value) for _ in files
    ]
    names = naming.deduplicate_filenames(names)

    attachments: list[Path] = []
    for file_row, filename in zip(files, names):
        stem = filename.rsplit(".", 1)[0]
        produced, converted = pdf.ensure_pdf(
            Path(file_row.chemin_fichier), target_dir=target_dir, target_stem=stem
        )
        logger.info(
            "Piece comptable prete : %s (%s)",
            produced.name,
            "convertie" if converted else "PDF d'origine",
        )
        attachments.append(produced)
    return attachments


def _split_by_size(attachments: list[Path]) -> list[list[Path]]:
    """Repartit les pieces en lots respectant la limite SMTP.

    Dix fichiers de 10 Mo depassent tres largement ce qu'accepte un SMTP
    mutualise. Plutot que d'echouer, on decoupe en plusieurs courriels.
    """
    budget = settings.max_attachment_total_mb * 1024 * 1024
    batches: list[list[Path]] = []
    current: list[Path] = []
    current_size = 0
    for path in attachments:
        size = path.stat().st_size if path.exists() else 0
        if current and current_size + size > budget:
            batches.append(current)
            current, current_size = [], 0
        current.append(path)
        current_size += size
    if current:
        batches.append(current)
    return batches or [[]]


# ---- Factures ---------------------------------------------------------------


def prepare_invoice_dispatch(
    db: Session, invoice: Invoice, *, triggered_by: int | None = None
) -> list[OutboundEmail]:
    depositor = invoice.user.full_name if invoice.user else "-"
    attachments = _prepare_attachments(
        files=list(invoice.files),
        components=[invoice.pole, invoice.evenement or invoice.categorie],
        # Sans evenement, sa date n'existe pas : le depot fait foi.
        date_value=invoice.date_evenement or invoice.date_depot,
        entity_type="invoice",
        entity_id=invoice.id,
    )
    batches = _split_by_size(attachments)

    rows: list[OutboundEmail] = []
    for index, batch in enumerate(batches, start=1):
        suffix = f" ({index}/{len(batches)})" if len(batches) > 1 else ""
        subject = (
            f"[Facture] {invoice.pole or 'NC'} — "
            f"{invoice.evenement or invoice.categorie or 'NC'} — "
            f"{_format_date(invoice.date_evenement or invoice.date_depot)}{suffix}"
        )
        body = (
            "Bonjour,\n\n"
            "Une nouvelle facture a ete deposee dans l'application de gestion.\n\n"
            f"Pole          : {invoice.pole or '-'}\n"
            f"Evenement     : {invoice.evenement or '-'}\n"
            f"Categorie     : {invoice.categorie or '-'}\n"
            f"Date          : {_format_date(invoice.date_evenement or invoice.date_depot)}\n"
            f"Fournisseur   : {invoice.fournisseur or '-'}\n"
            f"Montant       : {_format_amount(invoice.montant)}\n"
            f"Depose par    : {depositor}\n"
            f"Le            : {_format_date(invoice.date_depot)}\n"
            f"Commentaire   : {invoice.commentaire or '-'}\n\n"
            "Piece(s) jointe(s) :\n"
            + "\n".join(f"  - {p.name}" for p in batch)
            + "\n\nCordialement,\nLe Kouttab — gestion des stocks."
        )
        rows.append(
            outbox.enqueue(
                db,
                kind=KIND_INVOICE,
                entity_type="invoice",
                entity_id=invoice.id,
                recipients=settings.compta_emails,
                subject=subject,
                body=body,
                attachments=batch,
                triggered_by=triggered_by,
            )
        )
    return rows


# ---- Notes de frais ---------------------------------------------------------


def prepare_expense_dispatch(
    db: Session, expense: Expense, *, triggered_by: int | None = None
) -> list[OutboundEmail]:
    depositor = expense.user.full_name if expense.user else "-"
    # Meme nomenclature que les factures : {Pole}_{Evenement}_{Date}.pdf.
    # La date de l'evenement fait foi ; a defaut (note sans evenement rattache),
    # on retombe sur la date de la depense pour ne jamais produire un « NC ».
    date_value = expense.date_evenement or expense.date_depense
    attachments = _prepare_attachments(
        files=list(expense.files),
        components=[
            expense.pole,
            expense.evenement or expense.categorie or expense.rattachement,
        ],
        date_value=date_value,
        entity_type="expense",
        entity_id=expense.id,
    )
    batches = _split_by_size(attachments)

    rows: list[OutboundEmail] = []
    for index, batch in enumerate(batches, start=1):
        suffix = f" ({index}/{len(batches)})" if len(batches) > 1 else ""
        subject = (
            f"[Note de frais] {expense.pole or 'NC'} — "
            f"{expense.evenement or expense.categorie or expense.rattachement or 'NC'} — "
            f"{_format_date(date_value)}{suffix}"
        )
        body = (
            "Bonjour,\n\n"
            "Une nouvelle note de frais a ete deposee dans l'application.\n\n"
            f"Pole          : {expense.pole or '-'}\n"
            f"Evenement     : {expense.evenement or '-'}\n"
            f"Categorie     : {expense.categorie or '-'}\n"
            f"Rattachement  : {expense.rattachement or '-'}\n"
            f"Date          : {_format_date(date_value)}\n"
            f"Fournisseur   : {expense.fournisseur or '-'}\n"
            f"Nature        : {expense.nature_charge or '-'}\n"
            f"Montant       : {_format_amount(expense.montant)}\n"
            f"Deja rembourse: {_format_amount(expense.remboursement_deja_emis)}\n"
            f"Remise        : {_format_amount(expense.remise)}\n"
            f"Depose par    : {depositor}\n"
            f"Commentaires  : {expense.commentaires or '-'}\n\n"
            "Ticket(s) joint(s) :\n"
            + "\n".join(f"  - {p.name}" for p in batch)
            + "\n\nCordialement,\nLe Kouttab — gestion des stocks."
        )
        rows.append(
            outbox.enqueue(
                db,
                kind=KIND_EXPENSE,
                entity_type="expense",
                entity_id=expense.id,
                recipients=settings.compta_emails,
                subject=subject,
                body=body,
                attachments=batch,
                triggered_by=triggered_by,
            )
        )
    return rows
