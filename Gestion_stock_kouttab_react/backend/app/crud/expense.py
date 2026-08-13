"""Expense (notes de frais) CRUD."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.workflow import check_expense_transition
from app.core.logger import get_logger
from app.db.models import Expense, ExpenseFile


logger = get_logger("expense")


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
        "id_categorie": expense.id_categorie,
        "categorie": expense.categorie,
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
        "non_lu_demandeur": expense.non_lu_demandeur,
        "archived_at": expense.archived_at,
        "archived_by_name": expense.archiviste.full_name if expense.archiviste else None,
        "user_full_name": user.full_name if user else None,
        "user_email": user.email if user else None,
        # Sert la salutation des courriels : « Assalamu alaykum Omar » plutot
        # qu'une formule anonyme.
        "user_prenom": user.prenom if user else None,
        "user_rib": user.rib if user else None,
        # Presence du document, pas son contenu : la colonne est `deferred`,
        # et lister les notes ne doit pas rapatrier les RIB de tout le monde.
        "user_rib_document_nom": user.rib_document_nom if user else None,
        "files": [
            {
                "id": f.id,
                "nom_fichier": f.nom_fichier,
                "taille_fichier": f.taille_fichier,
                "type_fichier": f.type_fichier,
                "date_upload": f.date_upload,
                "ecarte_at": f.ecarte_at,
                "motif_ecart": f.motif_ecart,
            }
            for f in expense.files
        ],
    }


def list_expenses_for_user(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Les notes du benevole, **sans les archivees**.

    Une note archivee a ete rangee par la comptabilite : la reafficher parmi les
    demandes en cours laisserait croire qu'il reste quelque chose a suivre.
    """
    stmt = (
        select(Expense)
        .options(selectinload(Expense.files), selectinload(Expense.user))
        .where(Expense.id_user == user_id, Expense.archived_at.is_(None))
        .order_by(Expense.date_soumission.desc())
    )
    return [_serialize(e) for e in db.execute(stmt).scalars().all()]


def marquer_lues(db: Session, user_id: int) -> None:
    """Eteint les pastilles du deposant : il vient de voir sa liste.

    Separe de la lecture : `list_expenses_for_user` sert aussi a construire des
    courriels et des exports, ou eteindre un signal n'aurait aucun sens. Seul
    l'endpoint qui repond a un ecran appelle cette fonction.
    """
    db.execute(
        update(Expense)
        .where(Expense.id_user == user_id, Expense.non_lu_demandeur.is_(True))
        .values(non_lu_demandeur=False)
    )
    db.commit()


def list_all_expenses(db: Session, *, include_archived: bool = False) -> list[dict[str, Any]]:
    """Toutes les notes pour la comptabilite.

    Les archivees ne remontent que sur demande explicite : elles n'ont plus rien
    a traiter, et les melanger au courant est exactement ce que l'archivage
    cherche a eviter.
    """
    stmt = (
        select(Expense)
        .options(
            selectinload(Expense.files),
            selectinload(Expense.user),
            selectinload(Expense.archiviste),
        )
        .order_by(Expense.date_soumission.desc())
    )
    if not include_archived:
        stmt = stmt.where(Expense.archived_at.is_(None))
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
    id_categorie: int | None = None,
    categorie: str | None = None,
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
        id_categorie=id_categorie,
        categorie=categorie,
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
    contenu: bytes | None = None,
) -> ExpenseFile:
    file_row = ExpenseFile(
        id_note_de_frais=expense_id,
        nom_fichier=nom_fichier,
        chemin_fichier=chemin_fichier,
        taille_fichier=taille_fichier,
        type_fichier=type_fichier,
        contenu=contenu,
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

    # Le versement fait foi. Repasser une note « Approuvee » alors qu'un
    # remboursement lui est rattache contredirait un justificatif deja emis et
    # envoye — le document porte le montant, la date et l'approbation.
    #
    # Le retour reste ouvert pour une note marquee « Remboursee » SANS
    # versement : c'est le cas des notes passees par l'ancienne liste
    # deroulante, qui seraient sinon bloquees a jamais dans un etat terminal
    # sans document.
    if (
        expense.status == "Remboursée"
        and new_status != "Remboursée"
        and expense.id_remboursement is not None
    ):
        raise AppException(
            ErrorCode.CONFLICT,
            detail=(
                "Cette note est soldee par un remboursement enregistre : son "
                "justificatif a deja ete emis. Corriger le versement plutot que "
                "le statut de la note."
            ),
        )

    # Message explicite plutot que le refus generique du graphe de transitions :
    # « Transition interdite : Approuvee -> Remboursee » se lit comme un bug
    # quand on vient de cliquer sur un choix que l'ecran proposait.
    if new_status == "Remboursée" and expense.status != "Remboursée":
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=(
                "Une note ne se declare pas remboursee : enregistrez le versement "
                "avec le bouton « Rembourser ». Il produit le justificatif (PDF et "
                "tableur), l'envoie, et passe la note a « Remboursee »."
            ),
        )

    check_expense_transition(expense.status, new_status)

    # Le deposant doit savoir qu'il s'est passe quelque chose, y compris quand
    # SEUL le commentaire change : c'est souvent lui qui porte la demande de
    # correction, et il n'allumait rien.
    a_bouge = new_status != expense.status or (comment or "") != (
        expense.commentaires_compta or ""
    )

    if new_status != expense.status:
        expense.validated_by = validated_by
        expense.validated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    expense.status = new_status
    expense.commentaires_compta = comment
    if a_bouge:
        expense.non_lu_demandeur = True
    db.commit()
    db.refresh(expense)
    return expense


def archive_expense(db: Session, expense_id: int, *, user: Any) -> Expense:
    """Range la note sans la detruire.

    Remplace la suppression, qui effacait la ligne **et** les justificatifs. Une
    piece comptable se conserve plusieurs annees : la faire disparaitre sur un
    clic, sans trace de son existence, etait le vrai risque de cet ecran.

    Meme garde-fou qu'avant : seule une note deja remboursee s'archive. Ranger
    une note en cours de traitement la ferait sortir des listes alors que le
    benevole attend encore son argent.
    """
    expense = get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    if user.role not in ("Compta", "Super Admin"):
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Archivage reserve aux comptables."
        )
    if expense.status != "Remboursée":
        raise AppException(ErrorCode.EXPENSE_NOT_DELETABLE)
    if expense.archived_at is None:
        expense.archived_at = datetime.now(timezone.utc)
        expense.archived_by = user.id
        db.commit()
        db.refresh(expense)
    return expense


def supprimer_definitivement(db: Session, expense_id: int, *, user: Any, motif: str) -> None:
    """Efface la note, ses justificatifs, et le versement qu'elle laisserait vide.

    **A n'utiliser que pour du ménage** : notes de test, saisies fautives. Une
    piece comptable reelle s'archive (`archive_expense`), elle ne se detruit pas
    — l'association doit pouvoir la produire plusieurs annees apres.

    Reserve au Super Admin. La comptabilite archive ; detruire n'entre pas dans
    son travail, et un geste irreversible se confie au plus petit cercle
    possible.

    Le motif est journalise AVANT l'effacement : c'est la seule trace qui
    restera de l'existence de la note.
    """
    if user.role != "Super Admin":
        raise AppException(
            ErrorCode.FORBIDDEN,
            detail="Suppression definitive reservee au Super Admin.",
        )
    if not motif.strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Un motif de suppression est obligatoire."
        )

    expense = get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)

    versement = expense.reimbursement
    logger.warning(
        "SUPPRESSION DEFINITIVE note #%s (%s, %s EUR, deposant #%s) par %s — motif : %s",
        expense.id,
        expense.fournisseur or "sans fournisseur",
        expense.montant,
        expense.id_user,
        user.username,
        motif.strip(),
    )

    db.delete(expense)
    db.flush()

    # Un versement dont toutes les notes ont disparu ne documente plus rien : le
    # laisser encombrerait l'ecran d'un remboursement sans contrepartie.
    if versement is not None:
        restantes = db.execute(
            select(func.count())
            .select_from(Expense)
            .where(Expense.id_remboursement == versement.id)
        ).scalar_one()
        if not restantes:
            logger.warning(
                "Remboursement #%s supprime avec sa derniere note.", versement.id
            )
            db.delete(versement)

    db.commit()


def restore_expense(db: Session, expense_id: int, *, role: str) -> Expense:
    """Defait un archivage. C'est ce qui rend l'operation sans danger."""
    expense = get_expense(db, expense_id)
    if not expense:
        raise AppException(ErrorCode.EXPENSE_NOT_FOUND)
    if role not in ("Compta", "Super Admin"):
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Restauration reservee aux comptables."
        )
    expense.archived_at = None
    expense.archived_by = None
    db.commit()
    db.refresh(expense)
    return expense


def ecarter_fichier(
    db: Session, expense_id: int, file_id: int, *, user: Any, motif: str
) -> ExpenseFile:
    """Sort une piece du dossier sans la detruire.

    Une piece illisible ou rattachee a la mauvaise note ne pouvait ni etre
    retiree ni remplacee. L'ecarter la retire de ce que la comptabilite examine
    et de ce qui part au circuit comptable, tout en la gardant en base : une
    piece jointe a un dossier reste une trace, meme refusee.

    Le motif est obligatoire — il est montre au deposant, qui doit savoir ce
    qu'on lui reproche pour redeposer ce qu'il faut.
    """
    if user.role not in ("Compta", "Super Admin"):
        raise AppException(
            ErrorCode.FORBIDDEN, detail="Reserve a la comptabilite."
        )
    if not motif.strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Indiquez pourquoi cette piece est ecartee : le deposant le lira.",
        )

    fichier = _fichier_de_la_note(db, expense_id, file_id)
    fichier.ecarte_at = datetime.now(timezone.utc).replace(tzinfo=None)
    fichier.ecarte_par = user.id
    fichier.motif_ecart = motif.strip()

    # Le deposant doit l'apprendre : c'est une demande d'action.
    note = get_expense(db, expense_id, with_user=False)
    if note is not None:
        note.non_lu_demandeur = True

    db.commit()
    db.refresh(fichier)
    return fichier


def restaurer_fichier(db: Session, expense_id: int, file_id: int, *, role: str) -> ExpenseFile:
    """Defait un ecart. C'est ce qui rend le geste sans danger."""
    if role not in ("Compta", "Super Admin"):
        raise AppException(ErrorCode.FORBIDDEN, detail="Reserve a la comptabilite.")

    fichier = _fichier_de_la_note(db, expense_id, file_id)
    fichier.ecarte_at = None
    fichier.ecarte_par = None
    fichier.motif_ecart = None
    db.commit()
    db.refresh(fichier)
    return fichier


def _fichier_de_la_note(db: Session, expense_id: int, file_id: int) -> ExpenseFile:
    """Charge la piece EN VERIFIANT qu'elle appartient bien a cette note.

    Sans ce controle, l'identifiant d'une piece d'une autre note passerait : les
    deux sont des entiers qui se suivent.
    """
    fichier = db.get(ExpenseFile, file_id)
    if fichier is None or fichier.id_note_de_frais != expense_id:
        raise AppException(ErrorCode.NOT_FOUND, detail="Justificatif introuvable.")
    return fichier


def peut_deposer_une_piece(expense: Expense, *, user: Any) -> bool:
    """Qui peut ajouter un justificatif a une note deja creee.

    Le deposant tant que sa note n'est pas soldee — au-dela, le versement est
    parti et son justificatif est emis. La comptabilite a tout moment : c'est
    elle qui constate le manque.
    """
    if user.role in ("Compta", "Super Admin"):
        return True
    return expense.id_user == user.id and expense.status != "Remboursée"


def list_files(db: Session, expense_id: int) -> list[ExpenseFile]:
    stmt = select(ExpenseFile).where(ExpenseFile.id_note_de_frais == expense_id)
    return list(db.execute(stmt).scalars().all())


def get_file(db: Session, file_id: int) -> ExpenseFile | None:
    return db.get(ExpenseFile, file_id)
