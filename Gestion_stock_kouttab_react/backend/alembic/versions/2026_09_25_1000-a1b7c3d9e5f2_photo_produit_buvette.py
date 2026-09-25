"""La photo d'un produit de la buvette, deposee depuis l'application.

La tablette de caisse affiche `image_url` — jusqu'ici uniquement l'adresse
fournie par HelloAsso ou par le scan de code-barres. Un produit saisi a la main
n'avait donc aucune photo, et aucune ne pouvait etre corrigee.

- `photo` / `photo_type` : l'image EN BASE, comme les justificatifs et le RIB.
  Le disque du VPS n'est pas sauvegarde, la base l'est : une photo posee sur le
  volume disparaitrait avec lui. Elle est reduite a 600 px de large avant
  enregistrement (`services/images.py`), soit quelques dizaines de kilo-octets
  — la tablette affiche des fiches de 168 dp.
- `photo_jeton` : l'adresse publique sous laquelle la photo est servie
  (`/buvette/photos/{jeton}`). Un jeton NEUF est tire a chaque depot, et c'est
  volontaire : la tablette met les photos en cache **par URL** en ignorant les
  en-tetes de cache, si bien qu'une photo remplacee a la meme adresse y
  resterait l'ancienne, parfois des jours.
- `edite_manuellement` : la synchronisation HelloAsso ecrasait le nom, la
  description, le prix et la photo a chaque passage. Rendre ces champs
  modifiables sans ce garde-fou aurait fait disparaitre le travail de la
  personne au premier clic sur « Synchroniser ». Le drapeau se leve tout seul
  des qu'un de ces champs est modifie a la main.

Additif et sans risque : colonnes nullables ou a defaut serveur, aucune ecriture
dans les lignes existantes.

Revision ID: a1b7c3d9e5f2
Revises: f9c3a5e7b2d1
Create Date: 2026-09-25 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision = "a1b7c3d9e5f2"
down_revision = "f9c3a5e7b2d1"
branch_labels = None
depends_on = None


# LONGBLOB sur MySQL (4 Go), BLOB ailleurs : la base de developpement est en
# SQLite, qui ne connait pas le type MySQL.
_BLOB = sa.LargeBinary().with_variant(mysql.LONGBLOB(), "mysql")


def upgrade() -> None:
    op.add_column("BuvetteProducts", sa.Column("photo", _BLOB, nullable=True))
    op.add_column(
        "BuvetteProducts", sa.Column("photo_type", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "BuvetteProducts", sa.Column("photo_jeton", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "BuvetteProducts",
        sa.Column(
            "edite_manuellement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Index UNIQUE : le jeton est la cle de lecture de l'adresse publique, et
    # deux produits ne doivent jamais servir la meme photo.
    op.create_index(
        "idx_buvette_prod_photo_jeton", "BuvetteProducts", ["photo_jeton"], unique=True
    )


def downgrade() -> None:
    op.drop_index("idx_buvette_prod_photo_jeton", table_name="BuvetteProducts")
    op.drop_column("BuvetteProducts", "edite_manuellement")
    op.drop_column("BuvetteProducts", "photo_jeton")
    op.drop_column("BuvetteProducts", "photo_type")
    op.drop_column("BuvetteProducts", "photo")
