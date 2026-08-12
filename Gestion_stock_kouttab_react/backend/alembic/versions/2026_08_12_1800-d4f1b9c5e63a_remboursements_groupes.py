"""Remboursements groupes : un versement solde plusieurs notes de frais.

La comptabilite ne rembourse pas note par note — elle vire un montant a un
benevole, couvrant toutes ses depenses approuvees. Cette table represente ce
versement et porte le bloc « Apurement » du justificatif remis : date, moyen,
etablissement, approbateur.

Entierement additif : aucune colonne existante n'est touchee, et les notes deja
remboursees restent valides avec `id_remboursement` a NULL — elles l'ont ete
avant que le suivi n'existe.

Revision ID: d4f1b9c5e63a
Revises: c3e0a8b4d529
Create Date: 2026-08-12 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d4f1b9c5e63a"
down_revision = "c3e0a8b4d529"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Remboursements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.Column("date_remboursement", sa.Date(), nullable=False),
        # Chaines en clair et non cles etrangeres : un justificatif deja emis
        # doit rester lisible tel quel si les listes evoluent.
        sa.Column("moyen", sa.String(50), nullable=False),
        sa.Column("etablissement", sa.String(80), nullable=False),
        sa.Column("approuve_par", sa.String(120), nullable=False),
        # Instantane du montant reellement vire : le recalculer ferait bouger un
        # chiffre deja justifie si une note etait corrigee ensuite.
        sa.Column("montant_total", sa.DECIMAL(10, 2), nullable=False),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("chemin_pdf", sa.String(500), nullable=True),
        sa.Column("chemin_xlsx", sa.String(500), nullable=True),
        sa.Column("cree_par", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["id_user"], ["Admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cree_par"], ["Admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_remb_user", "Remboursements", ["id_user"])
    op.create_index("idx_remb_date", "Remboursements", ["date_remboursement"])

    op.add_column(
        "NotesDeFrais", sa.Column("id_remboursement", sa.Integer(), nullable=True)
    )
    op.create_index("idx_nf_remboursement", "NotesDeFrais", ["id_remboursement"])
    op.create_foreign_key(
        "fk_nf_remboursement",
        "NotesDeFrais",
        "Remboursements",
        ["id_remboursement"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_nf_remboursement", "NotesDeFrais", type_="foreignkey")
    op.drop_index("idx_nf_remboursement", table_name="NotesDeFrais")
    op.drop_column("NotesDeFrais", "id_remboursement")

    op.drop_index("idx_remb_date", table_name="Remboursements")
    op.drop_index("idx_remb_user", table_name="Remboursements")
    op.drop_table("Remboursements")
