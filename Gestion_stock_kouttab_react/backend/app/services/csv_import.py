"""Inventory CSV import — port of the legacy logic."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Category, Stock, SubCategory


logger = get_logger("csv_import")


EMOJI_MAP: dict[str, str] = {
    "Nourriture": "🍔",
    "Fournitures": "📝",
    "Intendance": "🧼",
    "Bibliothèque": "📚",
}


def _read_dataframe(content: bytes, *, sep: str = ",", skiprows: int = 0) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(content), sep=sep, skiprows=skiprows)
    except Exception as exc:  # noqa: BLE001
        try:
            return pd.read_csv(io.BytesIO(content), sep=";", skiprows=skiprows)
        except Exception as inner:  # noqa: BLE001
            raise AppException(
                ErrorCode.CSV_FORMAT_INVALID,
                detail=f"CSV illisible ({exc!s} / fallback ';': {inner!s})",
            ) from inner


def import_inventory(
    db: Session,
    *,
    content: bytes,
    skiprows: int = 6,
    default_threshold: int = 5,
) -> dict[str, Any]:
    df = _read_dataframe(content, skiprows=skiprows)

    expected = {"Catégorie", "Sous-catégorie", "Nom de l'article", "Quantité initiale"}
    missing = expected - set(df.columns)
    if missing:
        raise AppException(
            ErrorCode.CSV_FORMAT_INVALID,
            detail=f"Colonnes manquantes dans le CSV : {', '.join(sorted(missing))}.",
            extras={"missing_columns": sorted(missing)},
        )

    imported = 0
    skipped = 0
    errors: list[str] = []

    # Pre-load existing names / sub-categories to avoid N queries AND
    # to detect duplicates added within this same transaction (unflushed
    # ORM additions are invisible to subsequent queries — that was the
    # original bug : the same (categorie, sous_categorie) was queued
    # multiple times and crashed the UNIQUE constraint at commit).
    existing_stock_names: set[str] = {n for (n,) in db.query(Stock.nom).all()}
    existing_subcategories: set[tuple[str, str]] = {
        (cat, sub)
        for (cat, sub) in db.query(
            SubCategory.nom_categorie, SubCategory.nom_sous_categorie
        ).all()
    }
    existing_categories: set[str] = {n for (n,) in db.query(Category.nom).all()}

    for index, row in df.iterrows():
        try:
            categorie = str(row.get("Catégorie", "") or "").strip()
            sous_categorie = str(row.get("Sous-catégorie", "") or "").strip()
            nom = str(row.get("Nom de l'article", "") or "").strip()
            try:
                quantite_raw = row.get("Quantité initiale", 0)
                quantite = int(quantite_raw) if pd.notna(quantite_raw) else 0
            except (ValueError, TypeError):
                quantite = 0

            if not nom:
                errors.append(f"Ligne {index + 1} : nom manquant.")
                skipped += 1
                continue
            if not categorie:
                errors.append(f"Ligne {index + 1} : categorie manquante.")
                skipped += 1
                continue

            if nom in existing_stock_names:
                errors.append(f"Ligne {index + 1} : article '{nom}' deja existant.")
                skipped += 1
                continue

            # La categorie doit rejoindre le referentiel, au meme titre que la
            # sous-categorie juste en dessous. Sans cela, les articles importes
            # pointent vers une categorie que la table `Categories` ignore :
            # l'ecran « Naviguer par categorie » ne l'affiche pas, et si
            # quelqu'un la ressaisit a la main avec une faute de frappe, elle
            # s'affiche a cote avec zero article.
            if categorie not in existing_categories:
                db.add(Category(nom=categorie, is_default=False))
                existing_categories.add(categorie)

            if sous_categorie:
                key = (categorie, sous_categorie)
                if key not in existing_subcategories:
                    db.add(
                        SubCategory(
                            nom_categorie=categorie,
                            nom_sous_categorie=sous_categorie,
                        )
                    )
                    existing_subcategories.add(key)

            emoji = EMOJI_MAP.get(categorie, "📦")
            db.add(
                Stock(
                    nom=nom,
                    categorie=categorie,
                    sous_categorie=sous_categorie or None,
                    quantite=quantite,
                    seuil_alerte=default_threshold,
                    emoji=emoji,
                )
            )
            existing_stock_names.add(nom)
            imported += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Ligne {index + 1} : {exc!s}")
            skipped += 1

    if imported:
        db.commit()
    else:
        db.rollback()

    logger.info("Import CSV : %d importes / %d ignores", imported, skipped)
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:50],
    }
