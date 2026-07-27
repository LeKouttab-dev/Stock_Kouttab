"""Admin: database export/import & diagnostics."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.exceptions import ValidationError
from app.core.logger import get_logger
from app.db.models import (
    Admin,
    AdminInvitation,
    Category,
    Expense,
    ExpenseFile,
    Invoice,
    InvoiceFile,
    Stock,
    StockModification,
    SubCategory,
)
from app.db.session import engine, get_db
from app.schemas.auth import MessageOut


router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger("admin")


# Tables exported to CSV. Admins is excluded for security.
_EXPORTABLE: list[tuple[str, type]] = [
    ("Stock", Stock),
    ("Categories", Category),
    ("SousCategories", SubCategory),
    ("NotesDeFrais", Expense),
    ("FichiersNotesDeFrais", ExpenseFile),
    ("Factures", Invoice),
    ("FichiersFactures", InvoiceFile),
    ("StockModifications", StockModification),
    ("AdminInvitations", AdminInvitation),
]


# ---- Diagnostics -----------------------------------------------------------


@router.get(
    "/database/status",
    dependencies=[Depends(require_roles("Super Admin"))],
)
def database_status(db: Session = Depends(get_db)) -> Any:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    counts: dict[str, int] = {}
    for tname, model in [
        *_EXPORTABLE,
        ("Admins", Admin),
    ]:
        try:
            counts[tname] = db.query(model).count()
        except Exception as exc:  # noqa: BLE001
            counts[tname] = -1
            logger.warning("Count failed for %s: %s", tname, exc)
    return {
        "engine": str(engine.url).split("@")[-1],
        "tables": tables,
        "row_counts": counts,
        "ok": True,
    }


# ---- Export ----------------------------------------------------------------


@router.post(
    "/database/export",
    dependencies=[Depends(require_roles("Super Admin"))],
)
def export_database(db: Session = Depends(get_db)) -> Any:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for table_name, model in _EXPORTABLE:
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            columns = [c.name for c in model.__table__.columns]
            writer.writerow(columns)
            for row in db.query(model).all():
                writer.writerow([_serialize_cell(getattr(row, col)) for col in columns])
            archive.writestr(f"{table_name}.csv", csv_buffer.getvalue())

    buffer.seek(0)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    headers = {
        "Content-Disposition": f'attachment; filename="kouttab_export_{timestamp}.zip"'
    }
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


def _serialize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


# ---- Import ----------------------------------------------------------------


_IMPORTABLE: dict[str, type] = {name: model for name, model in _EXPORTABLE}


@router.post(
    "/database/import",
    response_model=MessageOut,
    dependencies=[Depends(require_roles("Super Admin"))],
)
async def import_database(
    confirm: bool = False,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> Any:
    if not confirm:
        raise ValidationError(
            "Confirmation requise (parametre 'confirm=true') pour eviter une perte de donnees."
        )
    if not files:
        raise ValidationError("Aucun fichier fourni.")

    summary: dict[str, int] = {}
    for upload in files:
        if not upload or not upload.filename:
            continue
        table_name = upload.filename.rsplit(".", 1)[0]
        model = _IMPORTABLE.get(table_name)
        if not model:
            summary[upload.filename] = 0
            continue
        content = await upload.read()
        text_io = io.StringIO(content.decode("utf-8-sig"))
        reader = csv.DictReader(text_io)
        inserted = 0
        for raw_row in reader:
            cleaned = {k: (v if v != "" else None) for k, v in raw_row.items()}
            try:
                db.execute(model.__table__.insert().values(**cleaned))
                inserted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Import %s: ligne ignoree: %s", table_name, exc)
        summary[table_name] = inserted
    db.commit()

    parts = ", ".join(f"{k}={v}" for k, v in summary.items())
    return MessageOut(message=f"Import termine ({parts}).")


# ---- Truncate (rare, dangerous) -------------------------------------------


@router.post(
    "/database/check",
    dependencies=[Depends(require_roles("Super Admin"))],
)
def check_database(db: Session = Depends(get_db)) -> Any:
    """Quick health check: SELECT 1."""
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.exception("DB health check failed: %s", exc)
        return {"ok": False, "error": str(exc)}
