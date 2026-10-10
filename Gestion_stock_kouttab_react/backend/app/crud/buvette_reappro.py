"""Reapprovisionnements de la buvette : historique, et mouvements d'un inventaire.

L'ecriture (increment atomique + trace) vit dans `crud.buvette.reapprovisionner`,
a cote des decrements des ventes : les deux touchent au stock de la meme facon.

Ici, la lecture :

- `lister` : historique filtre (jours de Paris, produit, origine) et totaux ;
- `periode_mouvements` / `mouvements_inventaire` : ce qui s'est passe entre deux
  etats de stock connus (validation du stock de l'inventaire precedent, puis de
  celui-ci) : reappros, ventes par article, ecarts d'inventaire, et un
  recapitulatif par produit (compte au precedent + reappros - ventes = attendu).

Horodatages des reappros en UTC naif ; les ventes portent l'heure murale de
Paris (`crud.buvette._instant`), d'ou les conversions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud.buvette import (
    _cle_vente,
    _instant,
    _verifier_periode,
    aujourd_hui,
    moyen_de_paiement,
    resume_carte,
    taux_frais_carte,
    ventes_regroupees,
)
from app.crud.buvette_cloture import cloture_out
from app.crud.buvette_cloture import entre as clotures_entre
from app.crud.buvette_inventaire import (
    debut_du_jour_en_utc,
    en_utc,
    maintenant,
    utc_vers_paris,
)
from app.db.models import BuvetteReapprovisionnement, BuvetteSale, Inventaire


# ---------------------------------------------------------------------------
# Historique
# ---------------------------------------------------------------------------


def reappro_out(r: BuvetteReapprovisionnement) -> dict[str, Any]:
    return {
        "id": r.id,
        "product_id": r.buvette_product_id,
        "nom": r.nom_snapshot,
        "quantite": r.quantite,
        "prix_achat_unitaire_cents": r.prix_achat_unitaire_cents,
        "total_cents": r.total_cents,
        "origine": r.origine,
        "commentaire": r.commentaire,
        "fait_par": r.fait_par,
        "stock_avant": r.stock_avant,
        "stock_apres": r.stock_apres,
        "created_at": en_utc(r.created_at),
    }


def totaux(reappros: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "nb": len(reappros),
        "quantite": sum(r["quantite"] for r in reappros),
        "montant_cents": sum(r["total_cents"] or 0 for r in reappros),
    }


def periode_par_defaut(debut: date | None, fin: date | None) -> tuple[date, date]:
    """`debut` et `fin` inclus ; par defaut, les 30 derniers jours (Paris)."""
    fin = fin or aujourd_hui()
    debut = debut or (fin - timedelta(days=29))
    _verifier_periode(debut, fin)
    return debut, fin


def entre(
    db: Session,
    debut_utc: datetime | None,
    fin_utc: datetime | None,
    *,
    product_id: int | None = None,
    origine: str | None = None,
    fin_incluse: bool = False,
) -> list[BuvetteReapprovisionnement]:
    """Reappros entre deux instants UTC naifs (debut exclu si `fin_incluse`).

    Deux usages : un filtre par jours (`[debut, fin[`) et une periode de
    mouvements (`]validation precedente, validation[`) : un reappro trace a la
    seconde meme d'une validation appartient a la periode qui se termine.
    """
    stmt = select(BuvetteReapprovisionnement)
    if debut_utc is not None:
        stmt = stmt.where(
            BuvetteReapprovisionnement.created_at > debut_utc
            if fin_incluse
            else BuvetteReapprovisionnement.created_at >= debut_utc
        )
    if fin_utc is not None:
        stmt = stmt.where(
            BuvetteReapprovisionnement.created_at <= fin_utc
            if fin_incluse
            else BuvetteReapprovisionnement.created_at < fin_utc
        )
    if product_id is not None:
        stmt = stmt.where(BuvetteReapprovisionnement.buvette_product_id == product_id)
    if origine:
        stmt = stmt.where(BuvetteReapprovisionnement.origine == origine)
    stmt = stmt.order_by(
        BuvetteReapprovisionnement.created_at.desc(), BuvetteReapprovisionnement.id.desc()
    )
    return list(db.execute(stmt).scalars())


def par_jours(
    db: Session,
    debut: date | None,
    fin: date | None,
    *,
    product_id: int | None = None,
    origine: str | None = None,
) -> list[dict[str, Any]]:
    """Reappros dont le jour (Paris) tombe dans [debut, fin], plus recents d'abord.

    Une borne absente n'est pas appliquee (export de l'historique des inventaires).
    """
    return [
        reappro_out(r)
        for r in entre(
            db,
            debut_du_jour_en_utc(debut) if debut else None,
            debut_du_jour_en_utc(fin + timedelta(days=1)) if fin else None,
            product_id=product_id,
            origine=origine,
        )
    ]


def lister(
    db: Session,
    debut: date | None,
    fin: date | None,
    *,
    product_id: int | None = None,
    origine: str | None = None,
) -> tuple[date, date, dict[str, Any]]:
    """Historique filtre (30 derniers jours par defaut) et ses totaux."""
    debut, fin = periode_par_defaut(debut, fin)
    reappros = par_jours(db, debut, fin, product_id=product_id, origine=origine)
    return debut, fin, {"reappros": reappros, "totaux": totaux(reappros)}


# ---------------------------------------------------------------------------
# Mouvements entre deux inventaires
# ---------------------------------------------------------------------------


def inventaire_precedent(db: Session, inventaire: Inventaire) -> Inventaire | None:
    """Le dernier inventaire dont le stock a ete valide avant celui-ci."""
    borne = inventaire.stock_valide_le
    stmt = select(Inventaire).where(
        Inventaire.id != inventaire.id, Inventaire.stock_valide_le.is_not(None)
    )
    if borne is not None:
        stmt = stmt.where(Inventaire.stock_valide_le < borne)
    return db.execute(
        stmt.order_by(Inventaire.stock_valide_le.desc(), Inventaire.id.desc()).limit(1)
    ).scalar_one_or_none()


def periode_mouvements(
    db: Session, inventaire: Inventaire
) -> tuple[Inventaire | None, datetime | None, datetime]:
    """(precedent, debut, fin) en UTC naif.

    Debut = validation du stock de l'inventaire precedent (a defaut, debut des
    donnees : `None`) ; fin = validation du stock de celui-ci (a defaut, maintenant).
    """
    precedent = inventaire_precedent(db, inventaire)
    debut = precedent.stock_valide_le if precedent is not None else None
    return precedent, debut, inventaire.stock_valide_le or maintenant()


def achats_cents(db: Session, inventaire: Inventaire) -> int:
    """Total des reappros (avec prix) de la periode des mouvements."""
    _, debut, fin = periode_mouvements(db, inventaire)
    stmt = select(func.coalesce(func.sum(BuvetteReapprovisionnement.total_cents), 0)).where(
        BuvetteReapprovisionnement.created_at <= fin
    )
    if debut is not None:
        stmt = stmt.where(BuvetteReapprovisionnement.created_at > debut)
    return int(db.execute(stmt).scalar_one() or 0)


def achats_par_inventaire(db: Session, inventaires: list[Inventaire]) -> dict[int, int]:
    """`achats_cents` de plusieurs inventaires, en deux requetes (base distante)."""
    if not inventaires:
        return {}
    valides = list(
        db.execute(
            select(Inventaire.id, Inventaire.stock_valide_le)
            .where(Inventaire.stock_valide_le.is_not(None))
            .order_by(Inventaire.stock_valide_le.asc(), Inventaire.id.asc())
        ).all()
    )
    lignes = list(
        db.execute(
            select(BuvetteReapprovisionnement.created_at, BuvetteReapprovisionnement.total_cents)
            .where(BuvetteReapprovisionnement.total_cents.is_not(None))
        ).all()
    )
    instant = maintenant()
    resultat: dict[int, int] = {}
    for inv in inventaires:
        fin = inv.stock_valide_le or instant
        anterieurs = [
            v for (i, v) in valides if i != inv.id and (inv.stock_valide_le is None or v < fin)
        ]
        debut = anterieurs[-1] if anterieurs else None
        resultat[inv.id] = sum(
            total for (cree, total) in lignes if cree <= fin and (debut is None or cree > debut)
        )
    return resultat


def _ventes(db: Session, debut: datetime | None, fin: datetime) -> list[BuvetteSale]:
    """Lignes de vente de la periode (bornes UTC naives converties en heure de Paris)."""
    instant = func.coalesce(BuvetteSale.sold_at, BuvetteSale.processed_at)
    stmt = select(BuvetteSale).where(instant <= utc_vers_paris(fin))
    if debut is not None:
        stmt = stmt.where(instant > utc_vers_paris(debut))
    return list(db.execute(stmt.order_by(BuvetteSale.id.asc())).scalars())


def _ventes_carte(db: Session, ventes: list[BuvetteSale]) -> list[dict[str, Any]]:
    """Ventes carte regroupees par transaction, avec leurs frais SumUp."""
    return ventes_regroupees(ventes, "carte", taux_frais_carte(db))


def ventes_carte(db: Session, inventaire: Inventaire) -> dict[str, int]:
    """Ventes carte de la periode des mouvements : nb, brut, frais SumUp, net."""
    _, debut, fin = periode_mouvements(db, inventaire)
    return resume_carte(_ventes_carte(db, _ventes(db, debut, fin)))


def mouvements_inventaire(db: Session, inventaire: Inventaire) -> dict[str, Any]:
    """Ce que l'export d'inventaire ajoute : reappros, mouvements, recap par produit.

    - `reappros` : ceux de la periode, plus anciens d'abord ;
    - `mouvements` : chronologie unique (reappros, ventes par article avec leur
      moyen, clotures de caisse, ecarts de cet inventaire), heures de Paris
      naives ;
    - `clotures` : clotures de caisse faites dans la periode, plus anciennes
      d'abord (`crud.buvette_cloture.cloture_out`) ;
    - `recap` : une ligne par produit de l'inventaire. « Compte au precedent »
      = quantite comptee a l'inventaire precedent ; 0 pour un produit cree
      depuis (son stock initial est trace comme reappro) ; inconnu sinon, et
      alors ni attendu ni ecart ne sont calcules.
    """
    precedent, debut, fin = periode_mouvements(db, inventaire)

    reappros = [
        reappro_out(r) for r in entre(db, debut, fin, fin_incluse=True)
    ]
    reappros.reverse()
    ventes = _ventes(db, debut, fin)
    carte = _ventes_carte(db, ventes)
    # Frais SumUp d'une transaction portes par sa PREMIERE ligne d'article : la
    # colonne se somme au total exact (frais calcules par transaction).
    frais_par_cle = {v["cle"]: v["frais_cents"] for v in carte}
    premieres: dict[str, int] = {}
    for v in sorted(ventes, key=lambda x: (x.caisse_line or 0, x.id)):
        premieres.setdefault(_cle_vente(v), v.id)

    mouvements: list[dict[str, Any]] = []
    for r in reappros:
        mouvements.append(
            {
                "quand": utc_vers_paris(r["created_at"].replace(tzinfo=None)),
                "type": "reappro",
                "produit": r["nom"],
                "quantite": r["quantite"],
                "moyen": r["origine"],
                "prix_unitaire_cents": r["prix_achat_unitaire_cents"],
                "montant_cents": r["total_cents"],
                "frais_cents": None,
                "detail": " ; ".join(
                    t for t in (r["fait_par"] and f"par {r['fait_par']}", r["commentaire"]) if t
                ),
            }
        )
    for v in ventes:
        mouvements.append(
            {
                "quand": _instant(v),
                "type": "vente",
                "produit": v.product_name_snapshot,
                "quantite": -v.quantity_sold,
                "moyen": moyen_de_paiement(v),
                "prix_unitaire_cents": (
                    v.amount_cents // v.quantity_sold if v.quantity_sold else None
                ),
                "montant_cents": v.amount_cents,
                "frais_cents": (
                    frais_par_cle.get(_cle_vente(v))
                    if premieres.get(_cle_vente(v)) == v.id
                    else None
                ),
                "detail": (
                    f"SumUp {v.sumup_tx_code}"
                    if v.sumup_tx_code
                    else (
                        f"Commande HelloAsso {v.helloasso_order_id}"
                        if v.helloasso_order_id is not None
                        else (v.caisse_tx_id or "")
                    )
                ),
            }
        )
    # Clotures de caisse de la periode : la boite a ete videe, montant compte.
    clotures = [cloture_out(c) for c in clotures_entre(db, debut, fin)]
    for c in clotures:
        mouvements.append(
            {
                "quand": utc_vers_paris(c["periode_fin"].replace(tzinfo=None)),
                "type": "cloture",
                "produit": "",
                "quantite": None,
                "moyen": "especes",
                "prix_unitaire_cents": None,
                "montant_cents": c["compte_cents"],
                "frais_cents": None,
                "detail": " ; ".join(
                    t
                    for t in (
                        f"attendu {c['attendu_cents'] / 100:.2f} €".replace(".", ","),
                        f"écart {c['ecart_cents'] / 100:+.2f} €".replace(".", ","),
                        c["saisi_par"] and f"par {c['saisi_par']}",
                        c["commentaire"],
                    )
                    if t
                ),
            }
        )
    if inventaire.stock_valide_le is not None:
        quand = utc_vers_paris(inventaire.stock_valide_le)
        for l in inventaire.lignes:
            if l.ecart:
                mouvements.append(
                    {
                        "quand": quand,
                        "type": "ecart",
                        "produit": l.nom_snapshot,
                        "quantite": l.ecart,
                        "moyen": None,
                        "prix_unitaire_cents": l.prix_cents_snapshot,
                        "montant_cents": l.valeur_ecart_cents,
                        "frais_cents": None,
                        "detail": f"Inventaire n° {inventaire.id}",
                    }
                )
    ordre = {"reappro": 0, "vente": 1, "cloture": 2, "ecart": 3}
    mouvements.sort(key=lambda m: (m["quand"], ordre[m["type"]]))

    # Recapitulatif par produit
    reappro_par_produit: dict[int, int] = defaultdict(int)
    for r in reappros:
        if r["product_id"] is not None:
            reappro_par_produit[r["product_id"]] += r["quantite"]
    ventes_par_produit: dict[int, int] = defaultdict(int)
    for v in ventes:
        if v.buvette_product_id is not None:
            ventes_par_produit[v.buvette_product_id] += v.quantity_sold
    comptes_precedents: dict[int, int] = (
        {
            l.buvette_product_id: l.quantite_comptee
            for l in precedent.lignes
            if l.buvette_product_id is not None
        }
        if precedent is not None
        else {}
    )

    recap: list[dict[str, Any]] = []
    for l in inventaire.lignes:
        pid = l.buvette_product_id
        entrees = reappro_par_produit.get(pid, 0) if pid else 0
        sorties = ventes_par_produit.get(pid, 0) if pid else 0
        avant: int | None = comptes_precedents.get(pid) if pid else None
        if (
            avant is None
            and precedent is not None
            and l.produit is not None
            and l.produit.created_at is not None
            and debut is not None
            and l.produit.created_at > debut
        ):
            avant = 0
        attendu = avant + entrees - sorties if avant is not None else None
        ecart = l.quantite_comptee - attendu if attendu is not None else None
        recap.append(
            {
                "nom": l.nom_snapshot,
                "categorie": l.categorie_snapshot,
                "prix_cents": l.prix_cents_snapshot or 0,
                "compte_precedent": avant,
                "reappros": entrees,
                "ventes": sorties,
                "attendu": attendu,
                "compte": l.quantite_comptee,
                "ecart": ecart,
                "valeur_ecart_cents": (
                    ecart * (l.prix_cents_snapshot or 0) if ecart is not None else None
                ),
            }
        )

    return {
        "precedent_id": precedent.id if precedent is not None else None,
        "periode_debut": en_utc(debut),
        "periode_fin": en_utc(fin),
        "reappros": reappros,
        "achats_cents": sum(r["total_cents"] or 0 for r in reappros),
        "mouvements": mouvements,
        "recap": recap,
        "clotures": clotures,
        "ventes_carte": resume_carte(carte),
    }

