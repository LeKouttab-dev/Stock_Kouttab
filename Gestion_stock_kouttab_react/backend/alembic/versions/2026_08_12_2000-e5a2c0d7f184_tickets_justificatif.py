"""Tickets de justificatif : demander une piece manquante, et relancer.

La comptabilite sait qu'un achat a eu lieu mais n'a pas la facture. Elle
relancait de memoire, par messages prives, sans trace — impossible de savoir
qui avait deja ete relance, ni combien de pieces manquaient a la cloture.

Table additive : rien de l'existant n'est touche.

Revision ID: e5a2c0d7f184
Revises: d4f1b9c5e63a
Create Date: 2026-08-12 20:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "e5a2c0d7f184"
down_revision = "d4f1b9c5e63a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TicketsJustificatif",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.Column("cree_par", sa.Integer(), nullable=True),
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Facultatifs : un ticket s'ouvre avec ce que la comptabilite sait, et
        # la relance ne mentionne que ce qui est renseigne.
        sa.Column("montant_attendu", sa.DECIMAL(10, 2), nullable=True),
        sa.Column("date_achat", sa.Date(), nullable=True),
        sa.Column("fournisseur", sa.String(255), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="ouvert"),
        sa.Column("id_facture", sa.Integer(), nullable=True),
        sa.Column("rappels_envoyes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dernier_rappel_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["id_user"], ["Admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cree_par"], ["Admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by"], ["Admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["id_facture"], ["Factures.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_ticket_user", "TicketsJustificatif", ["id_user"])
    op.create_index("idx_ticket_statut", "TicketsJustificatif", ["statut"])


def downgrade() -> None:
    op.drop_index("idx_ticket_statut", table_name="TicketsJustificatif")
    op.drop_index("idx_ticket_user", table_name="TicketsJustificatif")
    op.drop_table("TicketsJustificatif")
