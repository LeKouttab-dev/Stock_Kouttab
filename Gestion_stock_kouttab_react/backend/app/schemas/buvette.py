"""Buvette / HelloAsso schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


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
    last_sale_at: datetime | None = None
    sales_count: int = 0
    raw: dict[str, Any] | None = None


class SyncResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
