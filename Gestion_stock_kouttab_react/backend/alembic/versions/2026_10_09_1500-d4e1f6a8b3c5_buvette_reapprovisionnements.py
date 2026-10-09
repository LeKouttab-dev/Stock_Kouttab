"""Buvette : reapprovisionnements traces (prix d'achat, stock avant / apres).

- `BuvetteReapprovisionnements` : un reappro, origine `app` (prix d'achat
  obligatoire) ou `tablette` (sans prix). Nom du produit fige ; le produit passe
  a NULL s'il est supprime (SET NULL), la ligne reste.
- `BuvetteProducts.dernier_prix_achat_cents` : pre-remplissage du prochain
  reappro.

Additif et sans risque : une table neuve et une colonne nullable.

Revision ID: d4e1f6a8b3c5
Revises: c3d9e5f7a2b4
Create Date: 2026-10-09 15:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d4e1f6a8b3c5"
down_revision = "c3d9e5f7a2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "BuvetteProducts",
        sa.Column("dernier_prix_achat_cents", sa.Integer(), nullable=True),
    )

    op.create_table(
        "BuvetteReapprovisionnements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "buvette_product_id",
            sa.Integer(),
            sa.ForeignKey("BuvetteProducts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nom_snapshot", sa.String(length=255), nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False),
        sa.Column("prix_achat_unitaire_cents", sa.Integer(), nullable=True),
        sa.Column("total_cents", sa.Integer(), nullable=True),
        sa.Column("origine", sa.String(length=20), nullable=False, server_default="app"),
        sa.Column("commentaire", sa.String(length=255), nullable=True),
        sa.Column("fait_par", sa.String(length=255), nullable=True),
        sa.Column("stock_avant", sa.Integer(), nullable=False),
        sa.Column("stock_apres", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantite > 0", name="ck_reappro_quantite_positive"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_reappro_created", "BuvetteReapprovisionnements", ["created_at"])
    op.create_index("idx_reappro_produit", "BuvetteReapprovisionnements", ["buvette_product_id"])


def downgrade() -> None:
    op.drop_table("BuvetteReapprovisionnements")
    op.drop_column("BuvetteProducts", "dernier_prix_achat_cents")
