"""Classeurs Excel de la buvette : inventaire, historique des inventaires, paiements.

Fonctions pures : elles recoivent les donnees deja calculees par le CRUD (les
memes dictionnaires que l'API sert a l'ecran) et rendent les octets du classeur.
Un export ne recalcule rien, sinon il finirait par contredire l'ecran.

Conventions : en-tetes en gras sur fond vert, montants en euros (nombres, pas
du texte, pour que le tableur puisse les additionner), horodatages a l'heure de
Paris, une ligne de totaux en bas de chaque tableau.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timezone
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.crud.buvette import PARIS


MEDIA_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

FORMAT_EUROS = "#,##0.00 €"
FORMAT_DATE = "DD/MM/YYYY"
FORMAT_DATE_HEURE = "DD/MM/YYYY HH:MM"
FORMAT_HEURE = "HH:MM"

STATUTS = {
    "en_cours": "En cours (comptage)",
    "stock_valide": "Stock validé",
    "termine": "Terminé",
}
MOYENS = {"carte": "Carte", "especes": "Espèces", "helloasso": "HelloAsso"}
CATEGORIES = {
    "sucre_sale": "Sucré / salé",
    "boissons": "Boissons",
    "cafe": "Café",
    "epicerie": "Épicerie",
}

_GRAS = Font(bold=True)
_ENTETE_POLICE = Font(bold=True, color="FFFFFF")
_ENTETE_FOND = PatternFill("solid", fgColor="3D4F3D")
_TOTAL_FOND = PatternFill("solid", fgColor="EFE6D6")


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------


def euros(cents: int | None) -> float | None:
    return None if cents is None else round(cents / 100, 2)


def heure_paris(instant: datetime | None) -> datetime | None:
    """Horodatage (UTC, avec ou sans fuseau) -> heure de Paris, sans fuseau.

    Excel ne connait pas les fuseaux : une date avec fuseau y est refusee.
    """
    if instant is None:
        return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(PARIS).replace(tzinfo=None)


def _entetes(feuille: Worksheet, ligne: int, entetes: Iterable[str]) -> None:
    for colonne, texte in enumerate(entetes, start=1):
        cellule = feuille.cell(row=ligne, column=colonne, value=texte)
        cellule.font = _ENTETE_POLICE
        cellule.fill = _ENTETE_FOND
        cellule.alignment = Alignment(wrap_text=True, vertical="center")
    feuille.freeze_panes = feuille.cell(row=ligne + 1, column=1)


def _ligne(
    feuille: Worksheet,
    ligne: int,
    valeurs: Iterable[Any],
    formats: dict[int, str] | None = None,
    *,
    total: bool = False,
) -> None:
    formats = formats or {}
    for colonne, valeur in enumerate(valeurs, start=1):
        cellule = feuille.cell(row=ligne, column=colonne, value=valeur)
        if colonne in formats and valeur is not None:
            cellule.number_format = formats[colonne]
        if total:
            cellule.font = _GRAS
            cellule.fill = _TOTAL_FOND


def _largeurs(feuille: Worksheet, largeurs: Iterable[float]) -> None:
    for colonne, largeur in enumerate(largeurs, start=1):
        feuille.column_dimensions[get_column_letter(colonne)].width = largeur


def _octets(classeur: Workbook) -> bytes:
    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


def _categorie(code: str | None) -> str:
    return CATEGORIES.get(code or "", code or "")


def _articles_texte(articles: list[dict[str, Any]]) -> str:
    return ", ".join(f"{a['quantite']} × {a['nom']}" for a in articles)


# ---------------------------------------------------------------------------
# Un inventaire
# ---------------------------------------------------------------------------


ENTETES_ECARTS = (
    "Produit",
    "Catégorie",
    "Prix unitaire",
    "Stock théorique",
    "Quantité comptée",
    "Écart (unités)",
    "Valeur de l'écart",
)
ENTETES_VENTES_ESPECES = ("Date", "Heure", "Référence", "Articles", "Montant")


def _feuille_synthese(feuille: Worksheet, inv: dict[str, Any]) -> None:
    resume = inv["resume"]
    feuille.cell(row=1, column=1, value=f"Inventaire buvette n° {inv['id']}, Le Kouttâb").font = Font(
        bold=True, size=13
    )
    lignes: list[tuple[str, Any, str | None]] = [
        ("Statut", STATUTS.get(inv["statut"], inv["statut"]), None),
        ("Démarré le", heure_paris(inv["debut_le"]), FORMAT_DATE_HEURE),
        ("Stock validé le", heure_paris(inv["stock_valide_le"]), FORMAT_DATE_HEURE),
        ("Terminé le", heure_paris(inv["termine_le"]), FORMAT_DATE_HEURE),
        ("Réalisé par", inv["cree_par"] or "", None),
        ("", None, None),
        ("Produits comptés", resume["nb_produits"], None),
        ("Produits en écart", resume["nb_ecarts"], None),
        ("Écart total (unités)", resume["ecart_unites"], None),
        ("Valeur de l'écart", euros(resume["valeur_ecart_cents"]), FORMAT_EUROS),
        ("Perte estimée", euros(resume["perte_cents"]), FORMAT_EUROS),
        ("", None, None),
        ("Période des espèces : du", heure_paris(inv["periode_especes_debut"]), FORMAT_DATE_HEURE),
        ("Période des espèces : au", heure_paris(inv["periode_especes_fin"]), FORMAT_DATE_HEURE),
        ("Ventes en espèces", inv["nb_ventes_especes"], None),
        ("Espèces attendues", euros(inv["especes_attendues_cents"]), FORMAT_EUROS),
        ("Espèces comptées", euros(inv["especes_comptees_cents"]), FORMAT_EUROS),
        ("Écart espèces (compté moins attendu)", euros(inv["ecart_especes_cents"]), FORMAT_EUROS),
        ("Commentaire", inv["commentaire"] or "", None),
    ]
    for rang, (libelle, valeur, fmt) in enumerate(lignes, start=3):
        if not libelle:
            continue
        feuille.cell(row=rang, column=1, value=libelle).font = _GRAS
        cellule = feuille.cell(row=rang, column=2, value=valeur)
        if fmt and valeur is not None:
            cellule.number_format = fmt
        cellule.alignment = Alignment(horizontal="left", wrap_text=True)
    _largeurs(feuille, (38, 44))


def _feuille_ecarts(feuille: Worksheet, lignes: list[dict[str, Any]]) -> None:
    _entetes(feuille, 1, ENTETES_ECARTS)
    formats = {3: FORMAT_EUROS, 7: FORMAT_EUROS}
    rang = 2
    for l in lignes:
        _ligne(
            feuille,
            rang,
            (
                l["nom"],
                _categorie(l["categorie"]),
                euros(l["prix_cents"]),
                l["quantite_theorique"],
                l["quantite_comptee"],
                l["ecart"],
                euros(l["valeur_ecart_cents"]),
            ),
            formats,
        )
        rang += 1
    _ligne(
        feuille,
        rang,
        (
            "Total",
            "",
            None,
            sum(l["quantite_theorique"] or 0 for l in lignes),
            sum(l["quantite_comptee"] for l in lignes),
            sum(l["ecart"] or 0 for l in lignes),
            euros(sum(l["valeur_ecart_cents"] or 0 for l in lignes)),
        ),
        formats,
        total=True,
    )
    _largeurs(feuille, (32, 16, 13, 15, 16, 14, 17))


def _feuille_ventes_especes(feuille: Worksheet, ventes: list[dict[str, Any]]) -> None:
    _entetes(feuille, 1, ENTETES_VENTES_ESPECES)
    rang = 2
    for v in ventes:
        instant = heure_paris(v["sold_at"])
        _ligne(
            feuille,
            rang,
            (instant, instant, v["cle"], _articles_texte(v["articles"]), euros(v["total_cents"])),
            {1: FORMAT_DATE, 2: FORMAT_HEURE, 5: FORMAT_EUROS},
        )
        rang += 1
    _ligne(
        feuille,
        rang,
        (f"Total ({len(ventes)} ventes)", None, "", "", euros(sum(v["total_cents"] for v in ventes))),
        {5: FORMAT_EUROS},
        total=True,
    )
    _largeurs(feuille, (14, 8, 40, 60, 12))


def classeur_inventaire(inv: dict[str, Any], especes: dict[str, Any]) -> bytes:
    """Feuilles « Synthèse », « Écarts produits », « Ventes espèces »."""
    classeur = Workbook()
    synthese = classeur.active
    synthese.title = "Synthèse"
    _feuille_synthese(synthese, inv)
    _feuille_ecarts(classeur.create_sheet("Écarts produits"), inv["lignes"])
    _feuille_ventes_especes(classeur.create_sheet("Ventes espèces"), especes["ventes"])
    return _octets(classeur)


# ---------------------------------------------------------------------------
# Historique des inventaires
# ---------------------------------------------------------------------------


ENTETES_HISTORIQUE = (
    "N°",
    "Statut",
    "Démarré le",
    "Terminé le",
    "Réalisé par",
    "Produits comptés",
    "Produits en écart",
    "Écart (unités)",
    "Valeur de l'écart",
    "Perte estimée",
    "Ventes en espèces",
    "Espèces attendues",
    "Espèces comptées",
    "Écart espèces",
    "Commentaire",
)
ENTETES_DETAIL = (
    "N° inventaire",
    "Démarré le",
    "Produit",
    "Catégorie",
    "Prix unitaire",
    "Stock théorique",
    "Quantité comptée",
    "Écart (unités)",
    "Valeur de l'écart",
)


def classeur_historique(inventaires: list[dict[str, Any]]) -> bytes:
    """Feuille « Inventaires » (un résumé par ligne) et « Détail » (les lignes produits)."""
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Inventaires"
    _entetes(feuille, 1, ENTETES_HISTORIQUE)
    formats = {3: FORMAT_DATE_HEURE, 4: FORMAT_DATE_HEURE, 9: FORMAT_EUROS, 10: FORMAT_EUROS,
               12: FORMAT_EUROS, 13: FORMAT_EUROS, 14: FORMAT_EUROS}
    rang = 2
    for inv in inventaires:
        r = inv["resume"]
        _ligne(
            feuille,
            rang,
            (
                inv["id"],
                STATUTS.get(inv["statut"], inv["statut"]),
                heure_paris(inv["debut_le"]),
                heure_paris(inv["termine_le"]),
                inv["cree_par"] or "",
                r["nb_produits"],
                r["nb_ecarts"],
                r["ecart_unites"],
                euros(r["valeur_ecart_cents"]),
                euros(r["perte_cents"]),
                inv["nb_ventes_especes"],
                euros(inv["especes_attendues_cents"]),
                euros(inv["especes_comptees_cents"]),
                euros(inv["ecart_especes_cents"]),
                inv["commentaire"] or "",
            ),
            formats,
        )
        rang += 1
    _ligne(
        feuille,
        rang,
        (
            f"Total ({len(inventaires)} inventaires)",
            "",
            None,
            None,
            "",
            sum(i["resume"]["nb_produits"] for i in inventaires),
            sum(i["resume"]["nb_ecarts"] for i in inventaires),
            sum(i["resume"]["ecart_unites"] for i in inventaires),
            euros(sum(i["resume"]["valeur_ecart_cents"] for i in inventaires)),
            euros(sum(i["resume"]["perte_cents"] for i in inventaires)),
            sum(i["nb_ventes_especes"] or 0 for i in inventaires),
            euros(sum(i["especes_attendues_cents"] or 0 for i in inventaires)),
            euros(sum(i["especes_comptees_cents"] or 0 for i in inventaires)),
            euros(sum(i["ecart_especes_cents"] or 0 for i in inventaires)),
            "",
        ),
        formats,
        total=True,
    )
    _largeurs(feuille, (22, 18, 17, 17, 22, 11, 11, 11, 14, 14, 11, 14, 14, 14, 40))

    detail = classeur.create_sheet("Détail")
    _entetes(detail, 1, ENTETES_DETAIL)
    formats_detail = {2: FORMAT_DATE_HEURE, 5: FORMAT_EUROS, 9: FORMAT_EUROS}
    rang = 2
    toutes = [(inv, l) for inv in inventaires for l in inv["lignes"]]
    for inv, l in toutes:
        _ligne(
            detail,
            rang,
            (
                inv["id"],
                heure_paris(inv["debut_le"]),
                l["nom"],
                _categorie(l["categorie"]),
                euros(l["prix_cents"]),
                l["quantite_theorique"],
                l["quantite_comptee"],
                l["ecart"],
                euros(l["valeur_ecart_cents"]),
            ),
            formats_detail,
        )
        rang += 1
    _ligne(
        detail,
        rang,
        (
            "Total",
            None,
            "",
            "",
            None,
            sum(l["quantite_theorique"] or 0 for _, l in toutes),
            sum(l["quantite_comptee"] for _, l in toutes),
            sum(l["ecart"] or 0 for _, l in toutes),
            euros(sum(l["valeur_ecart_cents"] or 0 for _, l in toutes)),
        ),
        formats_detail,
        total=True,
    )
    _largeurs(detail, (14, 17, 32, 16, 13, 15, 16, 14, 17))
    return _octets(classeur)


# ---------------------------------------------------------------------------
# Paiements
# ---------------------------------------------------------------------------


ENTETES_PAIEMENTS = (
    "Date",
    "Heure",
    "Moyen",
    "Référence",
    "Client",
    "Produit",
    "Quantité",
    "Montant ligne",
    "Total vente",
)


def _reference(vente: dict[str, Any]) -> str:
    if vente.get("sumup_tx_code"):
        return f"SumUp {vente['sumup_tx_code']}"
    if vente.get("helloasso_order_id") is not None:
        return f"Commande HelloAsso {vente['helloasso_order_id']}"
    return vente["cle"]


def classeur_paiements(ventes: list[dict[str, Any]]) -> bytes:
    """Feuille « Paiements » : une ligne par article, puis une ligne de totaux.

    `ventes` : la liste `paiements` de `crud.buvette.paiements` (heure murale
    de Paris, sans fuseau), dans l'ordre de l'ecran.
    """
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Paiements"
    _entetes(feuille, 1, ENTETES_PAIEMENTS)
    formats = {1: FORMAT_DATE, 2: FORMAT_HEURE, 8: FORMAT_EUROS, 9: FORMAT_EUROS}
    rang = 2
    for v in ventes:
        instant = v["sold_at"]
        if isinstance(instant, datetime) and instant.tzinfo is not None:
            instant = heure_paris(instant)
        for a in v["articles"]:
            _ligne(
                feuille,
                rang,
                (
                    instant,
                    instant,
                    MOYENS.get(v["moyen"], v["moyen"]),
                    _reference(v),
                    v.get("client") or "",
                    a["nom"],
                    a["quantite"],
                    euros(a["montant_cents"]),
                    euros(v["total_cents"]),
                ),
                formats,
            )
            rang += 1
    _ligne(
        feuille,
        rang,
        (
            f"Total ({len(ventes)} ventes)",
            None,
            "",
            "",
            "",
            "",
            sum(a["quantite"] for v in ventes for a in v["articles"]),
            euros(sum(a["montant_cents"] for v in ventes for a in v["articles"])),
            euros(sum(v["total_cents"] for v in ventes)),
        ),
        formats,
        total=True,
    )
    _largeurs(feuille, (12, 8, 11, 30, 22, 30, 10, 14, 13))
    return _octets(classeur)


def nom_periode(debut: date | None, fin: date | None) -> str:
    """`2026-10-01_2026-10-31`, ou la borne connue, ou `tout`."""
    if debut and fin:
        return f"{debut.isoformat()}_{fin.isoformat()}"
    if debut:
        return f"depuis-{debut.isoformat()}"
    if fin:
        return f"jusqu-au-{fin.isoformat()}"
    return "tout"
