"""Invoice (factures) CRUD."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.workflow import check_invoice_transition
from app.db.models import Invoice, InvoiceFile


def serialize_invoice(invoice: Invoice) -> dict[str, Any]:
    """Representation d'une facture pour l'API.

    Point unique de verite : l'endpoint avait sa propre copie de cette fonction,
    ce qui garantissait qu'un champ ajoute ici manquerait la.
    """
    user = invoice.user
    return {
        "id": invoice.id,
        "id_user": invoice.id_user,
        "commentaire": invoice.commentaire,
        "date_depot": invoice.date_depot,
        "status": invoice.status,
        "commentaires_compta": invoice.commentaires_compta,
        "non_lu_demandeur": invoice.non_lu_demandeur,
        "archived_at": invoice.archived_at,
        "archived_by_name": invoice.archiviste.full_name if invoice.archiviste else None,
        "created_at": invoice.created_at,
        "id_pole": invoice.id_pole,
        "pole": invoice.pole,
        "id_event": invoice.id_event,
        "evenement": invoice.evenement,
        "id_categorie": invoice.id_categorie,
        "categorie": invoice.categorie,
        "date_evenement": invoice.date_evenement,
        "fournisseur": invoice.fournisseur,
        "montant": invoice.montant,
        "validated_by": invoice.validated_by,
        "validated_at": invoice.validated_at,
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


def marquer_lues(db: Session, user_id: int) -> None:
    """Eteint les pastilles du deposant. Cf. `crud.expense.marquer_lues`."""
    db.execute(
        update(Invoice)
        .where(Invoice.id_user == user_id, Invoice.non_lu_demandeur.is_(True))
        .values(non_lu_demandeur=False)
    )
    db.commit()


def list_invoices_for_user(
    db: Session,
    user_id: int,
    *,
    status: str | None = None,
    days: int | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Les factures du deposant, **sans les archivees**.

    Les trois filtres etaient ignores pour un benevole : le menu deroulant de
    statut de son ecran ne faisait donc rien, il changeait seulement la cle de
    cache et redemandait la meme liste.
    """
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.files), selectinload(Invoice.user))
        .where(Invoice.id_user == user_id, Invoice.archived_at.is_(None))
        .order_by(Invoice.date_depot.desc())
    )
    stmt = _appliquer_filtres(stmt, status=status, days=days)
    return _filtrer_par_texte(
        [serialize_invoice(e) for e in db.execute(stmt).scalars().all()], search
    )


def _appliquer_filtres(stmt, *, status: str | None, days: int | None):
    """Statut et anciennete, en SQL. Partages par les deux listes.

    Ils n'etaient appliques que pour la comptabilite : le menu deroulant de
    l'ecran du deposant ne faisait donc rien.
    """
    if status:
        stmt = stmt.where(Invoice.status == status)
    if days is not None and days > 0:
        seuil = datetime.now(timezone.utc).date() - timedelta(days=days)
        stmt = stmt.where(Invoice.date_depot >= seuil)
    return stmt


def _filtrer_par_texte(lignes: list[dict[str, Any]], search: str | None) -> list[dict[str, Any]]:
    """Recherche libre, en Python.

    Elle porte sur le nom des pieces jointes, ce qu'une requete SQL ne fait pas
    sans jointure ; les lignes sont deja chargees, le cout est celui d'un
    parcours de liste. La pousser en SQL demanderait un `exists()` correle —
    utile le jour ou le volume l'exigera, inutile aujourd'hui.
    """
    if not search:
        return lignes
    terme = search.lower()
    return [
        ligne
        for ligne in lignes
        if any(terme in (f.get("nom_fichier") or "").lower() for f in ligne.get("files", []))
        or terme in (ligne.get("commentaire") or "").lower()
        or terme in (ligne.get("fournisseur") or "").lower()
    ]


def list_invoices(
    db: Session,
    *,
    status: str | None = None,
    days: int | None = None,
    search: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Toutes les factures pour la comptabilite.

    Les archivees ne remontent que sur demande explicite, comme pour les notes.
    """
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.files),
            selectinload(Invoice.user),
            selectinload(Invoice.archiviste),
        )
        .order_by(Invoice.date_depot.desc())
    )
    if not include_archived:
        stmt = stmt.where(Invoice.archived_at.is_(None))
    stmt = _appliquer_filtres(stmt, status=status, days=days)
    return _filtrer_par_texte(
        [serialize_invoice(inv) for inv in db.execute(stmt).scalars().all()], search
    )


def archiver(db: Session, invoice_id: int, *, user: Any) -> Invoice:
    """Range la facture sans la detruire.

    Remplace un `DELETE` qui effacait la ligne, ses fichiers et leur contenu en
    base — et que la comptabilite pouvait declencher sur n'importe quel statut,
    « Validee » compris, c'est-a-dire sur une piece deja comptabilisee.
    """
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)

    est_comptable = user.role in ("Compta", "Super Admin")
    if invoice.id_user != user.id and not est_comptable:
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Vous ne pouvez pas archiver cette facture."
        )
    # Le deposant ne range que ce qui n'est pas encore parti au traitement.
    if not est_comptable and invoice.status != "En attente":
        raise AppException(
            ErrorCode.FORBIDDEN,
            detail=(
                "Cette facture est deja prise en charge par la comptabilite. "
                "Contactez le service comptable."
            ),
            extras={"status": invoice.status},
        )

    if invoice.archived_at is None:
        invoice.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
        invoice.archived_by = user.id
        db.commit()
        db.refresh(invoice)
    return invoice


def restaurer(db: Session, invoice_id: int, *, role: str) -> Invoice:
    """Defait un archivage : c'est ce qui rend le geste sans danger."""
    if role not in ("Compta", "Super Admin"):
        raise AppException(ErrorCode.FORBIDDEN, detail="Reserve a la comptabilite.")
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)
    invoice.archived_at = None
    invoice.archived_by = None
    db.commit()
    db.refresh(invoice)
    return invoice


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
    id_pole: int | None = None,
    pole: str | None = None,
    id_event: int | None = None,
    evenement: str | None = None,
    id_categorie: int | None = None,
    categorie: str | None = None,
    date_evenement: date | None = None,
    fournisseur: str | None = None,
    montant: Decimal | None = None,
) -> Invoice:
    invoice = Invoice(
        id_user=user_id,
        commentaire=commentaire,
        date_depot=date_depot or datetime.now(timezone.utc).date(),
        status="En attente",
        id_pole=id_pole,
        pole=pole,
        id_event=id_event,
        evenement=evenement,
        id_categorie=id_categorie,
        categorie=categorie,
        date_evenement=date_evenement,
        fournisseur=(fournisseur or None),
        montant=montant,
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
    contenu: bytes | None = None,
) -> InvoiceFile:
    f = InvoiceFile(
        id_facture=invoice_id,
        nom_fichier=nom_fichier,
        chemin_fichier=chemin_fichier,
        taille_fichier=taille_fichier,
        type_fichier=type_fichier,
        contenu=contenu,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def update_status(
    db: Session,
    invoice_id: int,
    new_status: str,
    *,
    validated_by: int | None = None,
    comment: str | None = None,
) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise AppException(ErrorCode.INVOICE_NOT_FOUND)
    check_invoice_transition(invoice.status, new_status)

    # Comme pour les notes : un commentaire seul est souvent la demande de
    # correction, et doit prevenir le deposant.
    a_bouge = new_status != invoice.status or (
        comment is not None and comment != (invoice.commentaires_compta or "")
    )

    if new_status != invoice.status:
        invoice.validated_by = validated_by
        invoice.validated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    invoice.status = new_status
    if comment is not None:
        invoice.commentaires_compta = comment
    if a_bouge:
        invoice.non_lu_demandeur = True

    db.commit()
    db.refresh(invoice)
    return invoice


def get_file(db: Session, file_id: int) -> InvoiceFile | None:
    return db.get(InvoiceFile, file_id)
