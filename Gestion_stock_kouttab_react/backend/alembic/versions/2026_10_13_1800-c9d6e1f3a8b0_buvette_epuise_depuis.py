"""Buvette : date d'epuisement, pour masquer de la tablette les produits a 0.

- `BuvetteProducts.epuise_depuis` (DateTime, NULL) : instant ou le stock est
  tombe a 0, NULL des qu'il repasse au-dessus. Au-dela de 7 jours, le produit
  sort du catalogue de la tablette (hors cafes) ; `is_active` n'est pas touche.

Les produits deja a 0 recoivent la date de la migration : le delai de 7 jours
part de la mise en ligne. Avec la date de leur derniere vente, presque tout le
menu disparaitrait d'un coup (stocks remis a 0 le 10/10 en attendant
l'inventaire n° 1). Un seul UPDATE, borne a ces produits.

Revision ID: c9d6e1f3a8b0
Revises: b8c5d0e2f7a9
Create Date: 2026-10-13 18:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "c9d6e1f3a8b0"
down_revision = "b8c5d0e2f7a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("BuvetteProducts", sa.Column("epuise_depuis", sa.DateTime(), nullable=True))
    maintenant = datetime.now(timezone.utc).replace(tzinfo=None)
    op.get_bind().execute(
        sa.text(
            "UPDATE BuvetteProducts SET epuise_depuis = :maintenant "
            "WHERE quantity <= 0 AND epuise_depuis IS NULL"
        ),
        {"maintenant": maintenant},
    )


def downgrade() -> None:
    op.drop_column("BuvetteProducts", "epuise_depuis")
