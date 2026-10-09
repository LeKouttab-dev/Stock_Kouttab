"""Buvette : inventaire guide (comptage du stock puis des especes).

- `Inventaires` : un inventaire, en trois etats (`en_cours`, `stock_valide`,
  `termine`). `verrou_actif` vaut 1 tant qu'il n'est pas termine, NULL ensuite ;
  l'index unique interdit en base deux inventaires ouverts a la fois.
- `InventaireLignes` : un produit compte. Nom, prix et onglet sont des
  instantanes ; `quantite_theorique` est figee a la validation du stock. Le
  produit passe a NULL s'il est supprime (SET NULL), la ligne reste.

Additif et sans risque : deux tables neuves, aucune ecriture dans l'existant.

Revision ID: c3d9e5f7a2b4
Revises: b2c8d4e6f1a3
Create Date: 2026-10-09 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c3d9e5f7a2b4"
down_revision = "b2c8d4e6f1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Inventaires",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="en_cours"),
        sa.Column("verrou_actif", sa.Integer(), nullable=True),
        sa.Column("debut_le", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("stock_valide_le", sa.DateTime(), nullable=True),
        sa.Column("termine_le", sa.DateTime(), nullable=True),
        sa.Column("cree_par", sa.String(length=255), nullable=True),
        sa.Column("periode_especes_debut", sa.DateTime(), nullable=True),
        sa.Column("periode_especes_fin", sa.DateTime(), nullable=True),
        sa.Column("especes_attendues_cents", sa.Integer(), nullable=True),
        sa.Column("especes_comptees_cents", sa.Integer(), nullable=True),
        sa.Column("ecart_especes_cents", sa.Integer(), nullable=True),
        sa.Column("nb_ventes_especes", sa.Integer(), nullable=True),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.UniqueConstraint("verrou_actif", name="uq_inventaire_verrou_actif"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_inventaire_debut", "Inventaires", ["debut_le"])

    op.create_table(
        "InventaireLignes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "inventaire_id",
            sa.Integer(),
            sa.ForeignKey("Inventaires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "buvette_product_id",
            sa.Integer(),
            sa.ForeignKey("BuvetteProducts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nom_snapshot", sa.String(length=255), nullable=False),
        sa.Column("prix_cents_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("categorie_snapshot", sa.String(length=20), nullable=True),
        sa.Column("quantite_theorique", sa.Integer(), nullable=True),
        sa.Column("quantite_comptee", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ecart", sa.Integer(), nullable=True),
        sa.Column("valeur_ecart_cents", sa.Integer(), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "idx_inventaire_ligne_inventaire", "InventaireLignes", ["inventaire_id"]
    )
    op.create_index(
        "idx_inventaire_ligne_produit", "InventaireLignes", ["buvette_product_id"]
    )


def downgrade() -> None:
    op.drop_table("InventaireLignes")
    op.drop_table("Inventaires")
