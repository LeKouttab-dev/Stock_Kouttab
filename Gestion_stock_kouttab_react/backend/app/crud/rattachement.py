"""Resolution du rattachement comptable d'une piece (pole + suite).

Ce que « rattachement » recouvre : le pole, puis **selon le pole**, un evenement
ou une categorie. Les factures et les notes de frais partagent exactement cette
regle et alimentent le meme circuit comptable — la resoudre a un seul endroit
evite qu'un ecran finisse par accepter ce que l'autre refuse.

La resolution se fait **avant toute ecriture** : ces champs composent le nom du
PDF envoye au comptable, et une erreur doit revenir au deposant plutot que de
produire une piece mal nommee.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud import event as event_crud
from app.crud import expense_category as category_crud
from app.crud import pole as pole_crud


@dataclass(frozen=True)
class Rattachement:
    """Ce qui sera enregistre sur la piece, identifiants et libelles."""

    id_pole: int
    pole: str
    id_event: int | None
    evenement: str | None
    id_categorie: int | None
    categorie: str | None
    date_evenement: date | None

    @property
    def libelle_document(self) -> str | None:
        """Deuxieme composant du nom du fichier comptable.

        L'evenement sous un pole evenementiel, la categorie sous les autres :
        dans les deux cas, ce qui dit a quoi la depense se rattache.
        """
        return self.evenement or self.categorie


def resoudre(
    db: Session,
    *,
    id_pole: int,
    id_event: int | None = None,
    evenement_libre: str | None = None,
    id_categorie: int | None = None,
    date_evenement: date | None = None,
) -> Rattachement:
    """Valide et resout le rattachement, ou leve avec un message utilisable.

    Le pole commande : lui seul dit s'il attend un evenement ou une categorie.
    Aucune liste de poles n'est ecrite en dur ici — un pole cree demain se
    comporte selon son propre drapeau.
    """
    pole = pole_crud.get_pole_or_404(db, id_pole)

    if pole.requiert_evenement:
        if id_categorie is not None:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                detail=(
                    f"Le pole « {pole.nom} » se rattache a un evenement, pas a une "
                    "categorie."
                ),
            )
        event_id, event_label = event_crud.resolve_event(
            db, event_id=id_event, evenement_libre=evenement_libre
        )
        if date_evenement is None:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                detail="La date de l'evenement est obligatoire.",
            )
        return Rattachement(
            id_pole=pole.id,
            pole=pole.nom,
            id_event=event_id,
            evenement=event_label,
            id_categorie=None,
            categorie=None,
            date_evenement=date_evenement,
        )

    # Pole sans evenement : une depense du local n'en a pas, et en exiger un
    # obligeait a en inventer.
    if id_event is not None or (evenement_libre or "").strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=(
                f"Le pole « {pole.nom} » ne se rattache pas a un evenement. "
                "Choisissez une categorie."
            ),
        )
    categorie = category_crud.resolve_for_pole(
        db, requiert_evenement=False, id_categorie=id_categorie
    )
    assert categorie is not None  # garanti par resolve_for_pole

    return Rattachement(
        id_pole=pole.id,
        pole=pole.nom,
        id_event=None,
        evenement=None,
        id_categorie=categorie.id,
        categorie=categorie.nom,
        # Pas d'evenement, donc pas de date d'evenement : la date de la depense
        # fait foi, et c'est elle qui datera le fichier comptable.
        date_evenement=None,
    )


__all__ = ["Rattachement", "resoudre"]
