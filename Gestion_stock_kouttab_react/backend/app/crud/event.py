"""Referentiel des evenements, synchronise depuis HelloAsso."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Event, Expense, Invoice


logger = get_logger("event")


SOURCE_HELLOASSO = "helloasso"
SOURCE_MANUAL = "manuel"

# Etats HelloAsso qui retirent un formulaire de la circulation.
_INACTIVE_STATES = {"Deleted", "Disabled", "Draft"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _first_of(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Premiere cle non vide parmi ``keys``.

    Le schema de reponse de ``GET /forms`` n'est pas documente par HelloAsso :
    on accepte plusieurs noms plausibles plutot que de casser au premier
    changement d'appellation.
    """
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return default


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    # Formats ISO usuels, avec ou sans fuseau.
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ---- Lecture ----------------------------------------------------------------


def list_events(
    db: Session,
    *,
    include_inactive: bool = False,
    search: str | None = None,
    limit: int = 500,
) -> list[Event]:
    # `nullslast()` genere `NULLS LAST`, syntaxe PostgreSQL que **MariaDB
    # refuse** (erreur 1064). SQLite l'accepte, si bien que le tri passait en
    # developpement et renvoyait une 500 en production : la liste des evenements
    # restait vide au depot d'une facture, sans message.
    #
    # `col IS NULL` s'evalue a 0 ou 1 : trier dessus en premier place les dates
    # renseignees avant les dates absentes, ce que `NULLS LAST` exprime ailleurs.
    stmt = (
        select(Event)
        .order_by(
            Event.date_evenement.is_(None),
            Event.date_evenement.desc(),
            Event.nom,
        )
        .limit(limit)
    )
    if not include_inactive:
        stmt = stmt.where(Event.is_active.is_(True))
    if search:
        stmt = stmt.where(Event.nom.ilike(f"%{search.strip()}%"))
    return list(db.execute(stmt).scalars().all())


def get_event(db: Session, event_id: int) -> Event | None:
    return db.get(Event, event_id)


def get_event_or_404(db: Session, event_id: int) -> Event:
    event = get_event(db, event_id)
    if event is None:
        raise AppException(
            ErrorCode.NOT_FOUND, detail="Evenement introuvable.", extras={"id": event_id}
        )
    return event


def resolve_event(
    db: Session, *, event_id: int | None, evenement_libre: str | None
) -> tuple[int | None, str]:
    """Valide le couple (evenement du referentiel | saisie libre).

    Exactement l'un des deux doit etre fourni. La saisie libre est le cas normal
    pour une depense sans evenement HelloAsso (electricite, achat courant), pas
    une degradation.
    """
    libre = (evenement_libre or "").strip()
    if event_id is not None and libre:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Choisissez un evenement de la liste OU saisissez-en un, pas les deux.",
        )
    if event_id is None and not libre:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="L'evenement est obligatoire.",
        )
    if event_id is not None:
        event = get_event_or_404(db, event_id)
        return event.id, event.nom
    return None, libre


# ---- Ecriture manuelle ------------------------------------------------------


def create_manual_event(
    db: Session,
    *,
    nom: str,
    date_evenement: date | None = None,
    type_ev: str | None = None,
) -> Event:
    cleaned = (nom or "").strip()
    if not cleaned:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="Le nom de l'evenement est requis."
        )
    event = Event(
        nom=cleaned,
        date_evenement=date_evenement,
        type_ev=(type_ev or None),
        source=SOURCE_MANUAL,
        is_active=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(
    db: Session,
    event_id: int,
    *,
    nom: str | None = None,
    date_evenement: date | None = None,
    type_ev: str | None = None,
    is_active: bool | None = None,
) -> Event:
    event = get_event_or_404(db, event_id)
    if type_ev is not None:
        # Chaine vide = retirer la famille, et non « ne rien changer ».
        event.type_ev = type_ev.strip() or None
    if nom is not None:
        cleaned = nom.strip()
        if not cleaned:
            raise AppException(
                ErrorCode.VALIDATION_ERROR, detail="Le nom ne peut pas etre vide."
            )
        event.nom = cleaned
    if date_evenement is not None:
        event.date_evenement = date_evenement
    if is_active is not None:
        event.is_active = is_active
    db.commit()
    db.refresh(event)
    return event


def count_usages(db: Session, event_id: int) -> int:
    invoices = db.execute(
        select(func.count()).select_from(Invoice).where(Invoice.id_event == event_id)
    ).scalar_one()
    expenses = db.execute(
        select(func.count()).select_from(Expense).where(Expense.id_event == event_id)
    ).scalar_one()
    return int(invoices) + int(expenses)


def delete_event(db: Session, event_id: int) -> None:
    event = get_event_or_404(db, event_id)
    used = count_usages(db, event_id)
    if used:
        raise AppException(
            ErrorCode.CONFLICT,
            detail=(
                f"Cet evenement est reference par {used} piece(s) comptable(s) et "
                "ne peut pas etre supprime. Desactivez-le pour le retirer des "
                "formulaires de depot."
            ),
            extras={"usages": used},
        )
    db.delete(event)
    db.commit()


# ---- Synchronisation HelloAsso ----------------------------------------------


def sync_events_from_helloasso(db: Session, forms: list[dict[str, Any]]) -> dict[str, Any]:
    """Upsert des formulaires HelloAsso dans le referentiel local.

    Regles :
    - cle ``(form_type, form_slug)`` ;
    - un evenement ``source='manuel'`` n'est jamais touche ;
    - un formulaire retire cote HelloAsso est desactive, jamais supprime : des
      pieces comptables le referencent.
    """
    created = updated = skipped = 0
    errors: list[str] = []

    for form in forms:
        try:
            slug = _first_of(form, "formSlug", "slug", "urlSlug")
            form_type = _first_of(form, "formType", "type", default="Event")
            nom = _first_of(form, "title", "name", "formName", "label")
            if not slug or not nom:
                skipped += 1
                continue

            state = _first_of(form, "state", "formState", "status")
            start = _parse_date(
                _first_of(form, "startDate", "start_date", "beginningDate")
            )
            end = _parse_date(_first_of(form, "endDate", "end_date"))
            url = _first_of(form, "url", "publicUrl", "formUrl")

            existing = db.execute(
                select(Event).where(
                    Event.helloasso_form_type == form_type,
                    Event.helloasso_form_slug == slug,
                )
            ).scalar_one_or_none()

            if existing is None:
                db.add(
                    Event(
                        helloasso_form_slug=slug,
                        helloasso_form_type=form_type,
                        nom=str(nom)[:255],
                        date_evenement=start,
                        date_fin=end,
                        url=str(url)[:500] if url else None,
                        helloasso_state=str(state)[:20] if state else None,
                        source=SOURCE_HELLOASSO,
                        is_active=str(state) not in _INACTIVE_STATES,
                        last_synced_at=_now(),
                    )
                )
                created += 1
            elif existing.source == SOURCE_MANUAL:
                # Ne jamais ecraser une saisie humaine.
                skipped += 1
                continue
            else:
                existing.nom = str(nom)[:255]
                existing.date_evenement = start
                existing.date_fin = end
                existing.url = str(url)[:500] if url else None
                existing.helloasso_state = str(state)[:20] if state else None
                existing.is_active = str(state) not in _INACTIVE_STATES
                existing.last_synced_at = _now()
                updated += 1
        except Exception as exc:  # noqa: BLE001 — un formulaire malforme ne doit
            # pas faire echouer la synchronisation des autres.
            logger.exception("Formulaire HelloAsso ignore : %s", exc)
            errors.append(str(exc)[:200])

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(
            ErrorCode.CONFLICT, detail="Conflit lors de la synchronisation des evenements."
        ) from exc

    logger.info(
        "Synchronisation evenements : %d cree(s), %d mis a jour, %d ignore(s).",
        created,
        updated,
        skipped,
    )
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def find_by_name(db: Session, nom: str) -> Event | None:
    cleaned = (nom or "").strip()
    if not cleaned:
        return None
    return db.execute(
        select(Event).where(or_(Event.nom == cleaned, Event.nom.ilike(cleaned)))
    ).scalars().first()
