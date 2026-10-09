"""Buvette : etat de la tablette, cloture de caisse especes, reglages du recap.

- `CaisseEtats` : une seule ligne (id = 1), reecrite par la tablette toutes les
  minutes (batterie, version, SumUp, lecteur, ventes en attente, ecran). Sert la
  fiche « Tablette » de l'application et le recap du soir.
- `CloturesCaisse` : une cloture par jour (`jour` unique). L'attendu est calcule
  par le serveur au moment de la saisie et fige avec l'ecart.
- `BuvetteReglages` : cle / valeur JSON. Amorcee avec `recap_destinataires`, la
  liste d'adresses qui recoit les courriels de la buvette (alertes de stock bas
  et recap du soir) en plus des comptes « AdminStock ». Avant, les alertes
  partaient a TOUS les AdminBenevoles et Super Admin : le 09/10/2026, onze
  personnes ont recu cinq alertes chacune.

Le nouveau role « AdminStock » ne demande aucune migration : `Admins.role` est
un VARCHAR(50) sans contrainte, la liste des roles valides vit dans le code.

Additif et sans risque : trois tables neuves, aucune ecriture dans l'existant.

Revision ID: b2c8d4e6f1a3
Revises: a1b7c3d9e5f2
Create Date: 2026-10-09 10:00:00.000000
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op


revision = "b2c8d4e6f1a3"
down_revision = "a1b7c3d9e5f2"
branch_labels = None
depends_on = None


# Liste demandee par Omar le 09/10/2026. Modifiable ensuite depuis l'ecran
# Buvette > Tablette (PUT /buvette/reglages), sans redeploiement.
RECAP_DESTINATAIRES = [
    "abde.rrahman.marght@gmail.com",
    "benfdila.omir@gmail.com",
    "comptabilite@lekouttab.fr",
    "ThaoDaniel75@gmail.com",
    "daaabou4@gmail.com",
]


def upgrade() -> None:
    op.create_table(
        "CaisseEtats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("batterie_pct", sa.Integer(), nullable=True),
        sa.Column("en_charge", sa.Boolean(), nullable=True),
        sa.Column("version_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_name", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("sumup_connecte", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lecteur_connecte", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lecteur_batterie_pct", sa.Integer(), nullable=True),
        sa.Column("ventes_en_attente", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ventes_rejetees", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ecran", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("recu_at", sa.DateTime(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "CloturesCaisse",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("jour", sa.Date(), nullable=False),
        sa.Column("attendu_cents", sa.Integer(), nullable=False),
        sa.Column("compte_cents", sa.Integer(), nullable=False),
        sa.Column("ecart_cents", sa.Integer(), nullable=False),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("saisi_par", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("jour", name="uq_cloture_caisse_jour"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    reglages = op.create_table(
        "BuvetteReglages",
        sa.Column("cle", sa.String(length=64), primary_key=True),
        sa.Column("valeur", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.bulk_insert(
        reglages,
        [{"cle": "recap_destinataires", "valeur": json.dumps(RECAP_DESTINATAIRES)}],
    )


def downgrade() -> None:
    op.drop_table("BuvetteReglages")
    op.drop_table("CloturesCaisse")
    op.drop_table("CaisseEtats")
