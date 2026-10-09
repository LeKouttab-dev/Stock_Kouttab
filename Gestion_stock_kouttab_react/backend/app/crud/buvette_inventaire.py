"""Inventaire de la buvette : comptage du stock, puis des especes.

Deroule (cf. `Inventaire`) :

1. `demarrer` : une ligne par produit inventorie, comptee a 0. Inventories :
   produits actifs ET ranges dans un onglet de la tablette, SAUF les cafes
   (prepares sur place, rien a compter).
2. `enregistrer_lignes` : brouillon des quantites comptees, repris si on quitte
   la page.
3. `valider_stock` : dans UNE transaction, fige la quantite theorique = stock en
   base A CET INSTANT (une vente passee pendant le comptage est donc comptee),
   calcule les ecarts et remplace le stock par les quantites comptees. Aucune
   alerte de stock bas n'est envoyee : `alert_sent` est seulement recale.
4. `terminer` : especes comptees contre especes attendues sur la periode, qui
   court de la fin du dernier inventaire termine jusqu'a maintenant (premier
   inventaire : depuis une date choisie).

Horodatages stockes en UTC naif ; les ventes portent l'heure murale de Paris
(`sold_at`, cf. `crud.buvette._instant`), d'ou les conversions de periode.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.crud.buvette import PARIS, aujourd_hui, ventes_regroupees
from app.db.models import BuvetteProduct, BuvetteSale, Inventaire, InventaireLigne


logger = get_logger("crud.buvette_inventaire")

EN_COURS = "en_cours"
STOCK_VALIDE = "stock_valide"
TERMINE = "termine"
NON_TERMINES = (EN_COURS, STOCK_VALIDE)

# Onglet de la tablette exclu du comptage : les cafes se preparent a la demande.
CATEGORIE_EXCLUE = "cafe"


# ---------------------------------------------------------------------------
# Heures
# ---------------------------------------------------------------------------


def maintenant() -> datetime:
    """Maintenant, en UTC naif (convention des colonnes DateTime de la base)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def en_utc(instant: datetime | None) -> datetime | None:
    """UTC naif -> UTC avec fuseau, pour les reponses JSON."""
    if instant is None:
        return None
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant


def utc_vers_paris(instant: datetime) -> datetime:
    """UTC naif -> heure murale de Paris, naive (l'heure des ventes)."""
    return instant.replace(tzinfo=timezone.utc).astimezone(PARIS).replace(tzinfo=None)


def paris_vers_utc(instant: datetime) -> datetime:
    """Heure murale de Paris, naive -> UTC avec fuseau."""
    return instant.replace(tzinfo=PARIS).astimezone(timezone.utc)


def debut_du_jour_en_utc(jour: date) -> datetime:
    """Minuit, heure de Paris, de ce jour, en UTC naif."""
    return (
        datetime.combine(jour, time.min, tzinfo=PARIS)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def _requete():
    return select(Inventaire).options(
        selectinload(Inventaire.lignes).selectinload(InventaireLigne.produit)
    )


def get(db: Session, inventaire_id: int) -> Inventaire | None:
    return db.execute(_requete().where(Inventaire.id == inventaire_id)).scalar_one_or_none()


def get_ou_404(db: Session, inventaire_id: int) -> Inventaire:
    inventaire = get(db, inventaire_id)
    if inventaire is None:
        raise AppException(ErrorCode.NOT_FOUND, detail="Inventaire introuvable.")
    return inventaire


def _verrouiller(db: Session, inventaire_id: int) -> Inventaire:
    """Relit l'inventaire en le verrouillant (FOR UPDATE ; ignore par SQLite).

    Deux validations simultanees se succedent ainsi au lieu de se melanger, et
    la seconde trouve le statut deja change.
    """
    inventaire = db.execute(
        select(Inventaire)
        .where(Inventaire.id == inventaire_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if inventaire is None:
        db.rollback()
        raise AppException(ErrorCode.NOT_FOUND, detail="Inventaire introuvable.")
    return inventaire


def _exiger_statut(db: Session, inventaire: Inventaire, statut: str, message: str) -> None:
    if inventaire.statut != statut:
        db.rollback()
        raise AppException(ErrorCode.CONFLICT, detail=message)


def en_cours(db: Session) -> Inventaire | None:
    """L'inventaire non termine (en comptage ou stock valide), s'il existe."""
    return db.execute(
        _requete()
        .where(Inventaire.statut.in_(NON_TERMINES))
        .order_by(Inventaire.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def historique(
    db: Session, debut: date | None = None, fin: date | None = None
) -> list[Inventaire]:
    """Tous les inventaires, plus recents d'abord ; filtre sur le jour (Paris) du debut."""
    if debut and fin and fin < debut:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="La date de fin precede la date de debut."
        )
    stmt = _requete()
    if debut:
        stmt = stmt.where(Inventaire.debut_le >= debut_du_jour_en_utc(debut))
    if fin:
        stmt = stmt.where(Inventaire.debut_le < debut_du_jour_en_utc(fin + timedelta(days=1)))
    stmt = stmt.order_by(Inventaire.debut_le.desc(), Inventaire.id.desc())
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Etape 1 : stock
# ---------------------------------------------------------------------------


def produits_inventories(db: Session) -> list[BuvetteProduct]:
    """Produits actifs, ranges dans un onglet de la tablette, hors cafes."""
    return list(
        db.execute(
            select(BuvetteProduct)
            .where(
                BuvetteProduct.is_active.is_(True),
                BuvetteProduct.caisse_category.is_not(None),
                BuvetteProduct.caisse_category != CATEGORIE_EXCLUE,
            )
            .order_by(BuvetteProduct.caisse_category.asc(), BuvetteProduct.name.asc())
        ).scalars()
    )


_DEJA_OUVERT = "Un inventaire est deja en cours : reprenez-le ou terminez-le."


def demarrer(db: Session, *, cree_par: str | None) -> Inventaire:
    """Ouvre un inventaire, toutes les lignes comptees a 0. 409 si un autre est ouvert."""
    if en_cours(db) is not None:
        raise AppException(ErrorCode.CONFLICT, detail=_DEJA_OUVERT)
    inventaire = Inventaire(
        statut=EN_COURS,
        verrou_actif=1,
        debut_le=maintenant(),
        cree_par=cree_par,
    )
    for produit in produits_inventories(db):
        inventaire.lignes.append(
            InventaireLigne(
                buvette_product_id=produit.id,
                nom_snapshot=produit.name,
                prix_cents_snapshot=produit.price_cents or 0,
                categorie_snapshot=produit.caisse_category,
                quantite_comptee=0,
            )
        )
    db.add(inventaire)
    try:
        db.commit()
    except IntegrityError as exc:
        # Deux demarrages simultanes : l'index unique sur `verrou_actif` a tranche.
        db.rollback()
        raise AppException(ErrorCode.CONFLICT, detail=_DEJA_OUVERT) from exc
    logger.info(
        "Inventaire %s demarre par %s (%d produits).",
        inventaire.id,
        cree_par,
        len(inventaire.lignes),
    )
    return get_ou_404(db, inventaire.id)


def enregistrer_lignes(
    db: Session, inventaire_id: int, saisies: list[tuple[int, int]]
) -> Inventaire:
    """Brouillon : quantites comptees, par identifiant de ligne. 409 hors comptage."""
    inventaire = _verrouiller(db, inventaire_id)
    _exiger_statut(
        db, inventaire, EN_COURS, "Le comptage du stock est deja valide : il n'est plus modifiable."
    )
    lignes = {l.id: l for l in inventaire.lignes}
    inconnues = sorted({ligne_id for ligne_id, _ in saisies if ligne_id not in lignes})
    if inconnues:
        db.rollback()
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Ligne(s) inconnue(s) dans cet inventaire.",
            extras={"lignes_inconnues": inconnues},
        )
    for ligne_id, quantite in saisies:
        lignes[ligne_id].quantite_comptee = quantite
    db.commit()
    return get_ou_404(db, inventaire_id)


def valider_stock(db: Session, inventaire_id: int) -> Inventaire:
    """Fige le theorique, calcule les ecarts et remplace le stock, en une transaction.

    Le theorique est lu ICI, produits verrouilles (FOR UPDATE sous MySQL) : une
    vente arrivee pendant le comptage a deja decremente le stock, elle n'est pas
    comptee comme un manque ; une vente concurrente attend la fin de la
    transaction et s'applique ensuite au stock compte.
    """
    inventaire = _verrouiller(db, inventaire_id)
    _exiger_statut(db, inventaire, EN_COURS, "Le stock de cet inventaire est deja valide.")

    ids = [l.buvette_product_id for l in inventaire.lignes if l.buvette_product_id]
    produits = (
        {
            p.id: p
            for p in db.execute(
                select(BuvetteProduct)
                .where(BuvetteProduct.id.in_(ids))
                .with_for_update()
                .execution_options(populate_existing=True)
            ).scalars()
        }
        if ids
        else {}
    )

    for ligne in inventaire.lignes:
        produit = produits.get(ligne.buvette_product_id) if ligne.buvette_product_id else None
        if produit is None:
            # Produit supprime depuis le demarrage : rien a comparer ni a corriger.
            ligne.quantite_theorique = None
            ligne.ecart = None
            ligne.valeur_ecart_cents = None
            continue
        theorique = produit.quantity or 0
        ligne.quantite_theorique = theorique
        ligne.ecart = ligne.quantite_comptee - theorique
        ligne.valeur_ecart_cents = ligne.ecart * (ligne.prix_cents_snapshot or 0)
        produit.quantity = ligne.quantite_comptee
        # Recale seulement : un inventaire n'envoie aucune alerte de stock bas.
        produit.alert_sent = produit.quantity < produit.seuil_alerte

    inventaire.statut = STOCK_VALIDE
    inventaire.stock_valide_le = maintenant()
    db.commit()
    logger.info("Inventaire %s : stock valide et mis a jour.", inventaire_id)
    return get_ou_404(db, inventaire_id)


def supprimer(db: Session, inventaire_id: int) -> None:
    """Abandon d'un brouillon. 409 des que le stock a ete valide (il a modifie le stock)."""
    inventaire = _verrouiller(db, inventaire_id)
    _exiger_statut(
        db,
        inventaire,
        EN_COURS,
        "Seul un inventaire en cours de comptage peut etre abandonne.",
    )
    db.delete(inventaire)
    db.commit()
    logger.info("Inventaire %s abandonne.", inventaire_id)


# ---------------------------------------------------------------------------
# Etape 2 : especes
# ---------------------------------------------------------------------------


def dernier_termine(
    db: Session, sauf: int | None = None, avant: datetime | None = None
) -> Inventaire | None:
    """Le dernier inventaire termine (hors `sauf`, et termine avant `avant`)."""
    stmt = select(Inventaire).where(Inventaire.statut == TERMINE)
    if sauf is not None:
        stmt = stmt.where(Inventaire.id != sauf)
    if avant is not None:
        stmt = stmt.where(Inventaire.termine_le < avant)
    return db.execute(
        stmt.order_by(Inventaire.termine_le.desc(), Inventaire.id.desc()).limit(1)
    ).scalar_one_or_none()


def ventes_especes(db: Session, debut: datetime, fin: datetime) -> list[dict[str, Any]]:
    """Ventes en especes (tablette, sans code SumUp) entre deux instants UTC naifs.

    Bornes converties en heure de Paris : c'est l'heure que portent les ventes.
    Regroupement et moyen de paiement : `crud.buvette.ventes_regroupees`, la
    meme regle que l'onglet Paiements. Ordre chronologique.
    """
    instant = func.coalesce(BuvetteSale.sold_at, BuvetteSale.processed_at)
    lignes = list(
        db.execute(
            select(BuvetteSale)
            .where(
                BuvetteSale.source == "caisse",
                BuvetteSale.sumup_tx_code.is_(None),
                instant >= utc_vers_paris(debut),
                instant <= utc_vers_paris(fin),
            )
            .order_by(BuvetteSale.id.asc())
        ).scalars()
    )
    ventes = ventes_regroupees(lignes, "especes")
    ventes.reverse()
    return ventes


def _debut_choisi(debut: date | None) -> datetime | None:
    if debut is None:
        return None
    if debut > aujourd_hui():
        raise AppException(
            ErrorCode.VALIDATION_ERROR, detail="La date de debut ne peut pas etre a venir."
        )
    return debut_du_jour_en_utc(debut)


def periode_especes(
    db: Session, inventaire: Inventaire, debut: date | None
) -> tuple[datetime | None, datetime, bool]:
    """(debut, fin, premier_inventaire) de la periode des especes, en UTC naif.

    Debut = fin du dernier inventaire termine ; sans inventaire termine avant
    celui-ci, la date choisie (minuit, heure de Paris), ou rien.
    """
    precedent = dernier_termine(db, sauf=inventaire.id)
    fin = maintenant()
    if precedent is not None and precedent.termine_le is not None:
        return precedent.termine_le, fin, False
    return _debut_choisi(debut), fin, True


def especes(db: Session, inventaire_id: int, debut: date | None) -> dict[str, Any]:
    """Periode, ventes en especes et total attendu.

    Inventaire termine : la periode et l'attendu figes a la cloture.
    """
    inventaire = get_ou_404(db, inventaire_id)
    if inventaire.statut == TERMINE and inventaire.periode_especes_fin is not None:
        debut_p, fin_p = inventaire.periode_especes_debut, inventaire.periode_especes_fin
        premier = dernier_termine(db, sauf=inventaire.id, avant=inventaire.termine_le) is None
        ventes = ventes_especes(db, debut_p, fin_p) if debut_p else []
        return {
            "periode_debut": en_utc(debut_p),
            "periode_fin": en_utc(fin_p),
            "premier_inventaire": premier,
            "attendu_cents": inventaire.especes_attendues_cents or 0,
            "nb_ventes": inventaire.nb_ventes_especes or 0,
            "ventes": [_vente_out(v) for v in ventes],
        }

    debut_p, fin_p, premier = periode_especes(db, inventaire, debut)
    ventes = ventes_especes(db, debut_p, fin_p) if debut_p else []
    return {
        "periode_debut": en_utc(debut_p),
        "periode_fin": en_utc(fin_p),
        "premier_inventaire": premier,
        "attendu_cents": sum(v["total_cents"] for v in ventes),
        "nb_ventes": len(ventes),
        "ventes": [_vente_out(v) for v in ventes],
    }


def _vente_out(vente: dict[str, Any]) -> dict[str, Any]:
    return {
        "cle": vente["cle"],
        "sold_at": paris_vers_utc(vente["sold_at"]),
        "total_cents": vente["total_cents"],
        "articles": vente["articles"],
    }


# ---------------------------------------------------------------------------
# Etape 3 : terminer
# ---------------------------------------------------------------------------


def terminer(
    db: Session,
    inventaire_id: int,
    *,
    especes_comptees_cents: int,
    commentaire: str | None,
    debut: date | None,
) -> Inventaire:
    """Fige la periode, l'attendu, l'ecart especes, et ferme l'inventaire."""
    inventaire = _verrouiller(db, inventaire_id)
    _exiger_statut(
        db,
        inventaire,
        STOCK_VALIDE,
        "Validez d'abord le stock : l'inventaire n'est pas a l'etape des especes.",
    )
    debut_p, fin_p, premier = periode_especes(db, inventaire, debut)
    if debut_p is None:
        db.rollback()
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail="Premier inventaire : indiquez la date de debut de la periode des especes.",
        )
    ventes = ventes_especes(db, debut_p, fin_p)
    attendu = sum(v["total_cents"] for v in ventes)

    inventaire.periode_especes_debut = debut_p
    inventaire.periode_especes_fin = fin_p
    inventaire.especes_attendues_cents = attendu
    inventaire.especes_comptees_cents = especes_comptees_cents
    inventaire.ecart_especes_cents = especes_comptees_cents - attendu
    inventaire.nb_ventes_especes = len(ventes)
    inventaire.commentaire = (commentaire or "").strip() or None
    inventaire.statut = TERMINE
    inventaire.termine_le = fin_p
    inventaire.verrou_actif = None
    db.commit()
    logger.info(
        "Inventaire %s termine : especes attendues %d, comptees %d (premier : %s).",
        inventaire_id,
        attendu,
        especes_comptees_cents,
        premier,
    )
    return get_ou_404(db, inventaire_id)


# ---------------------------------------------------------------------------
# Serialisation (contrat d'API)
# ---------------------------------------------------------------------------


def resume(lignes: list[InventaireLigne]) -> dict[str, int]:
    ecarts = [l.ecart for l in lignes if l.ecart is not None]
    valeurs = [l.valeur_ecart_cents for l in lignes if l.valeur_ecart_cents is not None]
    return {
        "nb_produits": len(lignes),
        "nb_ecarts": sum(1 for e in ecarts if e != 0),
        "ecart_unites": sum(ecarts),
        "valeur_ecart_cents": sum(valeurs),
        "perte_cents": -sum(v for v in valeurs if v < 0),
    }


def ligne_out(
    ligne: InventaireLigne, url_photo: Callable[[BuvetteProduct], str | None] | None = None
) -> dict[str, Any]:
    produit = ligne.produit
    return {
        "id": ligne.id,
        "product_id": produit.id if produit else None,
        "nom": ligne.nom_snapshot,
        "categorie": ligne.categorie_snapshot,
        "emoji": produit.emoji if produit else None,
        "image_url": (url_photo(produit) if url_photo else produit.image_url) if produit else None,
        "prix_cents": ligne.prix_cents_snapshot or 0,
        "stock_actuel": produit.quantity if produit else None,
        "quantite_comptee": ligne.quantite_comptee,
        "quantite_theorique": ligne.quantite_theorique,
        "ecart": ligne.ecart,
        "valeur_ecart_cents": ligne.valeur_ecart_cents,
    }


def inventaire_out(
    inventaire: Inventaire,
    *,
    avec_lignes: bool = True,
    url_photo: Callable[[BuvetteProduct], str | None] | None = None,
) -> dict[str, Any]:
    sortie: dict[str, Any] = {
        "id": inventaire.id,
        "statut": inventaire.statut,
        "debut_le": en_utc(inventaire.debut_le),
        "stock_valide_le": en_utc(inventaire.stock_valide_le),
        "termine_le": en_utc(inventaire.termine_le),
        "cree_par": inventaire.cree_par,
        "periode_especes_debut": en_utc(inventaire.periode_especes_debut),
        "periode_especes_fin": en_utc(inventaire.periode_especes_fin),
        "especes_attendues_cents": inventaire.especes_attendues_cents,
        "especes_comptees_cents": inventaire.especes_comptees_cents,
        "ecart_especes_cents": inventaire.ecart_especes_cents,
        "nb_ventes_especes": inventaire.nb_ventes_especes,
        "commentaire": inventaire.commentaire,
        "resume": resume(inventaire.lignes),
    }
    if avec_lignes:
        sortie["lignes"] = [ligne_out(l, url_photo) for l in inventaire.lignes]
    return sortie
