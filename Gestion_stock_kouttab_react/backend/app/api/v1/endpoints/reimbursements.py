"""Remboursements groupes : un versement solde plusieurs notes de frais."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core import reimbursement_options
from app.crud import reimbursement as reimbursement_crud
from app.db.models import Admin
from app.db.session import get_db
from app.schemas.reimbursement import (
    ReimbursementCreate,
    ReimbursementOptionsOut,
    ReimbursementOut,
    VolunteerExpensesOut,
)


router = APIRouter(prefix="/reimbursements", tags=["reimbursements"])

# Meme perimetre que la validation des notes : le remboursement est l'etape
# suivante du meme travail.
_ACCOUNTANT_ROLES = ("Compta", "Super Admin")

_MIME = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _to_out(row: Any) -> ReimbursementOut:
    out = ReimbursementOut.model_validate(row)
    out.user_full_name = row.user.full_name if row.user else None
    out.a_pdf = bool(row.chemin_pdf)
    out.a_xlsx = bool(row.chemin_xlsx)
    return out


@router.get(
    "/options",
    response_model=ReimbursementOptionsOut,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def get_options() -> Any:
    """Listes figees du formulaire, servies plutot que recopiees cote front.

    Elles doivent rester alignees sur ce que l'API accepte : les dupliquer dans
    le navigateur ferait diverger les deux au premier ajout.
    """
    return ReimbursementOptionsOut(
        moyens=list(reimbursement_options.MOYENS),
        etablissements=list(reimbursement_options.ETABLISSEMENTS),
        moyen_defaut=reimbursement_options.MOYEN_PAR_DEFAUT,
        etablissement_defaut=reimbursement_options.ETABLISSEMENT_PAR_DEFAUT,
        approbateur_defaut=reimbursement_options.APPROBATEUR_PAR_DEFAUT,
    )


@router.get(
    "/by-volunteer",
    response_model=list[VolunteerExpensesOut],
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def list_by_volunteer(db: Session = Depends(get_db)) -> Any:
    """Fiches des benevoles : combien de notes, combien a rembourser."""
    return [VolunteerExpensesOut(**f) for f in reimbursement_crud.list_by_volunteer(db)]


@router.get("", response_model=list[ReimbursementOut])
def list_reimbursements(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Tous les remboursements pour la comptabilite, les siens pour les autres.

    Un benevole peut consulter ce qu'on lui a verse — c'est son argent — mais
    rien de ce qui concerne autrui.
    """
    if current_user.role in _ACCOUNTANT_ROLES:
        rows = reimbursement_crud.list_reimbursements(db)
    else:
        rows = reimbursement_crud.list_reimbursements(db, user_id=current_user.id)
    return [_to_out(r) for r in rows]


@router.post(
    "",
    response_model=ReimbursementOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_ACCOUNTANT_ROLES))],
)
def create_reimbursement(
    payload: ReimbursementCreate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    row = reimbursement_crud.create_reimbursement(
        db,
        expense_ids=payload.expense_ids,
        date_remboursement=payload.date_remboursement,
        moyen=payload.moyen,
        etablissement=payload.etablissement,
        approuve_par=payload.approuve_par,
        commentaire=payload.commentaire,
        cree_par=current_user.id,
    )
    return _to_out(row)


@router.get("/{reimbursement_id}/document")
def download_document(
    reimbursement_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    """Telecharge le justificatif.

    Accessible au benevole concerne : c'est la preuve de son remboursement.
    """
    row = reimbursement_crud.get_or_404(db, reimbursement_id)
    if current_user.role not in _ACCOUNTANT_ROLES and row.id_user != current_user.id:
        from app.core.errors import ErrorCode
        from app.core.exceptions import AppException

        raise AppException(ErrorCode.FORBIDDEN)

    chemin = reimbursement_crud.document_path(row, format=format)
    return FileResponse(chemin, media_type=_MIME[format], filename=chemin.name)
