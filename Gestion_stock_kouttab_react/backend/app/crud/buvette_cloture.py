"""Cloture de caisse especes de la buvette, PONCTUELLE.

On cloture quand on veut (pas forcement chaque jour), et a chaque comptage on
VIDE la boite. L'attendu d'une cloture = ventes en especes de la tablette dans
]dernier comptage ; maintenant], le dernier comptage etant le plus recent entre
la derniere cloture et la fin du dernier inventaire termine
(`crud.buvette_inventaire.dernier_comptage`, regle partagee avec l'inventaire).
Premier comptage de tous : depuis une date choisie (minuit, heure de Paris).

Periode, attendu, ecart et nombre de ventes sont calcules et FIGES ici, au
moment du POST : l'ecran pourrait afficher un chiffre perime.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.crud.buvette_inventaire import (
    _debut_choisi,
    _vente_out,
    dernier_comptage,
    dernier_comptage_out,
    en_utc,
    maintenant,
    utc_vers_paris,
    ventes_especes,
)
from app.db.models import ClotureCaisse


logger = get_logger("crud.buvette_cloture")

# Garde-fou contre le double clic : une cloture sans aucune vente, moins de
# DOUBLON_SECONDES apres la precedente, est presque toujours un doublon.
DOUBLON_SECONDES = 60

_DEBUT_OBLIGATOIRE = (
    "Premier comptage : indiquez la date de debut de la periode des especes."
)


def periode(
    db: Session,
    debut: date | None,
    *,
    fin: datetime | None = None,
    verrouiller: bool = False,
) -> dict[str, Any]:
    """Periode courante et ses ventes especes (UTC naif), sans mise en forme."""
    fin = fin or maintenant()
    dernier = dernier_comptage(db, verrouiller=verrouiller)
    if dernier is not None:
        debut_p: datetime | None = dernier["le"]
        premier = False
    else:
        debut_p = _debut_choisi(debut)
        premier = True
    ventes = (
        ventes_especes(db, debut_p, fin, debut_inclus=premier) if debut_p is not None else []
    )
    return {
        "debut": debut_p,
        "fin": fin,
        "premier": premier,
        "dernier": dernier,
        "ventes": ventes,
        "attendu_cents": sum(v["total_cents"] for v in ventes),
    }


def attendu(db: Session, debut: date | None) -> dict[str, Any]:
    """Contrat de `GET /buvette/clotures/attendu`."""
    p = periode(db, debut)
    return {
        "periode_debut": en_utc(p["debut"]),
        "periode_fin": en_utc(p["fin"]),
        "premier_comptage": p["premier"],
        "attendu_cents": p["attendu_cents"],
        "nb_ventes": len(p["ventes"]),
        "ventes": [_vente_out(v) for v in p["ventes"]],
        "dernier_comptage": dernier_comptage_out(p["dernier"]),
    }


def _derniere_cloture(db: Session) -> ClotureCaisse | None:
    return db.execute(
        select(ClotureCaisse)
        .order_by(ClotureCaisse.periode_fin.desc(), ClotureCaisse.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def cloturer(
    db: Session,
    *,
    compte_cents: int,
    commentaire: str | None,
    debut: date | None,
    saisi_par: str | None,
    instant: datetime | None = None,
) -> ClotureCaisse:
    """Enregistre une cloture : periode, attendu, ecart et nb de ventes figes.

    - 422 si c'est le premier comptage et qu'aucune date de debut n'est donnee ;
    - 409 si la periode ne contient aucune vente ET que la cloture precedente
      date de moins d'une minute (double clic, double envoi).
    Plusieurs clotures le meme jour sont permises.
    """
    fin = instant or maintenant()
    # Verrou sur la derniere cloture : deux saisies simultanees se succedent,
    # et la seconde part de la premiere (boite deja videe) au lieu de recompter.
    p = periode(db, debut, fin=fin, verrouiller=True)
    if p["debut"] is None:
        db.rollback()
        raise AppException(ErrorCode.VALIDATION_ERROR, detail=_DEBUT_OBLIGATOIRE)

    if not p["ventes"]:
        precedente = _derniere_cloture(db)
        if precedente is not None and fin - precedente.periode_fin < timedelta(
            seconds=DOUBLON_SECONDES
        ):
            db.rollback()
            raise AppException(
                ErrorCode.CONFLICT,
                detail=(
                    "Une cloture vient d'etre enregistree il y a moins d'une minute et "
                    "aucune vente en especes n'a eu lieu depuis : c'est probablement un "
                    "doublon. Verifiez l'historique avant de recommencer."
                ),
            )

    texte = (commentaire or "").strip() or None
    attendu_cents = p["attendu_cents"]
    cloture = ClotureCaisse(
        jour=utc_vers_paris(fin).date(),
        periode_debut=p["debut"],
        periode_fin=fin,
        nb_ventes=len(p["ventes"]),
        attendu_cents=attendu_cents,
        compte_cents=compte_cents,
        ecart_cents=compte_cents - attendu_cents,
        commentaire=texte,
        saisi_par=saisi_par,
        created_at=fin,
    )
    db.add(cloture)
    db.commit()
    db.refresh(cloture)
    logger.info(
        "Cloture caisse %s : %d vente(s), attendu %d, compte %d, ecart %d (par %s).",
        cloture.id,
        cloture.nb_ventes,
        attendu_cents,
        compte_cents,
        cloture.ecart_cents,
        saisi_par,
    )
    return cloture


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def lister(
    db: Session,
    debut: date | None = None,
    fin: date | None = None,
    limit: int | None = None,
) -> list[ClotureCaisse]:
    """Clotures dont le jour (Paris) tombe dans [debut, fin], plus recentes d'abord."""
    if debut and fin and fin < debut:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="La date de fin precede la date de debut."
        )
    stmt = select(ClotureCaisse)
    if debut:
        stmt = stmt.where(ClotureCaisse.jour >= debut)
    if fin:
        stmt = stmt.where(ClotureCaisse.jour <= fin)
    stmt = stmt.order_by(ClotureCaisse.periode_fin.desc(), ClotureCaisse.id.desc())
    if limit is not None:
        stmt = stmt.limit(max(1, limit))
    return list(db.execute(stmt).scalars())


def entre(
    db: Session, debut_utc: datetime | None, fin_utc: datetime
) -> list[ClotureCaisse]:
    """Clotures faites dans ]debut ; fin] (UTC naif), plus anciennes d'abord.

    Meme convention que les reappros d'une periode de mouvements d'inventaire.
    """
    stmt = select(ClotureCaisse).where(ClotureCaisse.periode_fin <= fin_utc)
    if debut_utc is not None:
        stmt = stmt.where(ClotureCaisse.periode_fin > debut_utc)
    return list(
        db.execute(
            stmt.order_by(ClotureCaisse.periode_fin.asc(), ClotureCaisse.id.asc())
        ).scalars()
    )


def du_jour(db: Session, jour: date) -> list[ClotureCaisse]:
    """Clotures faites ce jour-la (heure de Paris), plus anciennes d'abord."""
    return list(
        db.execute(
            select(ClotureCaisse)
            .where(ClotureCaisse.jour == jour)
            .order_by(ClotureCaisse.periode_fin.asc(), ClotureCaisse.id.asc())
        ).scalars()
    )


def cloture_out(c: ClotureCaisse) -> dict[str, Any]:
    """Contrat d'API d'une cloture (horodatages en UTC avec fuseau)."""
    return {
        "id": c.id,
        "jour": c.jour,
        "periode_debut": en_utc(c.periode_debut),
        "periode_fin": en_utc(c.periode_fin),
        "attendu_cents": c.attendu_cents,
        "compte_cents": c.compte_cents,
        "ecart_cents": c.ecart_cents,
        "nb_ventes": c.nb_ventes,
        "commentaire": c.commentaire,
        "saisi_par": c.saisi_par,
        "created_at": en_utc(c.created_at),
    }
