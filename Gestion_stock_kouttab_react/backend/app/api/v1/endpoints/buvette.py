"""Buvette / HelloAsso endpoints."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.crud import buvette as buvette_crud
from app.db.models import Admin
from app.db.session import SessionLocal, get_db
from app.schemas.auth import MessageOut
from app.schemas.buvette import (
    BuvetteProductCreate,
    BuvetteProductOut,
    BuvetteProductUpdate,
    BuvetteSaleOut,
    HelloAssoWebhookPayload,
    SyncResult,
    WebhookConfigureIn,
    WebhookStatusOut,
)
from app.services import email as email_service
from app.services.helloasso import get_helloasso_client


logger = get_logger("api.buvette")
router = APIRouter(prefix="/buvette", tags=["buvette"])


_ADMIN_ROLES = ("AdminBenevoles", "Super Admin")
_SUPER_ADMIN = ("Super Admin",)
# Lecture du stock et des ventes : les administrateurs benevoles qui tiennent la
# buvette, et la comptabilite qui en suit les recettes. Un simple benevole n'y a
# pas acces — la buvette est un outil de gestion, pas un ecran de consultation.
_VIEW_ROLES = ("AdminBenevoles", "Super Admin", "Compta")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get(
    "/products",
    response_model=list[BuvetteProductOut],
    dependencies=[Depends(require_roles(*_VIEW_ROLES))],
)
def list_products(db: Session = Depends(get_db)) -> Any:
    return [BuvetteProductOut.model_validate(p) for p in buvette_crud.list_products(db)]


@router.post(
    "/products",
    response_model=BuvetteProductOut,
    status_code=201,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def create_product(payload: BuvetteProductCreate, db: Session = Depends(get_db)) -> Any:
    product = buvette_crud.create_product(db, payload)
    return BuvetteProductOut.model_validate(product)


@router.patch(
    "/products/{product_id}",
    response_model=BuvetteProductOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def update_product(
    product_id: int,
    payload: BuvetteProductUpdate,
    db: Session = Depends(get_db),
) -> Any:
    product = buvette_crud.update_product(db, product_id, payload)
    return BuvetteProductOut.model_validate(product)


@router.delete(
    "/products/{product_id}",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> Any:
    buvette_crud.delete_product(db, product_id)
    return MessageOut(message="Produit buvette supprime.")


@router.get("/products/by-barcode/{barcode}", response_model=BuvetteProductOut)
def get_product_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_user),
) -> Any:
    """Return the buvette product linked to ``barcode``. ``404`` if unknown."""
    product = buvette_crud.get_product_by_barcode(db, barcode.strip())
    if product is None:
        raise AppException(ErrorCode.BUVETTE_PRODUCT_NOT_FOUND)
    return BuvetteProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# Sync (HelloAsso shop tiers -> local products)
# ---------------------------------------------------------------------------


@router.post(
    "/sync",
    response_model=SyncResult,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def sync_products(db: Session = Depends(get_db)) -> Any:
    client = get_helloasso_client(settings)
    tiers = client.list_shop_tiers(
        settings.helloasso_org_slug,
        settings.helloasso_buvette_form_slug,
    )
    result = buvette_crud.sync_from_helloasso(db, tiers)
    logger.info(
        "Buvette sync done: created=%d updated=%d skipped=%d errors=%d",
        result.created,
        result.updated,
        result.skipped,
        len(result.errors),
    )
    return result


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


@router.get(
    "/sales",
    response_model=list[BuvetteSaleOut],
    dependencies=[Depends(require_roles(*_VIEW_ROLES))],
)
def list_sales(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Any:
    """Historique des ventes buvette : administrateurs benevoles et comptabilite.

    La buvette est un outil de gestion : stock et chiffre des ventes n'ont pas a
    etre exposes a l'ensemble des comptes. Cette route a d'abord ete ouverte a
    tout compte authentifie, ce qui donnait aussi la vue aux benevoles.
    """
    return [
        BuvetteSaleOut.model_validate(s)
        for s in buvette_crud.list_sales(db, limit=limit, offset=offset)
    ]


# ---------------------------------------------------------------------------
# Webhook (called by HelloAsso — no auth)
# ---------------------------------------------------------------------------


def _parse_sold_at(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # HelloAsso uses ISO 8601, sometimes with trailing Z.
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _slug_du_formulaire(order: dict[str, Any]) -> str | None:
    """Boutique ou billetterie d'ou vient la commande.

    HelloAsso le place tantot a la racine, tantot sous `formSlug`/`formType`
    dans un sous-objet selon l'evenement. On regarde les deux.
    """
    direct = order.get("formSlug")
    if isinstance(direct, str):
        return direct
    formulaire = order.get("form")
    if isinstance(formulaire, dict):
        slug = formulaire.get("formSlug") or formulaire.get("slug")
        if isinstance(slug, str):
            return slug
    return None


def _concerne_la_buvette(order: dict[str, Any]) -> bool:
    """Ecarte tout ce qui ne vient pas de la boutique buvette.

    **Indispensable.** L'association n'a droit qu'a UNE URL de notification pour
    tout son compte : la meme adresse recoit les ventes de la buvette ET les
    inscriptions aux stages. Sans ce filtre, une inscription a un stage serait
    enregistree comme une vente et decrementerait un stock qui n'a rien a voir.

    Le relais WordPress filtre deja, mais un filtre cote emetteur ne protege que
    tant qu'il fonctionne : celui-ci est le notre, et il ne depend de personne.

    Un slug absent est accepte : les commandes de la boutique n'en portent pas
    toujours selon le type d'evenement, et refuser par defaut ferait perdre des
    ventes reelles. Le refus est reserve a un slug present et different.
    """
    slug = _slug_du_formulaire(order)
    if slug is None:
        return True
    return slug.strip().lower() == settings.helloasso_buvette_form_slug.strip().lower()


def _process_order(
    db: Session,
    order: dict[str, Any],
    background: BackgroundTasks,
    raw_event: dict[str, Any],
) -> None:
    """Iterate over order items and record sales."""
    if not _concerne_la_buvette(order):
        logger.info(
            "Commande HelloAsso ignoree : formulaire=%s (attendu : %s).",
            _slug_du_formulaire(order),
            settings.helloasso_buvette_form_slug,
        )
        return

    order_id = order.get("id")
    payer = order.get("payer") or {}
    items = order.get("items") or []
    sold_at = _parse_sold_at(order.get("date") or order.get("orderDate"))

    if not items:
        logger.info("HelloAsso order %s has no items, skipping.", order_id)
        return

    for item in items:
        try:
            item_id = item.get("id")
            tier_id = item.get("tierId") or item.get("priceId")
            payment_id = item.get("paymentId") or item.get("payment_id")
            if payment_id is None:
                # Fall back to order-level payment id.
                payment_id = order.get("paymentId") or order.get("payment_id")
            qty = item.get("quantity") or 1
            try:
                qty_int = int(qty)
            except (TypeError, ValueError):
                qty_int = 1
            amount = item.get("amount") or 0
            try:
                amount_int = int(amount)
            except (TypeError, ValueError):
                amount_int = 0
            name = item.get("name") or item.get("label") or "Produit buvette"

            customer = item.get("user") or item.get("customer") or payer

            sale, decremented_product = buvette_crud.record_sale_and_decrement(
                db,
                order_id=int(order_id) if order_id is not None else None,
                payment_id=int(payment_id) if payment_id is not None else None,
                item_id=int(item_id) if item_id is not None else None,
                tier_id=int(tier_id) if tier_id is not None else None,
                name=name,
                quantity_sold=qty_int,
                amount_cents=amount_int,
                customer={
                    "firstName": customer.get("firstName") or customer.get("first_name"),
                    "lastName": customer.get("lastName") or customer.get("last_name"),
                    "email": customer.get("email"),
                },
                sold_at=sold_at,
                raw_event=raw_event,
            )

            if (
                decremented_product is not None
                and decremented_product.quantity < decremented_product.seuil_alerte
                and not decremented_product.alert_sent
            ):
                # Flag now to avoid duplicate emails before the background task runs.
                decremented_product.alert_sent = True
                db.commit()
                background.add_task(
                    _send_buvette_alert_safe,
                    decremented_product.name,
                    decremented_product.quantity,
                    decremented_product.seuil_alerte,
                )

            logger.info(
                "Buvette sale recorded: sale_id=%s order_id=%s item_id=%s tier_id=%s qty=%d",
                sale.id,
                order_id,
                item_id,
                tier_id,
                qty_int,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error processing HelloAsso item: %s", exc)


def _webhook_secret_ok(provided: str | None) -> bool:
    """Compare le secret d'URL en temps constant.

    C'est la SEULE protection de cet endpoint : il est public, HelloAsso ne
    presente aucune session. Accepter un `Order` forge cree des lignes de vente
    et decremente le stock.

    **Sans secret configure, la production refuse.** Elle laissait tout passer
    — « comportement historique » — et le 2026-08-13 elle tournait effectivement
    avec `HELLOASSO_WEBHOOK_SECRET` vide : n'importe qui connaissant l'URL
    pouvait vider l'inventaire. Un avertissement dans les journaux ne protege
    rien, personne ne les lit.

    Le developpement reste tolerant : aucune machine locale n'a de secret, et la
    buvette doit rester testable.
    """
    expected = settings.helloasso_webhook_secret
    if not expected:
        if settings.is_production:
            logger.error(
                "Webhook HelloAsso REFUSE : HELLOASSO_WEBHOOK_SECRET est vide. "
                "Definir la variable, redemarrer, puis reenregistrer le webhook "
                "depuis Buvette > Configurer le webhook."
            )
            return False
        logger.warning(
            "Webhook HelloAsso non protege : definir HELLOASSO_WEBHOOK_SECRET."
        )
        return True
    return secrets.compare_digest(provided or "", expected)


@router.post("/webhook/helloasso", include_in_schema=True)
async def helloasso_webhook(
    request: Request,
    background: BackgroundTasks,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Receive HelloAsso notifications. **Public** — no JWT required."""
    if not _webhook_secret_ok(token):
        logger.warning(
            "Webhook HelloAsso rejete : secret invalide (ip=%s).",
            request.client.host if request.client else "?",
        )
        # 200 volontaire : un 4xx renseignerait un attaquant sur l'existence du
        # secret, et HelloAsso ne doit de toute facon jamais voir d'erreur.
        return {"status": "ignored", "reason": "unauthorized"}
    try:
        raw_body = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("HelloAsso webhook: invalid JSON body: %s", exc)
        # Return 200 anyway — HelloAsso retries on 5xx; we don't want loops on bad bodies.
        return {"status": "ignored", "reason": "invalid_json"}

    try:
        payload = HelloAssoWebhookPayload.model_validate(raw_body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("HelloAsso webhook: invalid payload schema: %s body=%s", exc, raw_body)
        return {"status": "ignored", "reason": "invalid_schema"}

    logger.info("HelloAsso webhook received: eventType=%s", payload.eventType)
    try:
        if payload.eventType == "Order":
            _process_order(db, payload.data, background, raw_body)
        elif payload.eventType == "Payment":
            order = payload.data.get("order")
            if order:
                _process_order(db, order, background, raw_body)
            else:
                logger.info("HelloAsso Payment event without order — ignoring.")
        elif payload.eventType == "Form":
            logger.info("HelloAsso Form event — ignored.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("HelloAsso webhook processing failed: %s", exc)
        # Always return 200 to avoid HelloAsso retry storms.

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Webhook configuration
# ---------------------------------------------------------------------------


def _default_webhook_url() -> str:
    base = settings.backend_url.rstrip("/")
    url = f"{base}/v1/buvette/webhook/helloasso"
    # Le secret voyage dans l'URL enregistree chez HelloAsso : c'est la seule
    # forme d'authentification qu'accepte leur systeme de notifications.
    if settings.helloasso_webhook_secret:
        url = f"{url}?token={quote(settings.helloasso_webhook_secret, safe='')}"
    return url


@router.post(
    "/webhook/configure",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_SUPER_ADMIN))],
)
def configure_webhook(payload: WebhookConfigureIn) -> Any:
    """Enregistre l'URL de notification chez HelloAsso.

    **Ne fonctionne que pour un compte partenaire.** L'endpoint
    `/v5/partners/me/api-notifications` leur est reserve ; une association
    ordinaire recoit un 403 au corps vide, sans la moindre explication. Sa
    documentation le dit : elle passe par « Mon Compte > Integrations et API ».

    On traduit donc ce 403 en consigne exploitable, avec l'adresse a recopier —
    un jeton de 43 caracteres ne se retient pas.
    """
    url = (payload.url or _default_webhook_url()).strip()
    client = get_helloasso_client(settings)
    try:
        client.register_webhook(settings.helloasso_org_slug, url)
    except AppException as exc:
        if exc.extras.get("upstream_status") != 403:
            raise
        logger.info(
            "Compte HelloAsso non partenaire : enregistrement automatique refuse. "
            "URL a saisir manuellement : %s",
            url,
        )
        raise AppException(
            ErrorCode.HELLOASSO_API_ERROR,
            detail=(
                "HelloAsso reserve l'enregistrement automatique a ses comptes "
                "partenaires, et refuse le votre (403). Enregistrez l'adresse a "
                "la main depuis HelloAsso : Mon Compte > Integrations et API. "
                "L'adresse a coller, jeton compris, est affichee ci-dessous."
            ),
            extras={"upstream_status": 403, "url_a_enregistrer": url},
            # 409 et non le 502 par defaut du code d'erreur. Un 502 annonce une
            # panne passagere — « reessayez plus tard » — alors que la reponse
            # est definitive : ce compte n'aura jamais ce droit. Et un
            # intermediaire peut remplacer le corps d'un 502 par sa propre page
            # d'erreur, ce qui ferait disparaitre la consigne, qui est ici tout
            # l'interet de la reponse.
            status_code=409,
        ) from exc
    return MessageOut(message=f"Webhook HelloAsso configure sur {url}.")


@router.get(
    "/webhook/status",
    response_model=WebhookStatusOut,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
def webhook_status(db: Session = Depends(get_db)) -> Any:
    client = get_helloasso_client(settings)
    raw = client.get_webhook(settings.helloasso_org_slug)

    # Les ventes deja recues sont la seule preuve directe que HelloAsso nous
    # appelle : chacune est arrivee par le webhook. Elles servent de repli quand
    # HelloAsso refuse de relire sa propre configuration.
    last_sale_at, sales_count = buvette_crud.get_sales_activity(db)

    a_coller = _default_webhook_url()

    if not raw:
        return WebhookStatusOut(
            configured=True if sales_count else None,
            verifiable=False,
            url=None,
            url_a_enregistrer=a_coller,
            last_sale_at=last_sale_at,
            sales_count=sales_count,
            raw=None,
        )
    url = raw.get("url") if isinstance(raw, dict) else None
    return WebhookStatusOut(
        configured=bool(url),
        verifiable=True,
        url=url,
        url_a_enregistrer=a_coller,
        last_sale_at=last_sale_at,
        sales_count=sales_count,
        raw=raw,
    )


@router.delete(
    "/webhook",
    response_model=MessageOut,
    dependencies=[Depends(require_roles(*_SUPER_ADMIN))],
)
def delete_webhook() -> Any:
    client = get_helloasso_client(settings)
    client.delete_webhook(settings.helloasso_org_slug)
    return MessageOut(message="Webhook HelloAsso supprime.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _send_buvette_alert_safe(
    product_name: str, quantity: int, threshold: int
) -> None:
    """Background-safe wrapper that opens its own DB session."""
    db = SessionLocal()
    try:
        await email_service.send_buvette_low_stock_alert(
            db,
            product_name=product_name,
            quantity=quantity,
            threshold=threshold,
        )
    finally:
        db.close()
