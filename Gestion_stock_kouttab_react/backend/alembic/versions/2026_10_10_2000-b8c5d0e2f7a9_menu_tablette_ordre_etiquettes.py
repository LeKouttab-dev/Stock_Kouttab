"""Menu de la tablette : ordre des produits par onglet et etiquettes.

- `BuvetteProducts.ordre_caisse` (int, NULL) : rang du produit dans son onglet
  de la tablette (1..n). NULL = pas encore range : le produit passe apres les
  produits ranges, par ordre alphabetique (comportement d'avant).
- `BuvetteProducts.etiquette_type` (String(24), NULL) : `nouveaute`,
  `edition_limitee`, `derniers`, `coup_de_coeur`, `promo` ou `libre`.
- `BuvetteProducts.etiquette_texte` (String(20), NULL) : le texte d'une
  etiquette `libre` (20 caracteres au plus), vide pour les autres types.

Migration additive (colonnes nullables, aucune donnee reecrite).

Revision ID: b8c5d0e2f7a9
Revises: a7b4c9d1e6f8
Create Date: 2026-10-10 20:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8c5d0e2f7a9"
down_revision = "a7b4c9d1e6f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("BuvetteProducts", sa.Column("ordre_caisse", sa.Integer(), nullable=True))
    op.add_column(
        "BuvetteProducts", sa.Column("etiquette_type", sa.String(length=24), nullable=True)
    )
    op.add_column(
        "BuvetteProducts", sa.Column("etiquette_texte", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("BuvetteProducts", "etiquette_texte")
    op.drop_column("BuvetteProducts", "etiquette_type")
    op.drop_column("BuvetteProducts", "ordre_caisse")
