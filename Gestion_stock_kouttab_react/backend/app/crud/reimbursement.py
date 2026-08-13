"""Remboursements groupes : un versement solde plusieurs notes de frais.

La comptabilite ne rembourse pas note par note — elle vire un montant a un
benevole. Ce module cree ce versement, produit le justificatif (PDF + tableur)
et le met en file vers la comptabilite.

Tout se joue dans **une seule transaction** : le statut des notes, le
remboursement et les documents. Un echec a mi-chemin laisserait des notes
marquees « Rembourse » sans justificatif, ou l'inverse — deux etats qu'aucun
ecran ne permettrait de rattraper.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.core.money import total_a_rembourser
from app.core.reimbursement_options import (
    APPROBATEUR_PAR_DEFAUT,
    ETABLISSEMENT_PAR_DEFAUT,
    MOYEN_PAR_DEFAUT,
    valider_etablissement,
    valider_moyen,
)
from app.db.models import Admin, Expense, Reimbursement
from app.services import naming, outbox, reimbursement_doc
from app.services.email_layout import composer


logger = get_logger("reimbursement")

KIND_REIMBURSEMENT = "reimbursement_compta"
STATUT_REMBOURSE = "Remboursée"
STATUT_APPROUVE = "Approuvée"


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def get_reimbursement(db: Session, reimbursement_id: int) -> Reimbursement | None:
    return db.execute(
        select(Reimbursement)
        .options(
            selectinload(Reimbursement.user),
            selectinload(Reimbursement.expenses),
        )
        .where(Reimbursement.id == reimbursement_id)
    ).scalar_one_or_none()


def get_or_404(db: Session, reimbursement_id: int) -> Reimbursement:
    row = get_reimbursement(db, reimbursement_id)
    if row is None:
        raise AppException(ErrorCode.NOT_FOUND, detail="Remboursement introuvable.")
    return row


def list_reimbursements(db: Session, *, user_id: int | None = None) -> list[Reimbursement]:
    stmt = (
        select(Reimbursement)
        .options(selectinload(Reimbursement.user), selectinload(Reimbursement.expenses))
        .order_by(Reimbursement.date_remboursement.desc(), Reimbursement.id.desc())
    )
    if user_id is not None:
        stmt = stmt.where(Reimbursement.id_user == user_id)
    return list(db.execute(stmt).scalars().all())


def list_by_volunteer(db: Session) -> list[dict[str, Any]]:
    """Notes de frais regroupees par benevole, avec ses totaux.

    Une seule requete plutot qu'une par benevole : la base est distante
    (O2Switch), et chaque aller-retour coute (cf. CLAUDE.md §14).
    """
    notes = list(
        db.execute(
            select(Expense)
            .options(selectinload(Expense.user), selectinload(Expense.files))
            .order_by(Expense.date_depense.desc(), Expense.id.desc())
        )
        .scalars()
        .all()
    )

    par_benevole: dict[int, dict[str, Any]] = {}
    for note in notes:
        fiche = par_benevole.setdefault(
            note.id_user,
            {
                "id_user": note.id_user,
                "nom_complet": note.user.full_name if note.user else None,
                "email": note.user.email if note.user else None,
                "notes": [],
            },
        )
        fiche["notes"].append(note)

    fiches = list(par_benevole.values())
    for fiche in fiches:
        a_rembourser = [n for n in fiche["notes"] if n.status == STATUT_APPROUVE]
        fiche["nb_notes"] = len(fiche["notes"])
        fiche["nb_a_rembourser"] = len(a_rembourser)
        # Ce que l'association doit **aujourd'hui** : seules les notes
        # approuvees et non encore payees entrent dans ce total.
        fiche["total_du"] = total_a_rembourser(a_rembourser)
    # Le benevole qui attend le plus remonte en tete : c'est lui qu'il faut
    # traiter en premier.
    fiches.sort(key=lambda f: (-f["nb_a_rembourser"], f["nom_complet"] or ""))
    return fiches


# ---------------------------------------------------------------------------
# Ecriture
# ---------------------------------------------------------------------------


def _controler_les_notes(db: Session, expense_ids: list[int]) -> tuple[Admin, list[Expense]]:
    """Verifie que ces notes forment un remboursement coherent.

    Tout est refuse d'un bloc plutot que partiellement : rembourser trois notes
    sur quatre en silence, parce que la quatrieme avait deja ete payee, ne se
    verrait qu'au moment du rapprochement bancaire.
    """
    if not expense_ids:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Aucune note de frais selectionnee."
        )

    notes = list(
        db.execute(
            select(Expense)
            .options(selectinload(Expense.user))
            .where(Expense.id.in_(expense_ids))
        )
        .scalars()
        .all()
    )

    manquantes = set(expense_ids) - {n.id for n in notes}
    if manquantes:
        raise AppException(
            ErrorCode.NOT_FOUND,
            detail=f"Note(s) de frais introuvable(s) : {sorted(manquantes)}.",
        )

    proprietaires = {n.id_user for n in notes}
    if len(proprietaires) > 1:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=(
                "Un remboursement ne concerne qu'un seul benevole : "
                "ces notes appartiennent a plusieurs personnes."
            ),
        )

    deja_payees = [n.id for n in notes if n.id_remboursement is not None]
    if deja_payees:
        raise AppException(
            ErrorCode.CONFLICT,
            detail=f"Note(s) deja remboursee(s) : {sorted(deja_payees)}.",
            extras={"expenses": sorted(deja_payees)},
        )

    non_approuvees = [n.id for n in notes if n.status != STATUT_APPROUVE]
    if non_approuvees:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=(
                "Seules des notes « Approuvée » peuvent etre remboursees. "
                f"A corriger : {sorted(non_approuvees)}."
            ),
            extras={"expenses": sorted(non_approuvees)},
        )

    benevole = notes[0].user
    if benevole is None:
        raise AppException(ErrorCode.USER_NOT_FOUND, detail="Benevole introuvable.")
    return benevole, notes


def _ecrire_documents(
    reimbursement: Reimbursement, benevole: Admin, notes: list[Expense]
) -> tuple[Path, Path]:
    """Produit PDF et tableur dans OUTBOX_DIR.

    **Hors de `uploads/`** : ces fichiers portent des noms previsibles, et le
    serveur web laisse passer `uploads/`. Meme regle que les pieces jointes du
    circuit comptable (`compta_dispatch._outbox_dir`).
    """
    donnees = reimbursement_doc.DonneesJustificatif(
        benevole=benevole,
        notes=notes,
        date_remboursement=reimbursement.date_remboursement,
        moyen=reimbursement.moyen,
        etablissement=reimbursement.etablissement,
        approuve_par=reimbursement.approuve_par,
        commentaire=reimbursement.commentaire,
    )

    dossier = settings.outbox_path / "reimbursement" / str(reimbursement.id)
    dossier.mkdir(parents=True, exist_ok=True)

    # Nom ASCII pur : un client de messagerie deforme les accents dans le nom
    # d'une piece jointe (cf. services/naming.py).
    racine = naming.build_attachment_stem(
        ["NDF", benevole.full_name or benevole.username],
        reimbursement.date_remboursement,
    )
    chemin_pdf = dossier / f"{racine}.pdf"
    chemin_xlsx = dossier / f"{racine}.xlsx"

    chemin_pdf.write_bytes(reimbursement_doc.construire_pdf(donnees))
    chemin_xlsx.write_bytes(reimbursement_doc.construire_xlsx(donnees))
    logger.info("Justificatif de remboursement pret : %s", chemin_pdf.name)
    return chemin_pdf, chemin_xlsx


def create_reimbursement(
    db: Session,
    *,
    expense_ids: list[int],
    date_remboursement: date_type | None = None,
    moyen: str | None = None,
    etablissement: str | None = None,
    approuve_par: str | None = None,
    commentaire: str | None = None,
    cree_par: int | None = None,
) -> Reimbursement:
    """Solde plusieurs notes d'un benevole par un versement unique."""
    benevole, notes = _controler_les_notes(db, expense_ids)

    reimbursement = Reimbursement(
        id_user=benevole.id,
        date_remboursement=date_remboursement or date_type.today(),
        moyen=valider_moyen(moyen or MOYEN_PAR_DEFAUT),
        etablissement=valider_etablissement(etablissement or ETABLISSEMENT_PAR_DEFAUT),
        approuve_par=(approuve_par or APPROBATEUR_PAR_DEFAUT).strip()
        or APPROBATEUR_PAR_DEFAUT,
        montant_total=total_a_rembourser(notes),
        commentaire=commentaire,
        cree_par=cree_par,
    )
    db.add(reimbursement)
    db.flush()  # attribue l'identifiant, qui nomme le dossier des documents

    for note in notes:
        note.status = STATUT_REMBOURSE
        note.id_remboursement = reimbursement.id

    chemin_pdf, chemin_xlsx = _ecrire_documents(reimbursement, benevole, notes)
    reimbursement.chemin_pdf = str(chemin_pdf)
    reimbursement.chemin_xlsx = str(chemin_xlsx)
    # Le contenu en base fait autorite ; le disque n'est plus qu'un cache, utile
    # a la file d'envoi qui joint des fichiers.
    reimbursement.contenu_pdf = chemin_pdf.read_bytes()
    reimbursement.contenu_xlsx = chemin_xlsx.read_bytes()

    db.commit()
    db.refresh(reimbursement)

    _mettre_en_file(db, reimbursement, benevole, notes, triggered_by=cree_par)
    return reimbursement


def _mettre_en_file(
    db: Session,
    reimbursement: Reimbursement,
    benevole: Admin,
    notes: list[Expense],
    *,
    triggered_by: int | None,
) -> None:
    """Depose le justificatif dans la file, pour la comptabilite ET le benevole.

    Apres le commit : la file gere elle-meme ses tentatives, et un SMTP
    indisponible ne doit pas annuler un remboursement deja enregistre.

    **Le benevole ne recevait rien.** Seul `COMPTA_EMAIL` etait destinataire : il
    apprenait son remboursement en consultant son compte bancaire, et n'avait
    aucune piece a produire — alors que le document porte son nom, le montant et
    l'approbation.

    Deux envois plutot qu'un seul a deux destinataires : le comptable archive une
    operation, le benevole recoit une preuve. Les deux ne se disent pas de la
    meme facon, et mettre le benevole en copie d'un message ecrit pour la
    comptabilite se voit tout de suite.
    """
    identite = benevole.full_name or benevole.username
    sujet = (
        f"[Remboursement] {identite} — "
        f"{reimbursement.montant_total:.2f} EUR — "
        f"{reimbursement.date_remboursement.strftime('%d/%m/%Y')}"
    )
    details = [
        ("Montant", reimbursement.montant_total),
        ("Notes soldees", len(notes)),
        ("Emis le", reimbursement.date_remboursement),
        ("Moyen", reimbursement.moyen),
        ("Etablissement", reimbursement.etablissement),
        ("Approuve par", reimbursement.approuve_par),
    ]
    pieces = [Path(reimbursement.chemin_pdf), Path(reimbursement.chemin_xlsx)]

    def _deposer(destinataires: list[str], corps: str) -> None:
        if not destinataires:
            # Ne pas mettre en file un envoi sans destinataire : il resterait
            # « en attente » indefiniment, a encombrer l'ecran de diagnostic.
            return
        outbox.enqueue(
            db,
            kind=KIND_REIMBURSEMENT,
            entity_type="reimbursement",
            entity_id=reimbursement.id,
            recipients=destinataires,
            subject=sujet,
            body=corps,
            attachments=pieces,
            triggered_by=triggered_by,
        )

    _deposer(
        list(settings.compta_emails),
        composer(
            introduction="Un remboursement vient d'etre enregistre dans l'application.",
            blocs=[("Benevole", identite), *details],
            conclusion="Le detail figure dans le justificatif joint (PDF et tableur).",
        ),
    )

    _deposer(
        [benevole.email] if benevole.email else [],
        composer(
            prenom=benevole.prenom,
            introduction=(
                "Vos notes de frais viennent d'etre remboursees. "
                "Le justificatif est joint a ce message, en PDF et en tableur."
            ),
            blocs=details,
            conclusion=(
                "Vous retrouvez ce justificatif a tout moment dans l'application, "
                "onglet « Remboursements » de vos notes de frais."
            ),
        ),
    )


def contenu_document(reimbursement: Reimbursement, *, format: str) -> tuple[bytes, str]:
    """Rend le justificatif et son nom de fichier.

    La base fait autorite : c'est la seule copie sauvegardee. Le repli sur le
    disque couvre les remboursements emis avant la migration `d0f7b2c5e8a9`, sur
    une machine ou le volume est encore en place.
    """
    en_base = reimbursement.contenu_pdf if format == "pdf" else reimbursement.contenu_xlsx
    chemin = reimbursement.chemin_pdf if format == "pdf" else reimbursement.chemin_xlsx
    nom = Path(chemin).name if chemin else f"justificatif.{format}"

    if en_base:
        return en_base, nom

    fichier = Path(chemin) if chemin else None
    if fichier is not None and fichier.is_file():
        return fichier.read_bytes(), nom

    raise AppException(
        ErrorCode.NOT_FOUND, detail="Aucun justificatif pour ce remboursement."
    )


def a_un_document(reimbursement: Reimbursement, *, format: str) -> bool:
    """Presence reelle, et non presence du chemin.

    `bool(chemin_pdf)` renvoyait vrai pour un fichier disparu : l'ecran promettait
    un telechargement qui rendait un 404.
    """
    if (reimbursement.contenu_pdf if format == "pdf" else reimbursement.contenu_xlsx):
        return True
    chemin = reimbursement.chemin_pdf if format == "pdf" else reimbursement.chemin_xlsx
    return bool(chemin) and Path(chemin).is_file()


def total_rembourse(db: Session, user_id: int) -> Decimal:
    """Somme deja versee a un benevole, tous remboursements confondus."""
    valeur = db.execute(
        select(func.coalesce(func.sum(Reimbursement.montant_total), 0)).where(
            Reimbursement.id_user == user_id
        )
    ).scalar_one()
    return Decimal(str(valeur))


__all__ = [
    "KIND_REIMBURSEMENT",
    "create_reimbursement",
    "document_path",
    "get_or_404",
    "get_reimbursement",
    "list_by_volunteer",
    "list_reimbursements",
    "total_rembourse",
]
