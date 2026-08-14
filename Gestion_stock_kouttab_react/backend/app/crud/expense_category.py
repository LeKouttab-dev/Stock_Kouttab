"""Referentiel des categories de depense (hors evenement).

Calque sur ``crud/pole.py`` : meme cycle de vie, meme refus de supprimer ce qui
est deja reference, meme desactivation en remplacement de la suppression.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Expense, ExpenseCategory, Invoice


logger = get_logger("expense_category")


# Liste fournie par le client. Elle vit en base : la faire evoluer ne doit pas
# demander un deploiement.
#
# `Autre` porte volontairement un ordre tres eleve : c'est le choix de repli,
# et il doit rester en fin de liste quelles que soient les categories ajoutees
# ensuite. Une categorie fourre-tout en milieu de liste se choisit par defaut.
DEFAULT_CATEGORIES: tuple[tuple[str, int], ...] = (
    ("Courses", 1),
    ("Stock goûter", 2),
    ("Achat buvette", 3),
    ("Achat matériel", 4),
    ("Mobilier, immobilier et petit équipement", 5),
    ("Fournitures administratives", 6),
    ("Entretien", 7),
    ("Réceptions (repas, déplacements, nourriture)", 8),
    ("Autre", 99),
)


def ensure_default_categories(db: Session) -> int:
    """Cree les categories par defaut manquantes. Idempotent.

    Double emploi assume avec la migration, pour la meme raison que les poles :
    les tests et le developpement montent le schema par ``create_all`` et ne
    jouent jamais les migrations.
    """
    existing = {nom for (nom,) in db.execute(select(ExpenseCategory.nom)).all()}
    created = 0
    for nom, ordre in DEFAULT_CATEGORIES:
        if nom in existing:
            continue
        db.add(ExpenseCategory(nom=nom, is_default=True, is_active=True, ordre=ordre))
        created += 1
    if created:
        try:
            db.commit()
        except IntegrityError:
            # Course entre deux workers au demarrage : sans importance.
            db.rollback()
            return 0
        logger.info("%d categorie(s) de depense par defaut cree(s).", created)
    return created


def list_categories(
    db: Session, *, include_inactive: bool = False
) -> list[ExpenseCategory]:
    stmt = select(ExpenseCategory).order_by(ExpenseCategory.ordre, ExpenseCategory.nom)
    if not include_inactive:
        stmt = stmt.where(ExpenseCategory.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def get_category(db: Session, category_id: int) -> ExpenseCategory | None:
    return db.get(ExpenseCategory, category_id)


def get_category_or_404(db: Session, category_id: int) -> ExpenseCategory:
    categorie = get_category(db, category_id)
    if categorie is None:
        raise AppException(
            ErrorCode.NOT_FOUND,
            detail="Categorie introuvable.",
            extras={"id": category_id},
        )
    return categorie


def create_category(db: Session, *, nom: str, ordre: int = 0) -> ExpenseCategory:
    nom = (nom or "").strip()
    if not nom:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Le nom de la categorie est requis."
        )
    categorie = ExpenseCategory(nom=nom, is_default=False, is_active=True, ordre=ordre)
    db.add(categorie)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail=f"La categorie '{nom}' existe deja."
        ) from exc
    db.refresh(categorie)
    return categorie


def update_category(
    db: Session,
    category_id: int,
    *,
    nom: str | None = None,
    is_active: bool | None = None,
    ordre: int | None = None,
) -> ExpenseCategory:
    categorie = get_category_or_404(db, category_id)
    if nom is not None:
        cleaned = nom.strip()
        if not cleaned:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                detail="Le nom de la categorie ne peut pas etre vide.",
            )
        categorie.nom = cleaned
    if is_active is not None:
        categorie.is_active = is_active
    if ordre is not None:
        categorie.ordre = ordre
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail="Une categorie porte deja ce nom."
        ) from exc
    db.refresh(categorie)
    return categorie


def count_usages(db: Session, category_id: int) -> int:
    """Nombre de pieces comptables rattachees a cette categorie."""
    notes = db.execute(
        select(func.count())
        .select_from(Expense)
        .where(Expense.id_categorie == category_id)
    ).scalar_one()
    factures = db.execute(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.id_categorie == category_id)
    ).scalar_one()
    return int(notes) + int(factures)


def delete_category(db: Session, category_id: int) -> None:
    """Supprime une categorie, sauf si elle est par defaut ou deja utilisee."""
    categorie = get_category_or_404(db, category_id)
    if categorie.is_default:
        raise AppException(
            ErrorCode.CONFLICT,
            detail=(
                "Cette categorie fait partie du referentiel de base et ne peut pas "
                "etre supprimee. Desactivez-la pour la retirer du formulaire."
            ),
        )
    used = count_usages(db, category_id)
    if used:
        raise AppException(
            ErrorCode.CONFLICT,
            detail=(
                f"Cette categorie est referencee par {used} piece(s) comptable(s) "
                "et ne peut pas etre supprimee. Desactivez-la pour la retirer du "
                "formulaire."
            ),
            extras={"usages": used},
        )
    db.delete(categorie)
    db.commit()


def resolve_categorie(db: Session, *, id_categorie: int | None) -> ExpenseCategory:
    """Controle la categorie fournie. Elle est exigee sous **tous** les poles.

    Resolue **avant** toute ecriture, comme le pole et l'evenement : la
    categorie compose le nom du fichier envoye au comptable sous les poles sans
    evenement, et une erreur doit revenir au deposant plutot que de produire une
    piece mal nommee.

    Elle etait auparavant refusee sous les poles evenementiels, ou l'evenement
    tenait lieu de rattachement. Mais l'evenement dit *a quelle occasion* la
    depense a eu lieu, pas *ce qui a ete achete* : le comptable a besoin des
    deux pour imputer, et il n'avait la nature de la depense que sur la moitie
    des pieces.
    """
    if id_categorie is None:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Categorie obligatoire.",
        )

    categorie = get_category_or_404(db, id_categorie)
    if not categorie.is_active:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"La categorie '{categorie.nom}' n'est plus proposee.",
        )
    return categorie


__all__ = [
    "DEFAULT_CATEGORIES",
    "count_usages",
    "create_category",
    "delete_category",
    "ensure_default_categories",
    "get_category",
    "get_category_or_404",
    "list_categories",
    "resolve_categorie",
    "update_category",
]
