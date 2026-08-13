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
from fastapi import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import invoice as invoice_crud
from app.crud import rattachement as rattachement_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.invoice import InvoiceOut, InvoiceStatusUpdate
from app.services import compta_dispatch, email_layout, outbox
from app.services import email as email_service
from app.services.files import contenu_du_fichier, delete_file, save_upload_file


router = APIRouter(prefix="/invoices", tags=["invoices"])


# Ce que le statut signifie, et ce qu'il reste a faire. Le courriel de facture
# se contentait d'annoncer « nouveau statut : Refusee » : le deposant apprenait
# le refus sans savoir ni pourquoi, ni s'il devait redeposer quelque chose.
_INTRO_STATUT_FACTURE: dict[str, str] = {
    "En attente": "Votre facture est en attente de traitement par la comptabilite.",
    "En cours de traitement": "Votre facture est prise en charge par la comptabilite.",
    "Validée": "Votre facture a ete validee par la comptabilite.",
    "Refusée": "Votre facture n'a pas ete retenue par la comptabilite.",
}

_SUITE_STATUT_FACTURE: dict[str, str] = {
    "En cours de traitement": "Aucune action de votre part n'est necessaire pour l'instant.",
    "Validée": "Elle est comptabilisee ; rien de plus n'est attendu de vous.",
    "Refusée": (
        "Le motif figure ci-dessus. Vous pouvez deposer une nouvelle piece corrigee "
        "depuis « Depot de factures »."
    ),
}

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
    # Optionnelle depuis l'introduction des poles sans evenement : sous « Local »
    # il n'y a pas d'evenement, donc pas de date d'evenement. L'obligation est
    # portee par la resolution du rattachement, qui sait ce que le pole attend.
    date_evenement: str | None = Form(default=None),
    id_event: int | None = Form(default=None),
    evenement_libre: str | None = Form(default=None),
    id_categorie: int | None = Form(default=None),
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

    # Le rattachement est resolu AVANT toute ecriture : il compose le nom du
    # fichier envoye au comptable, une erreur ici doit etre signalee au deposant
    # plutot que produire une piece mal nommee.
    rattachement = rattachement_crud.resoudre(
        db,
        id_pole=id_pole,
        id_event=id_event,
        evenement_libre=evenement_libre,
        id_categorie=id_categorie,
        date_evenement=_parse_optional_date(date_evenement),
    )

    invoice = invoice_crud.create_invoice(
        db,
        user_id=current_user.id,
        commentaire=commentaire,
        date_depot=_parse_optional_date(date_depot),
        id_pole=rattachement.id_pole,
        pole=rattachement.pole,
        id_event=rattachement.id_event,
        evenement=rattachement.evenement,
        id_categorie=rattachement.id_categorie,
        categorie=rattachement.categorie,
        date_evenement=rattachement.date_evenement,
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
            contenu=meta.get("contenu"),  # type: ignore[arg-type]
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
    background.add_task(
        _notify_new_invoice_safe, current_user.full_name, commentaire, current_user.email
    )
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
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user),
) -> Any:
    avant = invoice_crud.get_invoice(db, invoice_id)
    ancien_statut = avant.status if avant else None

    invoice = invoice_crud.update_status(
        db,
        invoice_id,
        payload.status,
        validated_by=current_user.id,
        comment=payload.commentaires_compta,
    )

    # Le deposant est prevenu, comme sur les notes de frais. Le corps etait
    # ecrit en dur, en texte brut : ni salutation, ni fournisseur, ni montant,
    # ni ce qu'il reste a faire. Il passe desormais par le meme gabarit, et par
    # la file — un refus qui n'arrive pas laisse le deposant sans rien.
    destinataire = getattr(invoice.user, "email", None) if invoice.user else None
    if destinataire and email_service.doit_notifier_du_statut(
        destinataire, current_user.email
    ):
        if payload.status != ancien_statut:
            sujet = f"Votre facture #{invoice.id} — {payload.status}"
            introduction = _INTRO_STATUT_FACTURE.get(
                payload.status, f"Votre facture #{invoice.id} a ete mise a jour."
            )
        else:
            sujet = f"Votre facture #{invoice.id} — message de la comptabilite"
            introduction = (
                "La comptabilite a laisse un commentaire sur votre facture. "
                "Son statut n'a pas change."
            )

        envoi = outbox.enqueue(
            db,
            kind="statut_facture",
            entity_type="invoice",
            entity_id=invoice.id,
            recipients=[destinataire],
            subject=sujet,
            body=email_layout.composer(
                prenom=getattr(invoice.user, "prenom", None),
                introduction=introduction,
                blocs=[
                    ("Facture", f"#{invoice.id}"),
                    ("Fournisseur", invoice.fournisseur),
                    ("Rattachement", invoice.evenement or invoice.categorie),
                    ("Montant", invoice.montant),
                    ("Statut", payload.status),
                    ("Commentaire", payload.commentaires_compta),
                ],
                conclusion=_SUITE_STATUT_FACTURE.get(payload.status),
            ),
            triggered_by=current_user.id,
        )
        background.add_task(outbox.try_send_now, envoi.id)

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
    return _servir(file_row)


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


async def _notify_new_invoice_safe(
    user_full_name: str, comment: str | None, auteur_email: str | None = None
) -> None:
    db = SessionLocal()
    try:
        await email_service.send_invoice_notification(
            db, user_full_name=user_full_name, comment=comment, auteur_email=auteur_email
        )
    finally:
        db.close()


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
