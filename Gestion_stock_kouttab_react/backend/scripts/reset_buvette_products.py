"""Purge le catalogue buvette local et le reconstruit depuis HelloAsso.

A utiliser quand la boutique HelloAsso a ete refaite : les ``tier_id`` changent
alors integralement, et une synchronisation normale se contente d'ajouter les
nouveaux produits a cote des anciens, devenus orphelins. On se retrouve avec le
catalogue en double, sous deux orthographes, et des ventes qui ne retombent sur
aucun produit.

HelloAsso fait autorite sur le catalogue : ce script supprime les produits
locaux puis relance une synchronisation vierge.

Les ventes (``BuvetteSales``) ne sont jamais supprimees — leur cle etrangere est
``ON DELETE SET NULL`` et chaque vente porte un ``product_name_snapshot``.
L'historique comptable reste donc lisible apres la purge.

Usage :
    python scripts/reset_buvette_products.py            # simulation
    python scripts/reset_buvette_products.py --apply    # execution
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.crud import buvette as buvette_crud  # noqa: E402
from app.db.models import BuvetteProduct, BuvetteSale  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.helloasso import get_helloasso_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="execute reellement la purge (sans ce drapeau, simulation seule)",
    )
    args = parser.parse_args()

    client = get_helloasso_client(settings)
    tiers = client.list_shop_tiers(
        settings.helloasso_org_slug,
        settings.helloasso_buvette_form_slug,
    )

    with SessionLocal() as db:
        products = list(db.execute(select(BuvetteProduct)).scalars().all())
        sales = db.execute(select(func.count()).select_from(BuvetteSale)).scalar_one()

        print(f"Base      : {len(products)} produit(s), {sales} vente(s)")
        print(f"HelloAsso : {len(tiers)} produit(s) dans la boutique "
              f"'{settings.helloasso_buvette_form_slug}'")

        stocked = [p for p in products if p.quantity > 0]
        if stocked:
            print(f"\nATTENTION — {len(stocked)} produit(s) ont encore du stock local, "
                  "il sera perdu :")
            for p in stocked:
                print(f"  {p.name} : {p.quantity}")

        if not args.apply:
            print("\nSimulation. Relancer avec --apply pour executer.")
            return 0

        for product in products:
            db.delete(product)
        db.commit()
        print(f"\n{len(products)} produit(s) supprime(s).")

        result = buvette_crud.sync_from_helloasso(db, tiers)
        print(
            f"Synchronisation : {result.created} cree(s), {result.updated} mis a jour, "
            f"{result.skipped} ignore(s)"
        )
        for err in result.errors:
            print(f"  erreur : {err}")

        remaining = db.execute(select(func.count()).select_from(BuvetteProduct)).scalar_one()
        priced = db.execute(
            select(func.count()).select_from(BuvetteProduct).where(BuvetteProduct.price_cents > 0)
        ).scalar_one()
        print(f"Catalogue final : {remaining} produit(s), dont {priced} avec un prix.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
