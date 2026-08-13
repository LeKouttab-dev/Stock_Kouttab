"""La comptabilite peut ecarter un justificatif errone, sans le detruire.

Une piece illisible, ou rattachee a la mauvaise note, ne pouvait ni etre retiree
ni etre remplacee : `attach_file` n'etait appele qu'a la creation, et l'ecran
conseillait meme de « supprimer cette note et la recreer ».

Ecarter plutot qu'effacer, comme pour les notes elles-memes : la piece sort du
dossier, reste en base, et se restaure. Le motif accompagne le geste — le
deposant doit savoir ce qu'on lui reproche pour redeposer ce qu'il faut.

Revision ID: f2b9d4e7a1c3
Revises: e1a8c3d6f0b2
Create Date: 2026-08-14 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f2b9d4e7a1c3"
down_revision = "e1a8c3d6f0b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("FichiersNotesDeFrais", sa.Column("ecarte_at", sa.DateTime(), nullable=True))
    op.add_column("FichiersNotesDeFrais", sa.Column("ecarte_par", sa.Integer(), nullable=True))
    op.add_column("FichiersNotesDeFrais", sa.Column("motif_ecart", sa.String(255), nullable=True))
    op.create_index("idx_fnf_ecarte", "FichiersNotesDeFrais", ["ecarte_at"])
    # `SET NULL` : supprimer le compte du comptable ne doit pas emporter la
    # piece ecartee, ni la faire reapparaitre au dossier.
    op.create_foreign_key(
        "fk_fnf_ecarte_par",
        "FichiersNotesDeFrais",
        "Admins",
        ["ecarte_par"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_fnf_ecarte_par", "FichiersNotesDeFrais", type_="foreignkey")
    op.drop_index("idx_fnf_ecarte", table_name="FichiersNotesDeFrais")
    for colonne in ("motif_ecart", "ecarte_par", "ecarte_at"):
        op.drop_column("FichiersNotesDeFrais", colonne)
