"""Archiver une facture plutot que l'effacer.

Meme raisonnement que pour les notes de frais (`b8d5f3a0c4e7`), applique la ou
il manquait : `DELETE /invoices/{id}` supprimait la ligne, ses fichiers et leur
contenu en base. La comptabilite pouvait le faire sur **n'importe quelle**
facture, y compris validee — c'est-a-dire deja comptabilisee.

Revision ID: a3c7e5b2f9d4
Revises: f2b9d4e7a1c3
Create Date: 2026-08-14 11:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "a3c7e5b2f9d4"
down_revision = "f2b9d4e7a1c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("Factures", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("Factures", sa.Column("archived_by", sa.Integer(), nullable=True))
    op.create_index("idx_fact_archived", "Factures", ["archived_at"])
    op.create_foreign_key(
        "fk_fact_archived_by",
        "Factures",
        "Admins",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_fact_archived_by", "Factures", type_="foreignkey")
    op.drop_index("idx_fact_archived", table_name="Factures")
    op.drop_column("Factures", "archived_by")
    op.drop_column("Factures", "archived_at")
