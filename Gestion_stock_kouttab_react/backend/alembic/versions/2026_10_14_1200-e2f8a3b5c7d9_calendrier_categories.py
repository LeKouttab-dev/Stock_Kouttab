"""Calendrier : categorie et sous-categorie d'un agenda, pour le filtre en arbre.

Deux colonnes nullables sur `CalendrierAgendaReglages` :

- `categorie`, `sous_categorie` : la place de l'agenda dans le filtre, quand le
  calcul depuis le nom (`calendrier_salles.categorie_de`) tombe mal.

Purement additive, aucune donnee touchee : vide = calcule depuis le nom, ce qui
est le comportement de toutes les lignes existantes.

Revision ID: e2f8a3b5c7d9
Revises: d1e7f2a4b6c8
Create Date: 2026-10-14 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2f8a3b5c7d9"
down_revision = "d1e7f2a4b6c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "CalendrierAgendaReglages", sa.Column("categorie", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "CalendrierAgendaReglages",
        sa.Column("sous_categorie", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("CalendrierAgendaReglages", "sous_categorie")
    op.drop_column("CalendrierAgendaReglages", "categorie")
