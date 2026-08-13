"""Le deposant est prevenu dans l'application, pas seulement par courriel.

Un commentaire de la comptabilite n'allumait rien : il fallait ouvrir « Mes
demandes » et reperer soi-meme l'encart. Le seul canal etait un courriel
best-effort, qui n'arrivait pas quand `EMAIL_ENABLED` etait tombe.

`non_lu_demandeur` reprend le patron eprouve sur `Conversations` : une colonne
denormalisee, allumee a chaque decision de la comptabilite, eteinte quand le
deposant ouvre sa liste. C'est exactement la question que pose la pastille a
chaque chargement de page ; la deduire imposerait une sous-requete a chaque fois,
vers une base distante.

`Factures.commentaires_compta` comble un autre manque : une facture refusee
arrivait **sans motif**, la colonne n'existant nulle part.

Revision ID: e1a8c3d6f0b2
Revises: d0f7b2c5e8a9
Create Date: 2026-08-13 23:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "e1a8c3d6f0b2"
down_revision = "d0f7b2c5e8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("NotesDeFrais", "Factures"):
        op.add_column(
            table,
            sa.Column(
                "non_lu_demandeur", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
        op.create_index(f"idx_{table.lower()}_non_lu", table, ["non_lu_demandeur"])

    # Les pieces existantes ne s'allument pas retroactivement : reveiller des
    # pastilles sur des dossiers traites il y a des mois ferait prendre le
    # signal pour du bruit des le premier jour.
    op.add_column("Factures", sa.Column("commentaires_compta", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("Factures", "commentaires_compta")
    for table in ("NotesDeFrais", "Factures"):
        op.drop_index(f"idx_{table.lower()}_non_lu", table_name=table)
        op.drop_column(table, "non_lu_demandeur")
