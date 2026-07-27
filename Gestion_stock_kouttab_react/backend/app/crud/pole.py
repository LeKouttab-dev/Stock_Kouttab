"""Referentiel des poles de rattachement."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Invoice, Pole


logger = get_logger("pole")


# Valeurs initiales fournies par le client. La liste est appelee a evoluer :
# elle vit en base, pas dans le code.
DEFAULT_POLES: tuple[tuple[str, int], ...] = (
    ("Pôle événementiel", 1),
    ("Pôle institut", 2),
    ("Local", 3),
)


def ensure_default_poles(db: Session) -> int:
    """Cree les poles par defaut manquants. Idempotent.

    Double emploi assume avec le ``bulk_insert`` de la migration : les tests et
    les environnements de developpement montent le schema via
    ``Base.metadata.create_all`` et ne jouent jamais les migrations — ils
    auraient sinon une table vide.
    """
    existing = {
        nom for (nom,) in db.execute(select(Pole.nom)).all()
    }
    created = 0
    for nom, ordre in DEFAULT_POLES:
        if nom in existing:
            continue
        db.add(Pole(nom=nom, is_default=True, is_active=True, ordre=ordre))
        created += 1
    if created:
        try:
            db.commit()
        except IntegrityError:
            # Course entre deux workers au demarrage : sans importance.
            db.rollback()
            return 0
        logger.info("%d pole(s) par defaut cree(s).", created)
    return created


def list_poles(db: Session, *, include_inactive: bool = False) -> list[Pole]:
    stmt = select(Pole).order_by(Pole.ordre, Pole.nom)
    if not include_inactive:
        stmt = stmt.where(Pole.is_active.is_(True))
    return list(db.execute(stmt).scalars().all())


def get_pole(db: Session, pole_id: int) -> Pole | None:
    return db.get(Pole, pole_id)


def get_pole_or_404(db: Session, pole_id: int) -> Pole:
    pole = get_pole(db, pole_id)
    if pole is None:
        raise AppException(
            ErrorCode.NOT_FOUND, detail="Pole introuvable.", extras={"id": pole_id}
        )
    return pole


def create_pole(db: Session, *, nom: str, ordre: int = 0) -> Pole:
    nom = (nom or "").strip()
    if not nom:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Le nom du pole est requis.")
    pole = Pole(nom=nom, is_default=False, is_active=True, ordre=ordre)
    db.add(pole)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail=f"Le pole '{nom}' existe deja."
        ) from exc
    db.refresh(pole)
    return pole


def update_pole(
    db: Session,
    pole_id: int,
    *,
    nom: str | None = None,
    is_active: bool | None = None,
    ordre: int | None = None,
) -> Pole:
    pole = get_pole_or_404(db, pole_id)
    if nom is not None:
        cleaned = nom.strip()
        if not cleaned:
            raise AppException(
                ErrorCode.VALIDATION_ERROR, detail="Le nom du pole ne peut pas etre vide."
            )
        pole.nom = cleaned
    if is_active is not None:
        pole.is_active = is_active
    if ordre is not None:
        pole.ordre = ordre
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail="Un pole porte deja ce nom."
        ) from exc
    db.refresh(pole)
    return pole


def count_invoices(db: Session, pole_id: int) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(Invoice).where(Invoice.id_pole == pole_id)
        ).scalar_one()
    )


def delete_pole(db: Session, pole_id: int) -> None:
    """Supprime un pole, sauf s'il est par defaut ou deja utilise."""
    pole = get_pole_or_404(db, pole_id)
    if pole.is_default:
        raise AppException(
            ErrorCode.CONFLICT,
            detail=(
                "Ce pole fait partie du referentiel de base et ne peut pas etre "
                "supprime. Desactivez-le pour le retirer du formulaire de depot."
            ),
        )
    used = count_invoices(db, pole_id)
    if used:
        raise AppException(
            ErrorCode.CONFLICT,
            detail=(
                f"Ce pole est reference par {used} facture(s) et ne peut pas etre "
                "supprime. Desactivez-le pour le retirer du formulaire de depot."
            ),
            extras={"invoices": used},
        )
    db.delete(pole)
    db.commit()
