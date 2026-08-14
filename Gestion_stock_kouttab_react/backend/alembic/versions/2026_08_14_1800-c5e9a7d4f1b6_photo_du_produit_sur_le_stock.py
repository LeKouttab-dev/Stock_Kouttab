"""La photo du produit, conservee sur l'article de stock.

Le scan d'un code-barres interroge OpenFoodFacts et affiche la photo du produit
dans l'apercu. Elle etait ensuite **jetee** : l'article cree n'en gardait rien,
et la liste du stock retombait sur l'emoji.

Une adresse, et non les octets. Contrairement aux justificatifs — stockes en
base parce que leur perte est irreparable et que le disque du VPS n'est pas
sauvegarde —, cette image est publique, remplacable, et sa disparition ne coute
rien : l'emoji reprend sa place. La mettre en base ferait de surcroit payer un
aller-retour vers une base **distante** par vignette affichee, sur un ecran qui
en montre plusieurs dizaines a la fois.

C'est deja le choix fait pour `BuvetteProducts.image_url`, pour le meme usage.

Additif et sans risque : la colonne est nullable, les articles existants la
laissent vide et continuent d'afficher leur emoji.

Revision ID: c5e9a7d4f1b6
Revises: b4d8f6c3e0a5
Create Date: 2026-08-14 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c5e9a7d4f1b6"
down_revision = "b4d8f6c3e0a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("Stock", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("Stock", "image_url")
