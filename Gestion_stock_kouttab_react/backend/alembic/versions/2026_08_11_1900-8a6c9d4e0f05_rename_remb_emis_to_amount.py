"""Remplace NotesDeFrais.remb_emis (booleen) par un montant.

Le modele attend ``remboursement_deja_emis`` en DECIMAL(10,2) depuis que l'UI
accepte un montant d'avance recu, alors que le schema legacy Streamlit porte un
``remb_emis`` booleen. Aucune migration ne faisait la conversion : en production,
toute creation de note de frais echouait, la colonne héritée etant NOT NULL sans
valeur par defaut cote application.

La conversion est volontairement conservatrice. Un booleen ne dit pas *combien*
a ete rembourse : `1` devient `0` et non un montant invente. Aucune note n'est
concernee aujourd'hui — la table est vide en production — mais la regle doit
rester juste si la migration est rejouee sur une base qui en contient.

Revision ID: 8a6c9d4e0f05
Revises: 6f5b8c3d9e04
Create Date: 2026-08-11 19:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "8a6c9d4e0f05"
down_revision = "6f5b8c3d9e04"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    colonnes = _colonnes("NotesDeFrais")

    if "remboursement_deja_emis" not in colonnes:
        op.add_column(
            "NotesDeFrais",
            sa.Column(
                "remboursement_deja_emis",
                sa.DECIMAL(10, 2),
                nullable=False,
                server_default="0",
            ),
        )

    # `remb_emis` peut manquer : les bases creees apres la refonte ne l'ont
    # jamais eue. La migration doit rester rejouable sur les deux.
    if "remb_emis" in colonnes:
        op.drop_column("NotesDeFrais", "remb_emis")


def downgrade() -> None:
    colonnes = _colonnes("NotesDeFrais")

    if "remb_emis" not in colonnes:
        op.add_column(
            "NotesDeFrais",
            sa.Column("remb_emis", sa.Boolean(), nullable=True),
        )

    if "remboursement_deja_emis" in colonnes:
        op.drop_column("NotesDeFrais", "remboursement_deja_emis")
