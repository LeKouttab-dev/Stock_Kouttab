"""Buvette / HelloAsso schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


# Onglets de la tablette de caisse. Liste figee : chaque valeur correspond a un
# onglet code dans l'application Android, une valeur inconnue n'y serait
# affichee nulle part.
CaisseCategory = Literal["sucre_sale", "boissons", "cafe", "epicerie"]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class BuvetteProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(ge=0, default=0)
    quantity: int = Field(ge=0, default=0)
    seuil_alerte: int = Field(ge=0, default=5)
    emoji: str | None = "🥤"
    barcode: str | None = Field(default=None, max_length=32)


class BuvetteProductCreate(BaseModel):
    """Manual creation of a buvette product (not synced from HelloAsso)."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(ge=0, default=0)
    quantity: int = Field(ge=0, default=0)
    seuil_alerte: int = Field(ge=0, default=5)
    emoji: str | None = "🥤"
    image_url: str | None = None
    barcode: str | None = Field(default=None, max_length=32)
    helloasso_tier_id: int | None = None
    is_active: bool = True
    caisse_category: CaisseCategory | None = None


class BuvetteProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=0)
    seuil_alerte: int | None = Field(default=None, ge=0)
    emoji: str | None = None
    image_url: str | None = None
    barcode: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    # `null` explicite = retirer le produit de la tablette ; absent = inchange.
    caisse_category: CaisseCategory | None = None


class BuvetteProductOut(BaseModel):
    id: int
    helloasso_tier_id: int | None = None
    name: str
    description: str | None = None
    price_cents: int
    quantity: int
    seuil_alerte: int
    emoji: str | None = "🥤"
    image_url: str | None = None
    barcode: str | None = None
    is_active: bool = True
    caisse_category: CaisseCategory | None = None
    # Vrai des qu'un champ ecrit aussi par HelloAsso a ete modifie a la main
    # (nom, description, prix, photo). L'ecran l'affiche : sans cela, personne
    # ne peut savoir pourquoi « Synchroniser » ne change plus ce produit.
    edite_manuellement: bool = False
    # Present quand une photo a ete deposee : l'ecran propose alors de la
    # remplacer ou de la retirer, plutot que seulement d'en ajouter une.
    a_une_photo: bool = False
    alert_sent: bool = False
    last_synced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def low_stock(self) -> bool:
        return self.quantity < self.seuil_alerte


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


class BuvetteSaleOut(BaseModel):
    id: int
    source: Literal["helloasso", "caisse"] = "helloasso"
    caisse_tx_id: str | None = None
    sumup_tx_code: str | None = None
    helloasso_order_id: int | None = None
    helloasso_payment_id: int | None = None
    helloasso_item_id: int | None = None
    buvette_product_id: int | None = None
    product_name_snapshot: str
    quantity_sold: int
    amount_cents: int
    customer_first_name: str | None = None
    customer_last_name: str | None = None
    customer_email: str | None = None
    sold_at: datetime | None = None
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Caisse (tablette SumUp)
# ---------------------------------------------------------------------------


class CaisseProduitOut(BaseModel):
    """Ce que la tablette affiche d'un produit, et rien de plus."""

    id: int
    name: str
    price_cents: int
    category: CaisseCategory
    emoji: str | None = None
    # Photo de l'article (celle de la boutique HelloAsso). La tablette la garde
    # en cache et reprend l'emoji quand elle manque ou ne se charge pas.
    image_url: str | None = None
    quantity: int
    low_stock: bool


class CaisseCatalogueOut(BaseModel):
    products: list[CaisseProduitOut]
    generated_at: datetime


class CaisseLigneIn(BaseModel):
    """Une ligne du panier encaisse.

    `product_id` peut viser un produit supprime depuis le dernier catalogue : la
    vente est gardee sans decrement plutot que perdue. Le nom sert d'instantane.
    """

    product_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=1, le=100)
    unit_price_cents: int = Field(ge=0, le=100_000)


class CaisseVenteIn(BaseModel):
    # Le `foreignTransactionId` transmis a SumUp : l'identifiant qui rend la
    # vente idempotente. Alphabet restreint, il finit dans les journaux.
    transaction_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    sumup_tx_code: str | None = Field(default=None, max_length=64)
    total_cents: int = Field(ge=0)
    sold_at: datetime | None = None
    # La coherence total / detail est controlee dans `crud.record_caisse_sale`,
    # et non par un `model_validator` : le gestionnaire des erreurs de
    # validation ne sait pas serialiser l'exception qu'il porterait (500).
    lines: list[CaisseLigneIn] = Field(min_length=1, max_length=50)


class CaisseVenteOut(BaseModel):
    transaction_id: str
    status: Literal["recorded", "already_recorded"]
    lines: int


# ---------------------------------------------------------------------------
# Webhook & sync
# ---------------------------------------------------------------------------


class HelloAssoWebhookPayload(BaseModel):
    """Payload pushed by HelloAsso to our webhook endpoint."""

    eventType: Literal["Order", "Payment", "Form"]
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


class WebhookConfigureIn(BaseModel):
    """Optional override of the URL registered against HelloAsso."""

    url: str | None = None


class WebhookStatusOut(BaseModel):
    """Etat du webhook HelloAsso, tel qu'on peut honnetement le connaitre.

    HelloAsso n'expose aucun moyen de relire l'URL de notification enregistree
    (``GET`` sur la route repond 405). ``configured`` ne peut donc pas etre
    affirme : le declarer ``false`` faisait passer un webhook parfaitement
    fonctionnel pour absent.

    ``last_sale_at`` est la seule preuve verifiable qu'il fonctionne : une vente
    recue est une notification que HelloAsso nous a bel et bien envoyee.
    """

    configured: bool | None = None
    verifiable: bool = False
    url: str | None = None
    # L'adresse a enregistrer chez HelloAsso, jeton compris. Servie meme
    # quand l'enregistrement automatique est impossible : c'est alors la
    # seule chose dont l'utilisateur a besoin, et la recopier de memoire
    # — avec un jeton de 43 caracteres — n'est pas envisageable.
    url_a_enregistrer: str | None = None
    # Vrai quand le compte n'est pas partenaire HelloAsso : l'API refuse
    # alors l'enregistrement (403), et il faut passer par leur interface.
    enregistrement_manuel_requis: bool = False
    last_sale_at: datetime | None = None
    sales_count: int = 0
    raw: dict[str, Any] | None = None


class SyncResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
