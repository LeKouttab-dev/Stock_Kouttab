"""Caisse : etat fin du compte SumUp et du lecteur dans le releve de la tablette.

`sumup_connecte` (booleen) disait « non connecte » apres chaque redemarrage de
l'app, alors que le compte se reveille seul au premier paiement ; le lecteur,
lui, se met en veille (Bluetooth coupe) et se reveille aussi au paiement.

- `CaisseEtats.sumup_etat`  : "connecte" | "enregistre" | "deconnecte" | NULL ;
- `CaisseEtats.lecteur_etat` : "connecte" | "en_veille" | "non_appaire" | NULL.

NULL = releve d'une ancienne version de l'app (ou valeur inconnue) : l'ecran
retombe alors sur les booleens existants, gardes pour compatibilite.

Revision ID: a7b4c9d1e6f8
Revises: f6a3b8c0d5e7
Create Date: 2026-10-10 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "a7b4c9d1e6f8"
down_revision = "f6a3b8c0d5e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("CaisseEtats", sa.Column("sumup_etat", sa.String(length=16), nullable=True))
    op.add_column("CaisseEtats", sa.Column("lecteur_etat", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("CaisseEtats", "lecteur_etat")
    op.drop_column("CaisseEtats", "sumup_etat")
