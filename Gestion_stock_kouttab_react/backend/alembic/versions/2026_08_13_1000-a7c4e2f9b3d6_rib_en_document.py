"""Le releve d'identite bancaire depose en document, a cote de l'IBAN saisi.

L'IBAN tape a la main sert au virement ; le document de la banque sert de
preuve, et c'est lui que la comptabilite reclamait par messages prives faute de
pouvoir le recuperer dans l'application.

Stockage EN BASE, comme les justificatifs et pour la meme raison (migration
`f6b3d1e8a295`) : la base est sauvegardee, pas le disque du VPS.

Le contenu n'est pas chiffre, contrairement a la colonne `rib` : `ChampChiffre`
travaille sur du texte, et la protection utile sur un document est le controle
d'acces — proprietaire, Compta, Super Admin.

Revision ID: a7c4e2f9b3d6
Revises: f6b3d1e8a295
Create Date: 2026-08-13 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGBLOB


revision = "a7c4e2f9b3d6"
down_revision = "f6b3d1e8a295"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "Admins",
        sa.Column("rib_document", sa.LargeBinary().with_variant(LONGBLOB(), "mysql"), nullable=True),
    )
    op.add_column("Admins", sa.Column("rib_document_nom", sa.String(255), nullable=True))
    op.add_column("Admins", sa.Column("rib_document_type", sa.String(100), nullable=True))


def downgrade() -> None:
    # Les documents deposes sont perdus : ils n'existent qu'ici, sans copie
    # disque contrairement aux justificatifs. Sauvegarder avant.
    for colonne in ("rib_document_type", "rib_document_nom", "rib_document"):
        op.drop_column("Admins", colonne)
