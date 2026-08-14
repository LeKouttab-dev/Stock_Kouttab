"""Stock and inventory schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


STOCK_MOD_STATUS = Literal["En attente", "Approuvee", "Refusee", "Approuvée", "Refusée"]


class StockItemBase(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    categorie: str = Field(min_length=1, max_length=255)
    sous_categorie: str | None = None
    quantite: int = Field(ge=0, default=0)
    seuil_alerte: int = Field(ge=0, default=10)
    emoji: str | None = "📦"
    image_url: str | None = Field(default=None, max_length=500)
    barcode: str | None = Field(default=None, max_length=32)


class StockItemIn(StockItemBase):
    pass


class StockItemCreate(StockItemBase):
    """Alias kept for clarity at endpoint level."""


class StockItemUpdate(BaseModel):
    nom: str | None = None
    categorie: str | None = None
    sous_categorie: str | None = None
    quantite: int | None = Field(default=None, ge=0)
    seuil_alerte: int | None = Field(default=None, ge=0)
    emoji: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    barcode: str | None = Field(default=None, max_length=32)


class StockItemOut(StockItemBase):
    id: int
    alert_sent: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class QuantityUpdate(BaseModel):
    quantite: int = Field(ge=0)


class CategoryIn(BaseModel):
    nom: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class CategoryRename(BaseModel):
    new_name: str = Field(min_length=1, max_length=255)


class CategoryOut(BaseModel):
    id: int
    nom: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class SubCategoryIn(BaseModel):
    nom_categorie: str = Field(min_length=1, max_length=255)
    nom_sous_categorie: str = Field(min_length=1, max_length=255)


class SubCategoryUpdate(BaseModel):
    nom_categorie: str | None = None
    nom_sous_categorie: str | None = None


class SubCategoryOut(BaseModel):
    id: int
    nom_categorie: str
    nom_sous_categorie: str

    model_config = ConfigDict(from_attributes=True)


class ModificationIn(BaseModel):
    id_stock: int
    quantite_demandee: int = Field(ge=0)
    commentaires: str | None = None


class ModificationOut(BaseModel):
    id: int
    id_user: int
    id_stock: int
    quantite_actuelle: int
    quantite_demandee: int
    date_demande: datetime
    status: str
    approuve_par: int | None = None
    date_approbation: datetime | None = None
    commentaires: str | None = None
    user_username: str | None = None
    user_full_name: str | None = None
    stock_nom: str | None = None
    stock_categorie: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CategoryStat(BaseModel):
    categorie: str
    count: int
    total: int


class SubCategoryStat(BaseModel):
    sous_categorie: str
    count: int
    total: int


class RecentModif(BaseModel):
    date: datetime
    user_full_name: str
    stock_nom: str
    categorie: str
    status: str
    quantite_demandee: int


class StatsOut(BaseModel):
    total_articles: int
    total_quantite: int
    alertes_stock: int
    stock_epuise: int
    dernieres_modifs: list[RecentModif]
    stats_par_categorie: list[CategoryStat]
    stats_nourriture_sous_categories: list[SubCategoryStat]


class CSVImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
