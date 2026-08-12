"""Categories de depense pour les poles sans evenement.

Jusqu'ici, tout depot exigeait un evenement. Une depense du local — des
courses, du gouter, du materiel — n'en a aucun : il fallait en inventer un pour
satisfaire le formulaire, et le comptable recevait des pieces rattachees a des
evenements fictifs.

Trois changements, tous additifs (aucune colonne existante n'est touchee) :

1. ``Poles.requiert_evenement`` : chaque pole declare ce qu'il attend. Seul le
   pole evenementiel est bascule a vrai — c'est le comportement d'avant pour
   lui, et la nouveaute pour les autres.
2. ``CategoriesDepense`` : le referentiel administrable, avec ses cinq entrees
   initiales.
3. ``id_categorie`` / ``categorie`` sur ``NotesDeFrais`` et ``Factures``.
   Identifiant et libelle en double, comme pour le pole : le nom du PDF envoye
   au comptable est fige au depot et ne doit pas bouger si la categorie est
   renommee.

Les lignes existantes restent valides : leurs colonnes de categorie sont
simplement nulles, et elles portent deja un evenement.

Revision ID: b2d9f7a3c418
Revises: a1c8e6f2b307
Create Date: 2026-08-12 14:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b2d9f7a3c418"
down_revision = "a1c8e6f2b307"
branch_labels = None
depends_on = None


# Doit rester aligne sur `crud/expense_category.DEFAULT_CATEGORIES` : la
# migration sert la production, la constante sert les tests et le
# developpement, qui montent le schema par `create_all`.
CATEGORIES = (
    ("Courses", 1),
    ("Stock goûter", 2),
    ("Achat buvette", 3),
    ("Achat matériel", 4),
    ("Autre", 5),
)


def upgrade() -> None:
    op.add_column(
        "Poles",
        sa.Column(
            "requiert_evenement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # Le pole evenementiel garde son fonctionnement : c'est le seul qui se
    # rattache reellement a un evenement.
    # `LIKE '%nementiel%'` plutot que l'egalite : le pole a pu etre renomme
    # (« Pôle événementiel », « Evenementiel »...) et cette fin de mot les
    # couvre tous, accents compris.
    op.execute(
        sa.text("UPDATE Poles SET requiert_evenement = 1 WHERE nom LIKE '%nementiel%'")
    )

    op.create_table(
        "CategoriesDepense",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nom", sa.String(120), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nom", name="uq_catdep_nom"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_catdep_nom", "CategoriesDepense", ["nom"])
    op.create_index("idx_catdep_active", "CategoriesDepense", ["is_active"])

    op.bulk_insert(
        sa.table(
            "CategoriesDepense",
            sa.column("nom", sa.String),
            sa.column("is_default", sa.Boolean),
            sa.column("is_active", sa.Boolean),
            sa.column("ordre", sa.Integer),
        ),
        [
            {"nom": nom, "is_default": True, "is_active": True, "ordre": ordre}
            for nom, ordre in CATEGORIES
        ],
    )

    for table in ("NotesDeFrais", "Factures"):
        op.add_column(table, sa.Column("id_categorie", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("categorie", sa.String(120), nullable=True))


def downgrade() -> None:
    for table in ("NotesDeFrais", "Factures"):
        op.drop_column(table, "categorie")
        op.drop_column(table, "id_categorie")

    op.drop_index("idx_catdep_active", table_name="CategoriesDepense")
    op.drop_index("idx_catdep_nom", table_name="CategoriesDepense")
    op.drop_table("CategoriesDepense")

    op.drop_column("Poles", "requiert_evenement")
