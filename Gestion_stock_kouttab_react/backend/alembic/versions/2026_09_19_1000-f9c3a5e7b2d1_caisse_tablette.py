"""La caisse de la buvette : une tablette qui encaisse par SumUp.

Les ventes de la buvette ne passent plus par la boutique HelloAsso mais par une
tablette Android reliee a un terminal SumUp. Un encaissement SumUp ne previent
personne : sans ces colonnes, le stock ne bougeait plus.

- `BuvetteProducts.caisse_category` : l'onglet de la tablette (`sucre_sale`,
  `boissons`, `cafe`). NULL = absent de la tablette — l'etat de tous les
  produits existants, qui n'y apparaitront qu'une fois classes.
- `BuvetteSales.source` : `helloasso` ou `caisse`. Les lignes existantes sont
  toutes venues du webhook : le defaut serveur les etiquette sans UPDATE.
- `BuvetteSales.caisse_tx_id` / `caisse_line` / `sumup_tx_code` : l'identifiant
  de transaction genere par la tablette, le rang de la ligne, le code SumUp.
  L'unicite (`caisse_tx_id`, `caisse_line`) rend la vente idempotente : la
  tablette renvoie tant qu'elle n'a pas eu de reponse. Les lignes HelloAsso
  laissent ces colonnes a NULL, qui ne se heurtent jamais dans un index unique.

Additif et sans risque : colonnes nullables ou a defaut serveur, aucune ecriture
dans les lignes existantes. `batch_alter_table` pour la contrainte : sans effet
sur MariaDB (simple ALTER), indispensable a la base SQLite de developpement,
qui ne sait pas ajouter une contrainte a une table existante.

Revision ID: f9c3a5e7b2d1
Revises: e8b2f4a7c1d5
Create Date: 2026-09-19 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f9c3a5e7b2d1"
down_revision = "e8b2f4a7c1d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "BuvetteProducts", sa.Column("caisse_category", sa.String(20), nullable=True)
    )
    with op.batch_alter_table("BuvetteSales") as batch:
        batch.add_column(
            sa.Column(
                "source", sa.String(20), nullable=False, server_default="helloasso"
            )
        )
        batch.add_column(sa.Column("caisse_tx_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("caisse_line", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("sumup_tx_code", sa.String(64), nullable=True))
        batch.create_unique_constraint(
            "uq_sale_caisse_tx_line", ["caisse_tx_id", "caisse_line"]
        )


def downgrade() -> None:
    with op.batch_alter_table("BuvetteSales") as batch:
        batch.drop_constraint("uq_sale_caisse_tx_line", type_="unique")
        batch.drop_column("sumup_tx_code")
        batch.drop_column("caisse_line")
        batch.drop_column("caisse_tx_id")
        batch.drop_column("source")
    op.drop_column("BuvetteProducts", "caisse_category")
