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


# Referentiel fourni par le client. Il vit en base et non dans le code : la
# liste a deja change une fois et changera encore.
#
# Colonnes : nom, ordre, se rattache-t-il a un evenement, famille d'evenements.
# Les poles EV sont declines par famille et ne proposent que les evenements de
# la leur ; les autres demandent une categorie (courses, gouter, materiel...),
# car une depense de fonctionnement n'a pas d'evenement.
DEFAULT_POLES: tuple[tuple[str, int, bool, str | None], ...] = (
    ("EV(T)", 1, True, "T"),
    ("EV(G)", 2, True, "G"),
    ("EV(J)", 3, True, "J"),
    ("Frais généraux", 4, False, None),
    ("Institut", 5, False, None),
    ("Halaqa", 6, False, None),
    ("Séjour annuel", 7, False, None),
    ("ESP-VT", 8, False, None),
)

# Poles du referentiel precedent, remplaces par la liste ci-dessus. Ils sont
# desactives et non supprimes : les factures deja deposees les referencent.
POLES_RETIRES: tuple[str, ...] = ("Pôle événementiel", "Local")

# Renommages : meme pole, meme identifiant, donc les pieces deja rattachees le
# restent. Recreer « Institut » a neuf les aurait laissees orphelines.
POLES_RENOMMES: tuple[tuple[str, str], ...] = (("Pôle institut", "Institut"),)


def ensure_default_poles(db: Session) -> int:
    """Cree les poles par defaut manquants. Idempotent.

    Double emploi assume avec le ``bulk_insert`` de la migration : les tests et
    les environnements de developpement montent le schema via
    ``Base.metadata.create_all`` et ne jouent jamais les migrations — ils
    auraient sinon une table vide.
    """
    # Renommages d'abord : sans cela, « Institut » serait cree en double a cote
    # de « Pôle institut », et les factures deja deposees resteraient sur
    # l'ancien.
    for ancien, nouveau in POLES_RENOMMES:
        pole = db.execute(select(Pole).where(Pole.nom == ancien)).scalar_one_or_none()
        deja_present = db.execute(
            select(Pole).where(Pole.nom == nouveau)
        ).scalar_one_or_none()
        if pole is not None and deja_present is None:
            pole.nom = nouveau
            db.commit()

    existing = {
        nom for (nom,) in db.execute(select(Pole.nom)).all()
    }
    created = 0
    for nom, ordre, requiert_evenement, type_evenement in DEFAULT_POLES:
        if nom in existing:
            continue
        db.add(
            Pole(
                nom=nom,
                is_default=True,
                is_active=True,
                ordre=ordre,
                requiert_evenement=requiert_evenement,
                type_evenement=type_evenement,
            )
        )
        created += 1
    # Poles du referentiel precedent : desactives, jamais supprimes. Ils
    # disparaissent du formulaire de depot et restent lisibles sur les pieces
    # deja transmises au comptable.
    for nom in POLES_RETIRES:
        pole = db.execute(select(Pole).where(Pole.nom == nom)).scalar_one_or_none()
        if pole is not None and pole.is_active:
            pole.is_active = False
            created += 1  # force le commit ci-dessous

    if created:
        try:
            db.commit()
        except IntegrityError:
            # Course entre deux workers au demarrage : sans importance.
            db.rollback()
            return 0
        logger.info("Referentiel des poles mis a jour (%d changement(s)).", created)
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


def create_pole(
    db: Session,
    *,
    nom: str,
    ordre: int = 0,
    requiert_evenement: bool = False,
    type_evenement: str | None = None,
) -> Pole:
    nom = (nom or "").strip()
    if not nom:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Le nom du pole est requis.")
    pole = Pole(
        nom=nom,
        is_default=False,
        is_active=True,
        ordre=ordre,
        requiert_evenement=requiert_evenement,
        type_evenement=(type_evenement or None),
    )
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
    requiert_evenement: bool | None = None,
    type_evenement: str | None = None,
) -> Pole:
    pole = get_pole_or_404(db, pole_id)
    if requiert_evenement is not None:
        pole.requiert_evenement = requiert_evenement
    if type_evenement is not None:
        # Chaine vide = retirer le filtre, et non « ne rien changer ».
        pole.type_evenement = type_evenement.strip() or None
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
