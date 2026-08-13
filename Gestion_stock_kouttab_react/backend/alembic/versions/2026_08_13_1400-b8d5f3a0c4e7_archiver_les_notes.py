"""Archiver une note de frais plutot que l'effacer.

`DELETE /expenses/{id}` supprimait la ligne, et l'endpoint effacait ensuite les
justificatifs sur le disque. Une piece comptable que l'association doit conserver
plusieurs annees disparaissait donc sur un clic, sans qu'aucune trace ne dise
qu'elle avait existe.

Deux colonnes suffisent : la note sort des listes courantes, reste en base avec
ses justificatifs, et se restaure.

Revision ID: b8d5f3a0c4e7
Revises: a7c4e2f9b3d6
Create Date: 2026-08-13 14:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b8d5f3a0c4e7"
down_revision = "a7c4e2f9b3d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("NotesDeFrais", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("NotesDeFrais", sa.Column("archived_by", sa.Integer(), nullable=True))
    # Index sur la colonne qui filtre desormais toutes les listes.
    op.create_index("idx_nf_archived", "NotesDeFrais", ["archived_at"])
    # `SET NULL` et non `CASCADE` : supprimer le compte de celui qui a archive ne
    # doit pas emporter la note archivee — c'est tout l'objet de la migration.
    op.create_foreign_key(
        "fk_nf_archived_by",
        "NotesDeFrais",
        "Admins",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_nf_archived_by", "NotesDeFrais", type_="foreignkey")
    op.drop_index("idx_nf_archived", table_name="NotesDeFrais")
    op.drop_column("NotesDeFrais", "archived_by")
    op.drop_column("NotesDeFrais", "archived_at")
